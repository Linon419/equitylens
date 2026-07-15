import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.errors import DomainError
from app.jobs._filing_index import (
    FilingIndexSynchronizationServices,
    filing_index_deduplication_key,
    synchronize_filing_index,
)
from app.jobs._graph_sync import (
    GraphSynchronizationServices,
    graph_deduplication_key,
    synchronize_supply_chain_graph,
)
from app.jobs.errors import JobDispatchError
from app.jobs.schemas import JobBackend, JobPublic, SyncResponse
from app.jobs.state import prior_state
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.research_model import CompanyIntelligenceSnapshot, Filing
from app.quota.identity import RequestPrincipal
from app.quota.repository import QuotaRepository
from app.quota.service import (
    get_quota,
    refund_job_analysis,
    rereserve_job_analysis,
    reserve_analysis,
)

__all__ = [
    "GraphSynchronizationServices",
    "FilingIndexSynchronizationServices",
    "SynchronizationServices",
    "graph_deduplication_key",
    "filing_index_deduplication_key",
    "retry_job",
    "synchronize_company",
    "synchronize_filing_index",
    "synchronize_supply_chain_graph",
]


@dataclass(frozen=True)
class SynchronizationServices:
    quota_repository: QuotaRepository
    job_backend: JobBackend
    schema_version: str
    prompt_version: str
    model_id: str
    now: datetime | None = None
    guest_limit: int = 2
    user_limit: int = 10
    ip_limit: int = 10
    after_quota_reserved: Callable[[], None] | None = None


class UnconfiguredJobBackend:
    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict,
    ):
        raise JobDispatchError("job backend is pending configuration", retryable=True)


async def synchronize_company(
    session: Session,
    company: Company,
    principal: RequestPrincipal,
    accession_number: str,
    services: SynchronizationServices,
) -> SyncResponse:
    now = _as_utc(services.now or datetime.now(UTC))
    usage_date = now.date()
    key = deduplication_key(
        company.id,
        accession_number,
        services.schema_version,
        services.prompt_version,
        services.model_id,
    )
    quota = get_quota(
        services.quota_repository,
        principal,
        usage_date,
        guest_limit=services.guest_limit,
        user_limit=services.user_limit,
    )
    snapshot = _reusable_snapshot(
        session,
        company,
        accession_number,
        services,
    )
    if snapshot is not None:
        return SyncResponse(
            status="reused_snapshot",
            snapshot_id=snapshot.id,
            quota=quota,
        )
    existing = _job_by_key(session, key)
    if existing is not None:
        return SyncResponse(
            status="active_job",
            job=JobPublic.from_job(existing, company.symbol),
            quota=quota,
        )

    try:
        quota = reserve_analysis(
            services.quota_repository,
            principal,
            usage_date=usage_date,
            guest_limit=services.guest_limit,
            user_limit=services.user_limit,
            ip_limit=services.ip_limit,
        )
        if services.after_quota_reserved is not None:
            services.after_quota_reserved()
        job = IngestionJob(
            company_id=company.id,
            requested_by_type=principal.principal_type,
            requested_by_hash=principal.principal_hash,
            deduplication_key=key,
            state="queued",
            current_step="queued",
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _job_by_key(session, key)
        if existing is None:
            raise
        return SyncResponse(
            status="active_job",
            job=JobPublic.from_job(existing, company.symbol),
            quota=get_quota(
                services.quota_repository,
                principal,
                usage_date,
                guest_limit=services.guest_limit,
                user_limit=services.user_limit,
            ),
        )
    except Exception:
        session.rollback()
        raise

    session.refresh(job)
    await _dispatch(session, job, services.job_backend, now)
    return SyncResponse(
        status="accepted",
        job=JobPublic.from_job(job, company.symbol),
        quota=quota,
    )


def get_requester_job(
    session: Session,
    job_id: UUID,
    principal: RequestPrincipal,
) -> IngestionJob:
    job = session.exec(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.requested_by_type == principal.principal_type,
            IngestionJob.requested_by_hash == principal.principal_hash,
        )
    ).first()
    if job is None:
        raise DomainError("JOB_NOT_FOUND", 404)
    return job


async def retry_job(
    session: Session,
    job_id: UUID,
    principal: RequestPrincipal,
    backend: JobBackend,
    *,
    quota_repository: QuotaRepository | None = None,
    now: datetime | None = None,
) -> IngestionJob:
    job = get_requester_job(session, job_id, principal)
    if not job.retry_eligible or (
        job.state != "failed" and job.error_code != "JOB_DISPATCH_FAILED"
    ):
        raise DomainError("JOB_RETRY_UNAVAILABLE", 409)
    current_time = _as_utc(now or datetime.now(UTC))
    if job.job_type == "supply_chain_graph":
        if quota_repository is None:
            raise DomainError("GRAPH_QUOTA_REPOSITORY_MISSING", 500)
        rereserved = rereserve_job_analysis(
            quota_repository,
            job.id,
            now=current_time,
        )
        if not rereserved:
            raise DomainError("JOB_RETRY_UNAVAILABLE", 409)
    if job.state == "failed":
        resume_state = prior_state(job.job_type, job.current_step)
        job.state = resume_state
        job.current_step = resume_state
    job.attempt_count += 1
    job.error_code = None
    job.provider_run_id = None
    job.updated_at = current_time
    session.add(job)
    session.commit()
    session.refresh(job)
    await _dispatch(session, job, backend, current_time)
    if (
        job.job_type == "supply_chain_graph"
        and job.error_code == "JOB_DISPATCH_FAILED"
        and quota_repository is not None
    ):
        job.state = "failed"
        refund_job_analysis(quota_repository, job.id, now=current_time)
        session.add(job)
        session.commit()
        session.refresh(job)
    return job


def deduplication_key(
    company_id: int | None,
    accession_number: str,
    schema_version: str,
    prompt_version: str,
    model_id: str,
) -> str:
    components = "|".join(
        (
            str(company_id),
            accession_number,
            schema_version,
            prompt_version,
            model_id,
        )
    )
    digest = hashlib.sha256(components.encode()).hexdigest()
    return f"company-intelligence:{digest}"


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


def _reusable_snapshot(
    session: Session,
    company: Company,
    accession_number: str,
    services: SynchronizationServices,
) -> CompanyIntelligenceSnapshot | None:
    return session.exec(
        select(CompanyIntelligenceSnapshot)
        .join(Filing, Filing.id == CompanyIntelligenceSnapshot.filing_id)
        .where(
            CompanyIntelligenceSnapshot.company_id == company.id,
            Filing.accession_number == accession_number,
            CompanyIntelligenceSnapshot.status == "completed",
            CompanyIntelligenceSnapshot.schema_version == services.schema_version,
            CompanyIntelligenceSnapshot.prompt_version == services.prompt_version,
            CompanyIntelligenceSnapshot.model_id == services.model_id,
        )
        .order_by(CompanyIntelligenceSnapshot.generated_at.desc())
    ).first()


def _job_by_key(session: Session, key: str) -> IngestionJob | None:
    return session.exec(
        select(IngestionJob).where(IngestionJob.deduplication_key == key)
    ).first()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
