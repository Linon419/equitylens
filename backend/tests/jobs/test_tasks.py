from contextlib import asynccontextmanager
from datetime import UTC, datetime

from rq import Retry

from app.jobs.errors import PipelineStepError
from app.jobs.tasks import (
    _prepare_retry,
    run_company_intelligence,
    run_supply_chain_graph,
)
from app.models.job_model import IngestionJob
from app.quota.identity import RequestPrincipal
from app.quota.repository import SQLiteQuotaRepository
from app.quota.service import refund_job_analysis, reserve_job_analysis
from app.supply_chain.openai_agent import SupplyChainAgentError


class FakePipeline:
    def __init__(self, failure: PipelineStepError | None = None) -> None:
        self.failure = failure
        self.calls: list[str] = []

    async def _step(self, name: str) -> None:
        self.calls.append(name)
        if self.failure is not None:
            error = self.failure
            self.failure = None
            raise error

    async def download(self, job_id) -> None:
        await self._step("download")

    async def parse(self, job_id) -> None:
        await self._step("parse")

    async def analyze(self, job_id) -> None:
        await self._step("analyze")

    async def verify(self, job_id) -> None:
        await self._step("verify")

    async def localize(self, job_id) -> None:
        await self._step("localize")


def install_pipeline(monkeypatch, pipeline: FakePipeline) -> None:
    @asynccontextmanager
    async def context(job_id):
        yield pipeline

    monkeypatch.setattr("app.jobs.tasks.pipeline_context", context)


class FakeGraphPipeline:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.job_ids = []

    async def run(self, job_id) -> None:
        self.job_ids.append(job_id)
        if self.failure is not None:
            raise self.failure


def install_graph_pipeline(monkeypatch, pipeline: FakeGraphPipeline) -> None:
    @asynccontextmanager
    async def context(job_id):
        yield pipeline

    monkeypatch.setattr("app.jobs.tasks.graph_pipeline_context", context)


def test_task_executes_durable_steps_in_order(monkeypatch) -> None:
    pipeline = FakePipeline()
    install_pipeline(monkeypatch, pipeline)

    result = run_company_intelligence("11111111-1111-4111-8111-111111111111")

    assert result is None
    assert pipeline.calls == [
        "download",
        "parse",
        "analyze",
        "verify",
        "localize",
    ]


def test_task_returns_bounded_retry_for_retryable_failure(monkeypatch) -> None:
    pipeline = FakePipeline(
        PipelineStepError("SEC_DATA_UNAVAILABLE", retryable=True)
    )
    install_pipeline(monkeypatch, pipeline)

    result = run_company_intelligence("11111111-1111-4111-8111-111111111111")

    assert isinstance(result, Retry)
    assert result.max == 3
    assert result.intervals == [30, 120, 300]


def test_task_records_fatal_failure_without_rq_retry(monkeypatch) -> None:
    pipeline = FakePipeline(
        PipelineStepError("INSUFFICIENT_EVIDENCE", retryable=False)
    )
    install_pipeline(monkeypatch, pipeline)

    result = run_company_intelligence("11111111-1111-4111-8111-111111111111")

    assert result is None


def test_graph_task_runs_complete_agent_pipeline(monkeypatch) -> None:
    pipeline = FakeGraphPipeline()
    install_graph_pipeline(monkeypatch, pipeline)

    result = run_supply_chain_graph("11111111-1111-4111-8111-111111111111")

    assert result is None
    assert [str(job_id) for job_id in pipeline.job_ids] == [
        "11111111-1111-4111-8111-111111111111"
    ]


def test_graph_task_returns_retry_for_retryable_agent_failure(monkeypatch) -> None:
    pipeline = FakeGraphPipeline(
        SupplyChainAgentError("AGENT_PROVIDER_UNAVAILABLE", retryable=True)
    )
    install_graph_pipeline(monkeypatch, pipeline)

    result = run_supply_chain_graph("11111111-1111-4111-8111-111111111111")

    assert isinstance(result, Retry)
    assert result.max == 3
    assert result.intervals == [30, 120, 300]


def test_graph_task_stops_retrying_fatal_agent_failure(monkeypatch) -> None:
    pipeline = FakeGraphPipeline(
        SupplyChainAgentError("AGENT_PROVIDER_REJECTED", retryable=False)
    )
    install_graph_pipeline(monkeypatch, pipeline)

    assert (
        run_supply_chain_graph("11111111-1111-4111-8111-111111111111") is None
    )


def test_graph_worker_retry_rereserves_quota_and_resumes_prior_stage(
    job_session,
    job_company,
) -> None:
    now = datetime(2026, 7, 14, 12, tzinfo=UTC)
    principal = RequestPrincipal.guest("worker-guest", "worker-ip")
    repository = SQLiteQuotaRepository(job_session)
    job = IngestionJob(
        job_type="supply_chain_graph",
        company_id=job_company.id,
        requested_by_type="guest",
        requested_by_hash=principal.principal_hash,
        deduplication_key="worker-retry-graph",
        state="failed",
        current_step="localizing",
        error_code="AGENT_PROVIDER_UNAVAILABLE",
        retry_eligible=True,
        created_at=now,
        updated_at=now,
    )
    job_session.add(job)
    job_session.commit()
    reserve_job_analysis(repository, principal, job.id, now.date())
    refund_job_analysis(repository, job.id, now=now)
    job_session.commit()

    _prepare_retry(
        job_session,
        job.id,
        quota_repository=repository,
    )

    job_session.refresh(job)
    assert job.state == "verifying"
    assert job.current_step == "verifying"
    assert job.attempt_count == 1
    assert repository.lease_for_job(job.id).state == "reserved"
