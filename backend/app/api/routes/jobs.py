from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import (
    AgentPrincipal,
    JobBackendDep,
    QuotaRepositoryDep,
    SessionDep,
)
from app.core.config import settings
from app.core.errors import DomainError
from app.jobs.schemas import JobPublic
from app.jobs.service import get_requester_job, retry_job
from app.models.company_model import Company
from app.quota.schemas import QuotaStatus
from app.quota.service import get_quota

router = APIRouter()


@router.get("/agent-quota", response_model=QuotaStatus)
def agent_quota(
    principal: AgentPrincipal,
    repository: QuotaRepositoryDep,
) -> QuotaStatus:
    return get_quota(
        repository,
        principal,
        datetime.now(UTC).date(),
        guest_limit=settings.GUEST_DAILY_ANALYSIS_LIMIT,
        user_limit=settings.USER_DAILY_ANALYSIS_LIMIT,
    )


@router.get("/jobs/{job_id}", response_model=JobPublic)
def get_job(
    job_id: UUID,
    session: SessionDep,
    principal: AgentPrincipal,
) -> JobPublic:
    job = get_requester_job(session, job_id, principal)
    company = session.get(Company, job.company_id)
    if company is None:
        raise DomainError("COMPANY_NOT_FOUND", 404)
    return JobPublic.from_job(job, company.symbol)


@router.post("/jobs/{job_id}/retry", response_model=JobPublic)
async def retry_failed_job(
    job_id: UUID,
    session: SessionDep,
    principal: AgentPrincipal,
    backend: JobBackendDep,
) -> JobPublic:
    job = await retry_job(session, job_id, principal, backend)
    company = session.get(Company, job.company_id)
    if company is None:
        raise DomainError("COMPANY_NOT_FOUND", 404)
    return JobPublic.from_job(job, company.symbol)
