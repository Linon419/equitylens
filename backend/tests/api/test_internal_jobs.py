from collections.abc import Generator
from dataclasses import dataclass, field
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import (
    get_company_intelligence_pipeline,
    get_db,
    get_supply_chain_graph_pipeline,
)
from app.main import create_app
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.supply_chain.openai_agent import SupplyChainAgentError

NEXT_STATE = {
    "download": "downloading",
    "parse": "parsing",
    "analyze": "analyzing",
    "verify": "verifying",
    "localize": "completed",
}
GRAPH_NEXT_STATE = {
    "collect": "collecting",
    "extract": "extracting",
    "resolve": "resolving",
    "verify": "verifying",
    "localize": "localizing",
    "publish": "completed",
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
class FakeGraphPipeline:
    session: Session
    calls: list[str] = field(default_factory=list)
    failure: Exception | None = None
    completed_steps: set[str] = field(default_factory=set)
    resume_calls: int = 0

    def resume_retry(self, job_id: UUID) -> None:
        self.resume_calls += 1
        job = self.session.get(IngestionJob, job_id)
        assert job is not None
        job.state = "queued"
        job.current_step = "queued"
        job.error_code = None
        self.session.add(job)
        self.session.commit()

    def is_step_complete(self, job_id: UUID, step: str) -> bool:
        return step in self.completed_steps

    async def _run(self, job_id: UUID, step: str) -> None:
        self.calls.append(step)
        if self.failure is not None:
            job = self.session.get(IngestionJob, job_id)
            assert job is not None
            job.state = "failed"
            job.current_step = GRAPH_NEXT_STATE[step]
            job.error_code = getattr(self.failure, "code", "GRAPH_STEP_FAILED")
            job.retry_eligible = bool(getattr(self.failure, "retryable", True))
            self.session.add(job)
            self.session.commit()
            raise self.failure
        job = self.session.get(IngestionJob, job_id)
        assert job is not None
        job.state = GRAPH_NEXT_STATE[step]
        job.current_step = GRAPH_NEXT_STATE[step]
        self.session.add(job)
        self.session.commit()
        self.completed_steps.add(step)

    async def collect(self, job_id: UUID) -> None:
        await self._run(job_id, "collect")

    async def extract(self, job_id: UUID) -> None:
        await self._run(job_id, "extract")

    async def resolve(self, job_id: UUID) -> None:
        await self._run(job_id, "resolve")

    async def verify(self, job_id: UUID) -> None:
        await self._run(job_id, "verify")

    async def localize(self, job_id: UUID) -> None:
        await self._run(job_id, "localize")

    async def publish(self, job_id: UUID) -> None:
        await self._run(job_id, "publish")


@dataclass
class InternalHarness:
    client: TestClient
    job_id: UUID
    pipeline: FakePipeline
    graph_job_id: UUID
    graph_pipeline: FakeGraphPipeline


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
    graph_job = IngestionJob(
        job_type="supply_chain_graph",
        company_id=company.id,
        requested_by_type="guest",
        requested_by_hash="guest-hash",
        deduplication_key="internal-graph-job-test",
        state="queued",
        current_step="queued",
    )
    session.add(graph_job)
    session.commit()
    session.refresh(job)
    session.refresh(graph_job)
    pipeline = FakePipeline(session)
    graph_pipeline = FakeGraphPipeline(session)
    app = create_app()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_company_intelligence_pipeline] = lambda: pipeline
    app.dependency_overrides[get_supply_chain_graph_pipeline] = lambda: graph_pipeline
    with TestClient(app) as client:
        yield InternalHarness(
            client,
            job.id,
            pipeline,
            graph_job.id,
            graph_pipeline,
        )
    session.close()


def headers(job_id: UUID, step: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {'i' * 32}",
        "x-idempotency-key": f"{job_id}:{step}:v1",
    }


