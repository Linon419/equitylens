from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.errors import DomainError
from app.market_data.service import get_market_snapshot, refresh_company_profile
from app.models.company_model import Company
from app.providers.market import CompanyProfile, QuoteSnapshot

NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)


class FakeMarketProvider:
    def __init__(self) -> None:
        self.quote_calls = 0
        self.profile_calls = 0
        self.error: Exception | None = None

    async def get_quote(self, symbol: str) -> QuoteSnapshot:
        self.quote_calls += 1
        if self.error is not None:
            raise self.error
        return QuoteSnapshot(
            symbol=symbol,
            price=Decimal("212.48"),
            previous_close=Decimal("209.88"),
            market_cap=Decimal("3170000000000"),
            trailing_eps=Decimal("6.42"),
            trailing_pe=Decimal("33.096573"),
            forward_pe=Decimal("29.4"),
            currency="USD",
            observed_at=NOW,
            provider="yahoo",
            missing_reasons={},
            price_change=Decimal("2.60"),
            price_change_percent=Decimal("1.238803"),
        )

    async def get_company_profile(self, symbol: str) -> CompanyProfile:
        self.profile_calls += 1
        if self.error is not None:
            raise self.error
        return CompanyProfile(
            symbol=symbol,
            name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            description="Apple designs and sells devices and services.",
        )


def build_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def add_company(session: Session, symbol: str = "AAPL") -> Company:
    company = Company(symbol=symbol, cik="0000320193", name="Apple Inc.")
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


@pytest.mark.asyncio
async def test_quote_cache_and_stale_fallback() -> None:
    provider = FakeMarketProvider()
    with build_session() as session:
        company = add_company(session)
        fresh = await get_market_snapshot(session, company, provider, now=NOW)
        cached = await get_market_snapshot(
            session,
            company,
            provider,
            now=NOW + timedelta(minutes=5),
        )
        provider.error = RuntimeError("timeout")
        stale = await get_market_snapshot(
            session,
            company,
            provider,
            now=NOW + timedelta(hours=1),
        )

    assert provider.quote_calls == 2
    assert fresh.freshness == cached.freshness == "fresh"
    assert stale.freshness == "stale"
    assert stale.price == Decimal("212.48")


@pytest.mark.asyncio
async def test_initial_quote_failure_has_stable_error() -> None:
    provider = FakeMarketProvider()
    provider.error = RuntimeError("timeout")

    with build_session() as session:
        company = add_company(session)
        with pytest.raises(DomainError, match="MARKET_DATA_UNAVAILABLE") as error:
            await get_market_snapshot(session, company, provider, now=NOW)

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_company_profile_has_an_independent_seven_day_ttl() -> None:
    provider = FakeMarketProvider()
    with build_session() as session:
        company = add_company(session)
        first = await refresh_company_profile(session, company, provider, now=NOW)
        cached = await refresh_company_profile(
            session,
            first,
            provider,
            now=NOW + timedelta(days=5),
        )
        refreshed = await refresh_company_profile(
            session,
            cached,
            provider,
            now=NOW + timedelta(days=8),
        )

    assert provider.profile_calls == 2
    assert refreshed.sector == "Technology"
    assert refreshed.industry == "Consumer Electronics"
    assert refreshed.profile_fetched_at == NOW + timedelta(days=8)


@pytest.mark.asyncio
async def test_profile_failure_preserves_the_last_valid_profile() -> None:
    provider = FakeMarketProvider()
    with build_session() as session:
        company = add_company(session)
        persisted = await refresh_company_profile(session, company, provider, now=NOW)
        provider.error = RuntimeError("timeout")
        fallback = await refresh_company_profile(
            session,
            persisted,
            provider,
            now=NOW + timedelta(days=8),
        )

    assert fallback.sector == "Technology"
    assert fallback.profile_fetched_at == NOW
