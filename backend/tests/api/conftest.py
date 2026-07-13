from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import (
    get_current_user,
    get_db,
    get_market_data_provider,
    get_sec_data_provider,
)
from app.auth.errors import AuthError
from app.main import create_app
from app.models.user_model import User
from app.providers.market import CompanyProfile, QuoteSnapshot, SymbolMatch
from app.providers.sec import CompanyReference


@dataclass
class FakeMarketProvider:
    queries: list[str] = field(default_factory=list)
    quote_calls: int = 0
    profile_calls: int = 0

    async def search_symbols(self, query: str) -> list[SymbolMatch]:
        self.queries.append(query)
        return [SymbolMatch(symbol="AAPL", name="Apple Inc.", exchange="NMS")]

    async def get_quote(self, symbol: str) -> QuoteSnapshot:
        self.quote_calls += 1
        return QuoteSnapshot(
            symbol=symbol,
            price=Decimal("212.48"),
            previous_close=Decimal("209.88"),
            market_cap=Decimal("3170000000000"),
            trailing_eps=Decimal("6.42"),
            trailing_pe=Decimal("33.096573"),
            forward_pe=Decimal("29.4"),
            currency="USD",
            observed_at=datetime(2026, 7, 13, 12, tzinfo=UTC),
            provider="yahoo",
            missing_reasons={},
            price_change=Decimal("2.60"),
            price_change_percent=Decimal("1.238803"),
        )

    async def get_company_profile(self, symbol: str) -> CompanyProfile:
        self.profile_calls += 1
        return CompanyProfile(
            symbol=symbol,
            name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            description="Apple designs and sells devices and services.",
        )


@dataclass
class FakeSecProvider:
    calls: list[str] = field(default_factory=list)

    async def resolve_company(self, symbol: str) -> CompanyReference:
        self.calls.append(symbol)
        if symbol not in {"AAPL", "MSFT"}:
            from app.core.errors import DomainError

            raise DomainError("COMPANY_NOT_FOUND", 404)
        return CompanyReference(
            symbol=symbol,
            cik="0000320193" if symbol == "AAPL" else "0000789019",
            name="Apple Inc." if symbol == "AAPL" else "Microsoft Corp",
            exchange="Nasdaq",
        )


@dataclass
class Phase2ApiHarness:
    client: TestClient
    market: FakeMarketProvider
    sec: FakeSecProvider


@pytest.fixture
def phase_2_api() -> Generator[Phase2ApiHarness, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    market = FakeMarketProvider()
    sec = FakeSecProvider()
    app = create_app()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def override_current_user(
        x_test_user_id: Annotated[int | None, Header()] = None,
    ) -> User:
        if x_test_user_id is None:
            raise AuthError("AUTH_REQUIRED", 401)
        return User(
            id=x_test_user_id,
            email=f"user-{x_test_user_id}@example.com",
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_market_data_provider] = lambda: market
    app.dependency_overrides[get_sec_data_provider] = lambda: sec
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        yield Phase2ApiHarness(client=client, market=market, sec=sec)