def graph_headers(job_id: UUID, step: str) -> dict[str, str]:
    return {
        "authorization": f"Bearer {'i' * 32}",
        "x-idempotency-key": f"{job_id}:supply-chain-graph:{step}:v1",
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


def test_graph_steps_run_in_durable_order(internal_jobs) -> None:
    job_id = internal_jobs.graph_job_id
    for step in GRAPH_NEXT_STATE:
        response = internal_jobs.client.post(
            f"/api/v1/internal/jobs/{job_id}/supply-chain-graph/{step}",
            headers=graph_headers(job_id, step),
        )
        assert response.status_code == 204

    assert internal_jobs.graph_pipeline.calls == list(GRAPH_NEXT_STATE)


def test_graph_step_replay_returns_stored_result(internal_jobs) -> None:
    job_id = internal_jobs.graph_job_id
    path = f"/api/v1/internal/jobs/{job_id}/supply-chain-graph/collect"
    request_headers = graph_headers(job_id, "collect")

    first = internal_jobs.client.post(path, headers=request_headers)
    replay = internal_jobs.client.post(path, headers=request_headers)

    assert first.status_code == replay.status_code == 204
    assert internal_jobs.graph_pipeline.calls == ["collect"]


def test_graph_step_state_without_artifact_runs_stage(internal_jobs) -> None:
    job_id = internal_jobs.graph_job_id
    job = internal_jobs.graph_pipeline.session.get(IngestionJob, job_id)
    assert job is not None
    job.state = "collecting"
    job.current_step = "collecting"
    internal_jobs.graph_pipeline.session.add(job)
    internal_jobs.graph_pipeline.session.commit()

    response = internal_jobs.client.post(
        f"/api/v1/internal/jobs/{job_id}/supply-chain-graph/collect",
        headers=graph_headers(job_id, "collect"),
    )

    assert response.status_code == 204
    assert internal_jobs.graph_pipeline.calls == ["collect"]


def test_graph_step_rejects_job_type_mismatch(internal_jobs) -> None:
    response = internal_jobs.client.post(
        f"/api/v1/internal/jobs/{internal_jobs.job_id}/supply-chain-graph/collect",
        headers=graph_headers(internal_jobs.job_id, "collect"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "JOB_TYPE_CONFLICT"


def test_graph_step_rejects_mismatched_idempotency_key(internal_jobs) -> None:
    job_id = internal_jobs.graph_job_id
    response = internal_jobs.client.post(
        f"/api/v1/internal/jobs/{job_id}/supply-chain-graph/collect",
        headers=graph_headers(job_id, "extract"),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INTERNAL_JOB_IDEMPOTENCY_INVALID"


def test_graph_step_rejects_unsupported_step(internal_jobs) -> None:
    job_id = internal_jobs.graph_job_id
    response = internal_jobs.client.post(
        f"/api/v1/internal/jobs/{job_id}/supply-chain-graph/unknown",
        headers=graph_headers(job_id, "unknown"),
    )

    assert response.status_code == 422


def test_graph_step_maps_retryable_failure_to_service_unavailable(
    internal_jobs,
) -> None:
    job_id = internal_jobs.graph_job_id
    internal_jobs.graph_pipeline.failure = SupplyChainAgentError(
        "AGENT_PROVIDER_UNAVAILABLE",
        retryable=True,
    )

    response = internal_jobs.client.post(
        f"/api/v1/internal/jobs/{job_id}/supply-chain-graph/collect",
        headers=graph_headers(job_id, "collect"),
    )

    assert response.status_code == 503
    assert response.json()["code"] == "AGENT_PROVIDER_UNAVAILABLE"

    internal_jobs.graph_pipeline.failure = None
    replay = internal_jobs.client.post(
        f"/api/v1/internal/jobs/{job_id}/supply-chain-graph/collect",
        headers=graph_headers(job_id, "collect"),
    )

    assert replay.status_code == 204
    assert internal_jobs.graph_pipeline.resume_calls == 1
    assert internal_jobs.graph_pipeline.calls == ["collect", "collect"]
