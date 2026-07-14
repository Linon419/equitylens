import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.jobs.errors import JobDispatchError
from app.jobs.schemas import JobBackend, JobPublic
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.supply_chain_model import SupplyChainGraphSnapshot
from app.quota.identity import RequestPrincipal
from app.quota.repository import QuotaRepository
from app.quota.service import (
    get_quota,
    refund_job_analysis,
    reserve_job_analysis,
)
from app.supply_chain.schemas import GraphRefreshResponse

_TERMINAL_JOB_STATES = {"completed", "failed"}
_PUBLIC_GRAPH_STATES = {"completed", "insufficient_evidence"}


@dataclass(frozen=True)
class GraphSynchronizationServices:
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


async def synchronize_supply_chain_graph(
    session: Session,
    *,
    company: Company,
    principal: RequestPrincipal,
    latest_accession: str,
    force_refresh: bool,
    services: GraphSynchronizationServices,
) -> GraphRefreshResponse:
    if company.id is None:
        raise ValueError("persisted company requires an ID")
    now = _as_utc(services.now or datetime.now(UTC))
    quota = _quota(services, principal, now)
    active = _active_job(session, company.id)
    if active is not None:
        return GraphRefreshResponse(
            status="active_job",
            job=JobPublic.from_job(active, company.symbol),
            quota=quota,
        )
    base_key = graph_deduplication_key(
        company.id,
        latest_accession,
        services.schema_version,
        services.prompt_version,
        services.model_id,
    )
    reusable = _reusable_job(session, base_key)
    if reusable is not None and not force_refresh:
        return GraphRefreshResponse(
            status="reused_snapshot",
            snapshot_id=reusable.graph_snapshot_id,
            quota=quota,
        )
    job_id = uuid4()
    key = f"{base_key}:refresh:{job_id}" if force_refresh else base_key
    job = IngestionJob(
        id=job_id,
        job_type="supply_chain_graph",
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
        _, quota = reserve_job_analysis(
            services.quota_repository,
            principal,
            job.id,
            now.date(),
            guest_limit=services.guest_limit,
            user_limit=services.user_limit,
            ip_limit=services.ip_limit,
        )
        if services.after_quota_reserved is not None:
            services.after_quota_reserved()
        session.commit()
        session.refresh(job)
    except IntegrityError:
        session.rollback()
        active = _active_job(session, company.id)
        if active is None:
            raise
        return GraphRefreshResponse(
            status="active_job",
            job=JobPublic.from_job(active, company.symbol),
            quota=_quota(services, principal, now),
        )
    except Exception:
        session.rollback()
        raise

    await _dispatch_graph(session, job, services, now)
    return GraphRefreshResponse(
        status="accepted",
        job=JobPublic.from_job(job, company.symbol),
        quota=_quota(services, principal, now),
    )


def graph_deduplication_key(
    company_id: int,
    latest_accession: str,
    schema_version: str,
    prompt_version: str,
    model_id: str,
) -> str:
    raw = "|".join(
        (
            "supply_chain_graph",
            str(company_id),
            latest_accession,
            schema_version,
            prompt_version,
            model_id,
        )
    )
    return f"supply-chain-graph:{hashlib.sha256(raw.encode()).hexdigest()}"


async def _dispatch_graph(
    session: Session,
    job: IngestionJob,
    services: GraphSynchronizationServices,
    now: datetime,
) -> None:
    try:
        submission = await services.job_backend.enqueue(
            job_type=job.job_type,
            payload={"job_id": str(job.id)},
        )
    except JobDispatchError as error:
        job.state = "failed"
        job.error_code = "JOB_DISPATCH_FAILED"
        job.retry_eligible = error.retryable
        refund_job_analysis(services.quota_repository, job.id, now=now)
    else:
        job.provider_run_id = submission.job_id
        job.error_code = None
    job.updated_at = now
    session.add(job)
    session.commit()
    session.refresh(job)


def _active_job(session: Session, company_id: int) -> IngestionJob | None:
    return session.exec(
        select(IngestionJob)
        .where(
            IngestionJob.company_id == company_id,
            IngestionJob.job_type == "supply_chain_graph",
            IngestionJob.state.not_in(_TERMINAL_JOB_STATES),
        )
        .order_by(IngestionJob.created_at.desc())
    ).first()


def _reusable_job(session: Session, base_key: str) -> IngestionJob | None:
    return session.exec(
        select(IngestionJob)
        .join(
            SupplyChainGraphSnapshot,
            SupplyChainGraphSnapshot.id == IngestionJob.graph_snapshot_id,
        )
        .where(
            IngestionJob.job_type == "supply_chain_graph",
            IngestionJob.state == "completed",
            IngestionJob.deduplication_key.startswith(base_key),
            SupplyChainGraphSnapshot.status.in_(_PUBLIC_GRAPH_STATES),
        )
        .order_by(IngestionJob.updated_at.desc())
    ).first()


def _quota(
    services: GraphSynchronizationServices,
    principal: RequestPrincipal,
    now: datetime,
):
    return get_quota(
        services.quota_repository,
        principal,
        now.date(),
        guest_limit=services.guest_limit,
        user_limit=services.user_limit,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
