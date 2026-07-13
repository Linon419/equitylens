from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlmodel import Session, select

from app.core.errors import DomainError
from app.filings.service import download_latest_10k
from app.jobs.errors import PipelineStepError
from app.jobs.state import has_reached, next_state
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.research_model import (
    CompanyIntelligenceSnapshot,
    Filing,
    FilingSection,
)
from app.providers.sec import SecDataProvider
from app.research.service import (
    IntelligenceGenerator,
    generate_draft,
    localize_snapshot,
    verify_snapshot,
)

ERROR_CODES = {
    "downloading": "FILING_DOWNLOAD_FAILED",
    "parsing": "FILING_PARSE_FAILED",
    "analyzing": "INTELLIGENCE_GENERATION_FAILED",
    "verifying": "INTELLIGENCE_VERIFICATION_FAILED",
    "localizing": "INTELLIGENCE_LOCALIZATION_FAILED",
}


class CompanyIntelligencePipeline:
    def __init__(
        self,
        session: Session,
        sec_provider: SecDataProvider,
        generator: IntelligenceGenerator,
        *,
        schema_version: str,
        prompt_version: str,
        max_filing_bytes: int = 15 * 1024 * 1024,
    ) -> None:
        self._session = session
        self._sec = sec_provider
        self._generator = generator
        self._schema_version = schema_version
        self._prompt_version = prompt_version
        self._max_filing_bytes = max_filing_bytes

    async def download(self, job_id: UUID) -> None:
        async def operation(job: IngestionJob) -> None:
            company = self._company(job)
            await download_latest_10k(
                self._session,
                company,
                self._sec,
                max_bytes=self._max_filing_bytes,
            )

        await self._run(job_id, "queued", "downloading", operation)

    async def parse(self, job_id: UUID) -> None:
        async def operation(job: IngestionJob) -> None:
            filing = self._latest_filing(job)
            section = self._session.exec(
                select(FilingSection).where(FilingSection.filing_id == filing.id)
            ).first()
            if section is None:
                raise DomainError("FILING_PARSE_FAILED", 422)

        await self._run(job_id, "downloading", "parsing", operation)

    async def analyze(self, job_id: UUID) -> None:
        async def operation(job: IngestionJob) -> None:
            company = self._company(job)
            filing = self._latest_filing(job)
            snapshot = await generate_draft(
                self._session,
                company,
                filing,
                self._generator,
                schema_version=self._schema_version,
                prompt_version=self._prompt_version,
            )
            job = self._lock_job(job.id)
            job.snapshot_id = snapshot.id
            self._session.add(job)
            self._session.commit()

        await self._run(job_id, "parsing", "analyzing", operation)

    async def verify(self, job_id: UUID) -> None:
        async def operation(job: IngestionJob) -> None:
            snapshot = self._snapshot(job)
            await verify_snapshot(self._session, snapshot, self._generator)

        await self._run(job_id, "analyzing", "verifying", operation)

    async def localize(self, job_id: UUID) -> None:
        async def operation(job: IngestionJob) -> None:
            snapshot = self._snapshot(job)
            await localize_snapshot(self._session, snapshot, self._generator)

        ran = await self._run(
            job_id,
            "verifying",
            "localizing",
            operation,
        )
        if ran:
            self._advance(job_id, "localizing", "completed")

    async def _run(
        self,
        job_id: UUID,
        expected: str,
        target: str,
        operation: Callable[[IngestionJob], Awaitable[None]],
    ) -> bool:
        job = self._lock_job(job_id)
        if has_reached(job.state, target):
            return False
        if job.state != expected:
            raise DomainError("JOB_STATE_CONFLICT", 409)
        try:
            await operation(job)
        except Exception as error:
            self._fail(job_id, target, error)
            raise PipelineStepError(
                self._error_code(target, error),
                retryable=self._retryable(error),
            ) from error
        self._advance(job_id, expected, target)
        return True

    def _advance(self, job_id: UUID, expected: str, target: str) -> None:
        job = self._lock_job(job_id)
        if has_reached(job.state, target):
            return
        job.state = next_state(expected, target)
        job.current_step = target
        job.error_code = None
        self._session.add(job)
        self._session.commit()

    def _fail(self, job_id: UUID, step: str, error: Exception) -> None:
        self._session.rollback()
        job = self._lock_job(job_id)
        job.state = "failed"
        job.current_step = step
        job.error_code = self._error_code(step, error)
        job.retry_eligible = self._retryable(error)
        self._session.add(job)
        self._session.commit()

    def _lock_job(self, job_id: UUID) -> IngestionJob:
        job = self._session.exec(
            select(IngestionJob)
            .where(IngestionJob.id == job_id)
            .with_for_update()
        ).first()
        if job is None:
            raise DomainError("JOB_NOT_FOUND", 404)
        return job

    def _company(self, job: IngestionJob) -> Company:
        company = self._session.get(Company, job.company_id)
        if company is None:
            raise DomainError("COMPANY_NOT_FOUND", 404)
        return company

    def _latest_filing(self, job: IngestionJob) -> Filing:
        filing = self._session.exec(
            select(Filing)
            .where(Filing.company_id == job.company_id)
            .order_by(Filing.filed_at.desc())
        ).first()
        if filing is None:
            raise DomainError("FILING_NOT_FOUND", 404)
        return filing

    def _snapshot(self, job: IngestionJob) -> CompanyIntelligenceSnapshot:
        snapshot = self._session.get(
            CompanyIntelligenceSnapshot,
            job.snapshot_id,
        )
        if snapshot is None:
            raise DomainError("INTELLIGENCE_SNAPSHOT_NOT_FOUND", 404)
        return snapshot

    @staticmethod
    def _error_code(step: str, error: Exception) -> str:
        if isinstance(error, DomainError):
            return error.code
        return ERROR_CODES[step]

    @staticmethod
    def _retryable(error: Exception) -> bool:
        if isinstance(error, DomainError):
            return bool((error.details or {}).get("retryable", False))
        return True
