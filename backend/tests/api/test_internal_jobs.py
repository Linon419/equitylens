from collections.abc import Generator
from dataclasses import dataclass, field
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_company_intelligence_pipeline, get_db
from app.main import create_app
from app.models.company_model import Company
from app.models.job_model import IngestionJob

NEXT_STATE = {
    "download": "downloading",
    "parse": "parsing",
    "analyze": "analyzing",
    "verify": "verifying",
    "localize": "completed",
}


@dataclass
class FakePipeline:
    session: Session
    calls: list[str] = field(default_factory=list)

    async def _run(self, job_id: UUID, step: str) -> None:
        self.calls.append(step)
        job = self.session.get(IngestionJob, job_id)
        assert job is not None
        job.state = NEXT_STATE[step]
        job.current_step = NEXT_STATE[step]
        self.session.add(job)
        self.session.commit()

    async def download(self, job_id: UUID) -> None:
        await self._run(job_id, "download")

    async def parse(self, job_id: UUID) -> None:
        await self._run(job_id, "parse")

    async def analyze(self, job_id: UUID) -> None:
        await self._run(job_id, "analyze")

    async def verify(self, job_id: UUID) -> None:
        await self._run(job_id, "verify")

    async def localize(self, job_id: UUID) -> None:
        await self._run(job_id, "localize")


@dataclass
class InternalHarness:
    client: TestClient
    job_id: UUID
    pipeline: FakePipeline


@pytest.fixture
def internal_jobs() -> Generator[InternalHarness, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    company = Company(
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        exchange="Nasdaq",
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    job = IngestionJob(
        company_id=company.id,
        requested_by_type="guest",
        requested_by_hash="guest-hash",
        deduplication_key="internal-job-test",
        state="queued",
        current_step="queued",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    pipeline = FakePipeline(session)
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_company_intelligence_pipeline] = lambda: pipeline
    with TestClient(app) as client:
        yield InternalHarness(client, job.id, pipeline)
    session.close()


def headers(job_id: UUID, step: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {'i' * 32}",
        "x-idempotency-key": f"{job_id}:{step}:v1",
    }


def test_internal_step_requires_service_token(internal_jobs) -> None:
    response = internal_jobs.client.post(
        f"/api/v1/internal/jobs/{internal_jobs.job_id}/download"
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INTERNAL_JOB_AUTH_REQUIRED"


def test_internal_step_is_idempotent(internal_jobs) -> None:
    path = f"/api/v1/internal/jobs/{internal_jobs.job_id}/download"
    request_headers = headers(internal_jobs.job_id, "download")

    first = internal_jobs.client.post(path, headers=request_headers)
    second = internal_jobs.client.post(path, headers=request_headers)

    assert first.status_code == second.status_code == 204
    assert internal_jobs.pipeline.calls == ["download"]


def test_internal_steps_run_in_durable_order(internal_jobs) -> None:
    for step in ("download", "parse", "analyze", "verify", "localize"):
        response = internal_jobs.client.post(
            f"/api/v1/internal/jobs/{internal_jobs.job_id}/{step}",
            headers=headers(internal_jobs.job_id, step),
        )
        assert response.status_code == 204

    assert internal_jobs.pipeline.calls == [
        "download",
        "parse",
        "analyze",
        "verify",
        "localize",
    ]


def test_internal_step_rejects_mismatched_idempotency_key(internal_jobs) -> None:
    response = internal_jobs.client.post(
        f"/api/v1/internal/jobs/{internal_jobs.job_id}/download",
        headers={
            "authorization": f"Bearer {'i' * 32}",
            "x-idempotency-key": f"{internal_jobs.job_id}:parse:v1",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INTERNAL_JOB_IDEMPOTENCY_INVALID"
