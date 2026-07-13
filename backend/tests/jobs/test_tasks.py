from contextlib import asynccontextmanager

from rq import Retry

from app.jobs.errors import PipelineStepError
from app.jobs.tasks import run_company_intelligence


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
