from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import (
    get_db,
    get_intelligence_generator,
    get_job_backend,
    get_market_data_provider,
    get_optional_current_user,
    get_sec_data_provider,
)
from app.jobs.pipeline import CompanyIntelligencePipeline
from app.main import create_app
from app.models.job_model import IngestionJob
from app.models.user_model import User
from app.quota.identity import sign_guest_assertion
from tests.fixtures.company_intelligence import (
    COMPANY_SYMBOLS,
    DeterministicIntelligenceGenerator,
    DeterministicMarketProvider,
    DeterministicSecProvider,
    RecordingJobBackend,
)

GUEST_ONE = "11111111-1111-4111-8111-111111111111"
GUEST_TWO = "22222222-2222-4222-8222-222222222222"


@dataclass
class JourneyHarness:
    client: TestClient
    engine: object
    sec: DeterministicSecProvider
    generator: DeterministicIntelligenceGenerator
    jobs: RecordingJobBackend

    def run_job(self, job_id: str) -> None:
        with Session(self.engine) as session:
            pipeline = CompanyIntelligencePipeline(
                session,
                self.sec,
                self.generator,
                schema_version="company-intelligence-v1",
                prompt_version="company-intelligence-2026-07-13",
            )
            import asyncio

            asyncio.run(pipeline.download(UUID(job_id)))
            asyncio.run(pipeline.parse(UUID(job_id)))
            asyncio.run(pipeline.analyze(UUID(job_id)))
            asyncio.run(pipeline.verify(UUID(job_id)))
            asyncio.run(pipeline.localize(UUID(job_id)))


@pytest.fixture
def journey() -> Generator[JourneyHarness, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    sec = DeterministicSecProvider()
    market = DeterministicMarketProvider()
    generator = DeterministicIntelligenceGenerator()
    jobs = RecordingJobBackend()
    app = create_app()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def optional_user(
        x_test_user_id: Annotated[int | None, Header()] = None,
    ) -> User | None:
        if x_test_user_id is None:
            return None
        return User(
            id=x_test_user_id,
            email=f"investor-{x_test_user_id}@example.com",
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_market_data_provider] = lambda: market
    app.dependency_overrides[get_sec_data_provider] = lambda: sec
    app.dependency_overrides[get_intelligence_generator] = lambda: generator
    app.dependency_overrides[get_job_backend] = lambda: jobs
    app.dependency_overrides[get_optional_current_user] = optional_user

    with TestClient(app) as client:
        yield JourneyHarness(client, engine, sec, generator, jobs)


def guest_headers(guest_id: str, ip_hash: str = "a" * 64) -> dict[str, str]:
    return {
        "x-guest-assertion": sign_guest_assertion(
            guest_id=guest_id,
            ip_hash=ip_hash,
            secret="g" * 32,
            now=datetime.now(UTC),
        )
    }


def test_guest_research_journey(journey: JourneyHarness) -> None:
    search = journey.client.get("/api/v1/companies/search?q=apple")
    assert search.status_code == 200
    assert search.json()["items"][0]["symbol"] == "AAPL"

    headers = guest_headers(GUEST_ONE)
    sync = journey.client.post(
        "/api/v1/companies/AAPL/sync",
        headers=headers,
    )
    assert sync.status_code == 202
    assert sync.json()["quota"]["remaining"] == 1
    job_id = sync.json()["job"]["id"]

    duplicate = journey.client.post(
        "/api/v1/companies/AAPL/sync",
        headers=headers,
    )
    assert duplicate.json()["status"] == "active_job"
    assert duplicate.json()["job"]["id"] == job_id

    journey.run_job(job_id)

    job = journey.client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    market = journey.client.get("/api/v1/companies/AAPL/market")
    financials = journey.client.get("/api/v1/companies/AAPL/financials")
    intelligence = journey.client.get(
        "/api/v1/companies/AAPL/intelligence?locale=en"
    )
    quota = journey.client.get("/api/v1/agent-quota", headers=headers)

    assert job.json()["state"] == "completed"
    assert market.json()["trailing_pe"]["value"] == "33.09657300"
    revenue = next(
        row
        for row in financials.json()["series"]
        if row["metric_key"] == "revenue"
    )
    assert len(revenue["annual"]) == 4
    assert revenue["ttm"] is not None
    content = intelligence.json()["content"]
    assert content["upstream"][0]["citation_ids"]
    assert content["company_layer"][0]["citation_ids"]
    assert content["downstream"][0]["citation_ids"]
    assert quota.json()["remaining"] == 1


def test_guest_third_analysis_returns_429(journey: JourneyHarness) -> None:
    headers = guest_headers(GUEST_ONE)
    for symbol in COMPANY_SYMBOLS[:2]:
        response = journey.client.post(
            f"/api/v1/companies/{symbol}/sync",
            headers=headers,
        )
        assert response.status_code == 202

    blocked = journey.client.post(
        f"/api/v1/companies/{COMPANY_SYMBOLS[2]}/sync",
        headers=headers,
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "AGENT_DAILY_QUOTA_EXCEEDED"


def test_shared_ip_limit_applies_across_guest_ids(
    journey: JourneyHarness,
) -> None:
    shared_ip_hash = "b" * 64
    for index, symbol in enumerate(COMPANY_SYMBOLS[:10]):
        guest_id = f"00000000-0000-4000-8000-{index + 1:012d}"
        response = journey.client.post(
            f"/api/v1/companies/{symbol}/sync",
            headers=guest_headers(guest_id, shared_ip_hash),
        )
        assert response.status_code == 202

    blocked = journey.client.post(
        f"/api/v1/companies/{COMPANY_SYMBOLS[10]}/sync",
        headers=guest_headers(GUEST_TWO, shared_ip_hash),
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "AGENT_IP_DAILY_QUOTA_EXCEEDED"


def test_authenticated_user_receives_ten_analyses(
    journey: JourneyHarness,
) -> None:
    headers = {"x-test-user-id": "7"}
    for symbol in COMPANY_SYMBOLS[:10]:
        response = journey.client.post(
            f"/api/v1/companies/{symbol}/sync",
            headers=headers,
        )
        assert response.status_code == 202

    blocked = journey.client.post(
        f"/api/v1/companies/{COMPANY_SYMBOLS[10]}/sync",
        headers=headers,
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "AGENT_DAILY_QUOTA_EXCEEDED"


def test_failed_job_can_retry_once(journey: JourneyHarness) -> None:
    headers = guest_headers(GUEST_ONE)
    sync = journey.client.post(
        "/api/v1/companies/AAPL/sync",
        headers=headers,
    )
    job_id = sync.json()["job"]["id"]
    with Session(journey.engine) as session:
        job = session.get(IngestionJob, UUID(job_id))
        assert job is not None
        job.state = "failed"
        job.current_step = "analyzing"
        job.error_code = "INTELLIGENCE_GENERATION_FAILED"
        job.retry_eligible = True
        session.add(job)
        session.commit()

    retried = journey.client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers=headers,
    )
    second_retry = journey.client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers=headers,
    )

    assert retried.status_code == 200
    assert retried.json()["attempt_count"] == 1
    assert second_retry.status_code == 409
    assert second_retry.json()["code"] == "JOB_RETRY_UNAVAILABLE"
