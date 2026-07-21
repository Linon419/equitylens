import json
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import (
    get_current_user,
    get_db,
    get_job_backend,
    get_market_data_provider,
    get_sec_data_provider,
    get_supply_chain_graph_service,
)
from app.auth.errors import AuthError
from app.core.errors import DomainError
from app.jobs.errors import JobDispatchError
from app.jobs.schemas import JobSubmission
from app.main import create_app
from app.models.user_model import User
from app.providers.market import CompanyProfile, QuoteSnapshot, SymbolMatch
from app.providers.sec import CompanyReference


@dataclass
class FakeMarketProvider:
    provider_name = "yahoo"

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
    facts_calls: int = 0

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

    async def get_company_facts(self, cik: str) -> dict:
        self.facts_calls += 1
        path = (
            Path(__file__).parents[1]
            / "fixtures"
            / "sec"
            / "aapl_companyfacts.json"
        )
        return json.loads(path.read_text())

    async def get_submissions(self, cik: str) -> dict:
        path = (
            Path(__file__).parents[1]
            / "fixtures"
            / "sec"
            / "aapl_submissions.json"
        )
        return json.loads(path.read_text())


@dataclass
class FakeJobBackend:
    calls: list[str] = field(default_factory=list)
    fail: bool = False

    async def enqueue(self, *, job_type: str, payload: dict) -> JobSubmission:
        job_id = str(payload["job_id"])
        self.calls.append(job_id)
        if self.fail:
            raise JobDispatchError("fake timeout", retryable=True)
        return JobSubmission(job_id=f"fake:{job_id}")


@dataclass
class FakeSupplyChainGraphService:
    calls: list[dict] = field(default_factory=list)
    missing: bool = False

    def get_current(
        self,
        *,
        company,
        principal,
        locale: str,
        evidence: set[str],
        limit: int,
    ):
        self.calls.append(
            {
                "symbol": company.symbol,
                "principal_type": principal.principal_type,
                "locale": locale,
                "evidence": evidence,
                "limit": limit,
            }
        )
        if self.missing:
            raise DomainError("GRAPH_NOT_FOUND", 404)
        localized = locale == "zh"
        return {
            "snapshot": {
                "id": "11111111-1111-4111-8111-111111111111",
                "status": "completed",
                "symbol": company.symbol,
                "model_id": "gpt-5-mini",
                "focus_node_key": "company:0000320193",
                "thesis": "苹果产业链" if localized else "Apple supply chain",
                "evidence_coverage": "complete",
                "overall_confidence": "High",
                "node_count": 1,
                "edge_count": 0,
                "generated_at": "2026-07-14T12:00:00Z",
            },
            "nodes": [
                {
                    "id": "22222222-2222-4222-8222-222222222222",
                    "node_key": "company:0000320193",
                    "kind": "company",
                    "layer": "core",
                    "label": "苹果" if localized else "Apple Inc.",
                    "description": "核心公司" if localized else "Focal company",
                    "symbol": company.symbol,
                    "cik": company.cik,
                    "importance": 1.0,
                    "confidence": "High",
                    "rank": 0,
                }
            ],
            "edges": [],
            "sources": [],
            "refresh_job": None,
            "quota": {
                "limit": 2,
                "used": 0,
                "remaining": 2,
                "resets_at": "2026-07-15T00:00:00Z",
            },
        }


@dataclass
class Phase2ApiHarness:
    client: TestClient
    market: FakeMarketProvider
    sec: FakeSecProvider
    jobs: FakeJobBackend
    graphs: FakeSupplyChainGraphService
    engine: object


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
    jobs = FakeJobBackend()
    graphs = FakeSupplyChainGraphService()
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
    app.dependency_overrides[get_job_backend] = lambda: jobs
    app.dependency_overrides[get_supply_chain_graph_service] = lambda: graphs
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        yield Phase2ApiHarness(
            client=client,
            market=market,
            sec=sec,
            jobs=jobs,
            graphs=graphs,
            engine=engine,
        )
