import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.companies.service import (
    get_or_create_company,
    normalize_symbol,
    search_companies,
)
from app.core.errors import DomainError
from app.filings.sec_client import SecClient
from app.models.company_model import Company
from app.providers.market import SymbolMatch
from app.providers.sec import CompanyReference

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class FakeMarketProvider:
    provider_name = "yahoo"

    async def search_symbols(self, query: str) -> list[SymbolMatch]:
        assert query == "apple"
        return [SymbolMatch(symbol="aapl", name="Apple Inc.", exchange="NMS")]


class FakeSecProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def resolve_company(self, symbol: str) -> CompanyReference:
        self.calls += 1
        if symbol != "AAPL":
            raise DomainError("COMPANY_NOT_FOUND", 404)
        return CompanyReference(
            symbol="AAPL",
            cik="0000320193",
            name="Apple Inc.",
            exchange="Nasdaq",
        )


class RacingSecProvider(FakeSecProvider):
    def __init__(self, engine) -> None:
        super().__init__()
        self.engine = engine

    async def resolve_company(self, symbol: str) -> CompanyReference:
        reference = await super().resolve_company(symbol)
        with Session(self.engine) as competing_session:
            competing_session.add(
                Company(
                    symbol=reference.symbol,
                    cik=reference.cik,
                    name=reference.name,
                    exchange=reference.exchange,
                )
            )
            competing_session.commit()
        return reference


def build_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


@pytest.mark.asyncio
async def test_search_normalizes_provider_results() -> None:
    result = await search_companies(FakeMarketProvider(), " apple ")

    assert result[0].model_dump() == {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NMS",
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" brk-b ", "BRK-B"), ("bf.b", "BF.B"), ("aapl", "AAPL")],
)
def test_symbol_normalization_accepts_us_tickers(raw: str, expected: str) -> None:
    assert normalize_symbol(raw) == expected


@pytest.mark.parametrize("raw", ["", "-AAPL", "AAPL/US", "AAPL$"])
def test_symbol_normalization_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(DomainError, match="COMPANY_SYMBOL_INVALID"):
        normalize_symbol(raw)


@pytest.mark.asyncio
async def test_get_or_create_company_reuses_the_persisted_identity() -> None:
    provider = FakeSecProvider()
    with build_session() as session:
        first = await get_or_create_company(session, provider, "aapl")
        second = await get_or_create_company(session, provider, "AAPL")

    assert first.id == second.id
    assert first.cik == "0000320193"
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_get_or_create_company_recovers_from_a_concurrent_insert(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'companies.db'}")
    SQLModel.metadata.create_all(engine)
    provider = RacingSecProvider(engine)

    with Session(engine) as session:
        company = await get_or_create_company(session, provider, "AAPL")

    assert company.symbol == "AAPL"
    assert provider.calls == 1
    with Session(engine) as session:
        assert len(session.exec(select(Company)).all()) == 1


@pytest.mark.asyncio
async def test_sec_directory_maps_fields_and_sends_user_agent() -> None:
    payload = json.loads(
        (FIXTURES / "sec/company_tickers_exchange.json").read_text()
    )

    async def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "EquityLens test admin@example.com"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(respond)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = SecClient(
            client=client,
            user_agent="EquityLens test admin@example.com",
        )
        company = await provider.resolve_company("aapl")

    assert company == CompanyReference(
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        exchange="Nasdaq",
    )


@pytest.mark.asyncio
async def test_sec_directory_returns_stable_not_found_error() -> None:
    payload = json.loads(
        (FIXTURES / "sec/company_tickers_exchange.json").read_text()
    )
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=payload))

    async with httpx.AsyncClient(transport=transport) as client:
        provider = SecClient(
            client=client,
            user_agent="EquityLens test admin@example.com",
        )
        with pytest.raises(DomainError, match="COMPANY_NOT_FOUND"):
            await provider.resolve_company("NVDA")
