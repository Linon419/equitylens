from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.company_model import Company
from app.models.market_model import MarketSnapshot
from app.providers.sec import CompanyReference
from app.watchlist.service import (
    add_to_watchlist,
    list_watchlist,
    remove_from_watchlist,
)

NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)


class FakeSecProvider:
    async def resolve_company(self, symbol: str) -> CompanyReference:
        return CompanyReference(
            symbol=symbol,
            cik="0000320193",
            name="Apple Inc.",
            exchange="Nasdaq",
        )


def build_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.asyncio
async def test_watchlist_is_idempotent_and_user_scoped() -> None:
    with build_session() as session:
        first = await add_to_watchlist(session, 1, "AAPL", FakeSecProvider())
        second = await add_to_watchlist(session, 1, "AAPL", FakeSecProvider())

        assert first.id == second.id
        assert [item.symbol for item in list_watchlist(session, 1)] == ["AAPL"]
        assert list_watchlist(session, 2) == []

        assert remove_from_watchlist(session, 2, "AAPL") is False
        assert [item.symbol for item in list_watchlist(session, 1)] == ["AAPL"]
        assert remove_from_watchlist(session, 1, "AAPL") is True
        assert remove_from_watchlist(session, 1, "AAPL") is False


def test_watchlist_includes_latest_market_context() -> None:
    with build_session() as session:
        company = Company(symbol="AAPL", cik="0000320193", name="Apple Inc.")
        session.add(company)
        session.commit()
        session.refresh(company)
        assert company.id is not None

        session.add_all(
            [
                MarketSnapshot(
                    company_id=company.id,
                    price=Decimal("210"),
                    trailing_pe=Decimal("31"),
                    provider="yahoo",
                    observed_at=NOW,
                    fetched_at=NOW,
                ),
                MarketSnapshot(
                    company_id=company.id,
                    price=Decimal("212.48"),
                    trailing_pe=Decimal("33.096573"),
                    provider="yahoo",
                    observed_at=NOW,
                    fetched_at=NOW.replace(hour=13),
                ),
            ]
        )
        session.commit()

        from app.models.company_model import Watchlist

        session.add(Watchlist(user_id=1, company_id=company.id))
        session.commit()

        item = list_watchlist(session, 1)[0]

    assert item.price == Decimal("212.48")
    assert item.trailing_pe == Decimal("33.096573")
