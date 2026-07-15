import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.chat.indexing import FilingIndexResult
from app.core.errors import DomainError
from app.jobs.errors import JobDispatchError, PipelineStepError
from app.jobs.schemas import (
    FilingIndexSyncResponse,
    JobBackend,
    JobPublic,
)
from app.jobs.state import has_reached, next_state
from app.models.chat_model import FilingChunk
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.research_model import Filing, FilingSection
from app.quota.identity import RequestPrincipal


class FilingIndexer(Protocol):
    async def index_latest(self, *, company_id: int) -> FilingIndexResult: ...


@dataclass(frozen=True)
class FilingIndexSynchronizationServices:
    job_backend: JobBackend
    schema_version: str
    embedding_model: str
    now: datetime | None = None


async def synchronize_filing_index(
    session: Session,
    *,
    company: Company,
    principal: RequestPrincipal,
    filing: Filing,
    services: FilingIndexSynchronizationServices,
) -> FilingIndexSyncResponse:
    if company.id is None or filing.company_id != company.id:
        raise DomainError("FILING_NOT_FOUND", 404)
    if _complete_index(
        session,
        filing,
        schema_version=services.schema_version,
        embedding_model=services.embedding_model,
    ):
        return FilingIndexSyncResponse(status="ready", filing_id=filing.id)
    key = filing_index_deduplication_key(
        company.id,
        filing.accession_number,
        services.schema_version,
        services.embedding_model,
    )
    existing = session.exec(
        select(IngestionJob).where(IngestionJob.deduplication_key == key)
    ).first()
    if existing is not None:
        return FilingIndexSyncResponse(
            status="active_job",
            job=JobPublic.from_job(existing, company.symbol),
        )
    now = _as_utc(services.now or datetime.now(UTC))
    job = IngestionJob(
        job_type="filing_index",
        company_id=company.id,
        requested_by_type=principal.principal_type,
        requested_by_hash=principal.principal_hash,
        deduplication_key=key,
        state="queued",
        current_step="queued",
        created_at=now,
        updated_at=now,
    )
    try:
        session.add(job)
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(IngestionJob).where(IngestionJob.deduplication_key == key)
        ).one()
        return FilingIndexSyncResponse(
            status="active_job",
            job=JobPublic.from_job(existing, company.symbol),
        )
    session.refresh(job)
    await _dispatch(session, job, services.job_backend, now)
    return FilingIndexSyncResponse(
        status="accepted",
        job=JobPublic.from_job(job, company.symbol),
    )


class FilingIndexJobPipeline:
    def __init__(self, session: Session, indexer: FilingIndexer) -> None:
        self._session = session
        self._indexer = indexer

    async def run(self, job_id: UUID) -> None:
        job = self._lock_job(job_id)
        if has_reached(job.job_type, job.state, "completed"):
            return
        if job.state != "queued":
            raise PipelineStepError("JOB_STATE_CONFLICT", retryable=False)
        self._advance(job_id, "queued", "chunking")
        try:
            job = self._lock_job(job_id)
            await self._indexer.index_latest(company_id=job.company_id)
        except Exception as error:
            self._fail(job_id, error)
            raise PipelineStepError(
                _index_error_code(error),
                retryable=_retryable(error),
            ) from error
        self._advance(job_id, "chunking", "embedding")
        self._advance(job_id, "embedding", "indexing")
        self._advance(job_id, "indexing", "completed")

    def _advance(self, job_id: UUID, expected: str, target: str) -> None:
        job = self._lock_job(job_id)
        if has_reached(job.job_type, job.state, target):
            return
        job.state = next_state(job.job_type, expected, target)
        job.current_step = target
        job.error_code = None
        job.updated_at = datetime.now(UTC)
        self._session.add(job)
        self._session.commit()

    def _fail(self, job_id: UUID, error: Exception) -> None:
        self._session.rollback()
        job = self._lock_job(job_id)
        job.state = "failed"
        job.error_code = _index_error_code(error)
        job.retry_eligible = _retryable(error)
        job.updated_at = datetime.now(UTC)
        self._session.add(job)
        self._session.commit()

    def _lock_job(self, job_id: UUID) -> IngestionJob:
        job = self._session.exec(
            select(IngestionJob)
            .where(IngestionJob.id == job_id)
            .with_for_update()
        ).first()
        if job is None or job.job_type != "filing_index":
            raise PipelineStepError("JOB_NOT_FOUND", retryable=False)
        return job


def filing_index_deduplication_key(
    company_id: int,
    accession_number: str,
    schema_version: str,
    embedding_model: str,
) -> str:
    payload = "|".join(
        (str(company_id), accession_number, schema_version, embedding_model)
    )
    return f"filing-index:{hashlib.sha256(payload.encode()).hexdigest()}"


def _complete_index(
    session: Session,
    filing: Filing,
    *,
    schema_version: str,
    embedding_model: str,
) -> bool:
    section_ids = set(
        session.exec(
            select(FilingSection.id).where(FilingSection.filing_id == filing.id)
        ).all()
    )
    if not section_ids:
        return False
    indexed_ids = set(
        session.exec(
            select(FilingChunk.section_id).where(
                FilingChunk.filing_id == filing.id,
                FilingChunk.chunk_schema_version == schema_version,
                FilingChunk.embedding_model == embedding_model,
            )
        ).all()
    )
    return indexed_ids == section_ids


async def _dispatch(
    session: Session,
    job: IngestionJob,
    backend: JobBackend,
    now: datetime,
) -> None:
    try:
        submission = await backend.enqueue(
            job_type=job.job_type,
            payload={"job_id": str(job.id)},
        )
    except JobDispatchError as error:
        job.error_code = "JOB_DISPATCH_FAILED"
        job.retry_eligible = error.retryable
    else:
        job.provider_run_id = submission.job_id
        job.error_code = None
    job.updated_at = now
    session.add(job)
    session.commit()
    session.refresh(job)


def _index_error_code(error: Exception) -> str:
    if isinstance(error, DomainError):
        return error.code
    if isinstance(error, ValueError):
        return "FILING_INDEX_INVALID_EMBEDDING"
    return "FILING_INDEX_FAILED"


def _retryable(error: Exception) -> bool:
    return not isinstance(error, (DomainError, ValueError))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
