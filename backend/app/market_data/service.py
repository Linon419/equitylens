import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlmodel import Session, select

from app.core.errors import DomainError
from app.market_data.synthetic import PROVIDER_NAME as SYNTHETIC_PROVIDER_NAME
from app.models.company_model import Company
from app.models.market_model import MarketSnapshot
from app.providers.market import MarketDataProvider, QuoteSnapshot

PROFILE_FETCH_TIMEOUT_SECONDS = 5


@dataclass(frozen=True)
class MarketResult:
    snapshot: MarketSnapshot
    freshness: Literal["fresh", "stale"]

    @property
    def price(self) -> Decimal | None:
        return self.snapshot.price


async def get_market_snapshot(
    session: Session,
    company: Company,
    provider: MarketDataProvider,
    *,
    now: datetime | None = None,
    ttl_seconds: int = 900,
) -> MarketResult:
    current_time = now or datetime.now(UTC)
    latest = _latest_snapshot(
        session,
        company,
        getattr(provider, "provider_name", None),
    )
    if latest is not None and _is_fresh(
        latest.fetched_at,
        current_time,
        ttl_seconds,
    ):
        return MarketResult(_normalize_snapshot(latest), "fresh")

    try:
        async with asyncio.timeout(15):
            quote = await provider.get_quote(company.symbol)
    except Exception as error:
        if latest is not None:
            return MarketResult(_normalize_snapshot(latest), "stale")
        raise DomainError("MARKET_DATA_UNAVAILABLE", 503) from error

    snapshot = _persist_snapshot(session, company, quote, current_time)
    return MarketResult(snapshot, "fresh")


async def refresh_company_profile(
    session: Session,
    company: Company,
    provider: MarketDataProvider,
    *,
    now: datetime | None = None,
    ttl_seconds: int = 7 * 24 * 60 * 60,
) -> Company:
    current_time = now or datetime.now(UTC)
    synthetic_profile = (
        getattr(provider, "provider_name", None) == SYNTHETIC_PROVIDER_NAME
    )
    if (
        not synthetic_profile
        and company.profile_fetched_at is not None
        and _is_fresh(company.profile_fetched_at, current_time, ttl_seconds)
    ):
        return company

    try:
        async with asyncio.timeout(PROFILE_FETCH_TIMEOUT_SECONDS):
            profile = await provider.get_company_profile(company.symbol)
    except Exception:
        return company

    company.name = profile.name
    company.sector = profile.sector
    company.industry = profile.industry
    company.description = profile.description
    company.profile_fetched_at = current_time
    company.updated_at = current_time
    session.add(company)
    session.commit()
    session.refresh(company)
    company.profile_fetched_at = _as_utc(company.profile_fetched_at)
    company.updated_at = _as_utc(company.updated_at)
    return company


def _latest_snapshot(
    session: Session,
    company: Company,
    provider_name: str | None = None,
) -> MarketSnapshot | None:
    statement = select(MarketSnapshot).where(
        MarketSnapshot.company_id == company.id
    )
    if provider_name is not None:
        statement = statement.where(MarketSnapshot.provider == provider_name)
    return session.exec(statement.order_by(MarketSnapshot.fetched_at.desc())).first()


def _persist_snapshot(
    session: Session,
    company: Company,
    quote: QuoteSnapshot,
    fetched_at: datetime,
) -> MarketSnapshot:
    snapshot = MarketSnapshot(
        company_id=company.id,
        price=quote.price,
        previous_close=quote.previous_close,
        price_change=quote.price_change,
        price_change_percent=quote.price_change_percent,
        market_cap=quote.market_cap,
        trailing_eps=quote.trailing_eps,
        trailing_pe=quote.trailing_pe,
        forward_pe=quote.forward_pe,
        currency=quote.currency,
        provider=quote.provider,
        observed_at=quote.observed_at,
        fetched_at=fetched_at,
        missing_reasons=quote.missing_reasons,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return _normalize_snapshot(snapshot)


def _is_fresh(value: datetime, now: datetime, ttl_seconds: int) -> bool:
    return now - _as_utc(value) <= timedelta(seconds=ttl_seconds)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _normalize_snapshot(snapshot: MarketSnapshot) -> MarketSnapshot:
    snapshot.observed_at = _as_utc(snapshot.observed_at)
    snapshot.fetched_at = _as_utc(snapshot.fetched_at)
    return snapshot
