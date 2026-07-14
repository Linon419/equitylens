import hmac
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Response, status

from app.api.deps import CompanyIntelligencePipelineDep, SessionDep
from app.core.config import settings
from app.core.errors import DomainError
from app.jobs.state import has_reached
from app.models.job_model import IngestionJob

router = APIRouter(prefix="/internal/jobs")
Step = Literal["download", "parse", "analyze", "verify", "localize"]
TARGET_STATE = {
    "download": "downloading",
    "parse": "parsing",
    "analyze": "analyzing",
    "verify": "verifying",
    "localize": "completed",
}


async def _execute_step(
    job_id: UUID,
    step: Step,
    session: SessionDep,
    pipeline: CompanyIntelligencePipelineDep,
    authorization: str | None,
    idempotency_key: str | None,
) -> Response:
    _authorize(authorization)
    if idempotency_key != f"{job_id}:{step}:v1":
        raise DomainError("INTERNAL_JOB_IDEMPOTENCY_INVALID", 400)
    job = session.get(IngestionJob, job_id)
    if job is None:
        raise DomainError("JOB_NOT_FOUND", 404)
    if has_reached(job.job_type, job.state, TARGET_STATE[step]):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    method = getattr(pipeline, step)
    await method(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _authorize(authorization: str | None) -> None:
    prefix = "Bearer "
    if authorization is None or not authorization.startswith(prefix):
        raise DomainError("INTERNAL_JOB_AUTH_REQUIRED", 401)
    supplied = authorization.removeprefix(prefix)
    if not hmac.compare_digest(supplied, settings.INTERNAL_JOB_SECRET):
        raise DomainError("INTERNAL_JOB_AUTH_REQUIRED", 401)


AuthorizationHeader = Annotated[str | None, Header()]
IdempotencyHeader = Annotated[str | None, Header(alias="x-idempotency-key")]


@router.post("/{job_id}/download", status_code=204)
async def download(
    job_id: UUID,
    session: SessionDep,
    pipeline: CompanyIntelligencePipelineDep,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyHeader = None,
) -> Response:
    return await _execute_step(
        job_id, "download", session, pipeline, authorization, idempotency_key
    )


@router.post("/{job_id}/parse", status_code=204)
async def parse(
    job_id: UUID,
    session: SessionDep,
    pipeline: CompanyIntelligencePipelineDep,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyHeader = None,
) -> Response:
    return await _execute_step(
        job_id, "parse", session, pipeline, authorization, idempotency_key
    )


@router.post("/{job_id}/analyze", status_code=204)
async def analyze(
    job_id: UUID,
    session: SessionDep,
    pipeline: CompanyIntelligencePipelineDep,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyHeader = None,
) -> Response:
    return await _execute_step(
        job_id, "analyze", session, pipeline, authorization, idempotency_key
    )


@router.post("/{job_id}/verify", status_code=204)
async def verify(
    job_id: UUID,
    session: SessionDep,
    pipeline: CompanyIntelligencePipelineDep,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyHeader = None,
) -> Response:
    return await _execute_step(
        job_id, "verify", session, pipeline, authorization, idempotency_key
    )


@router.post("/{job_id}/localize", status_code=204)
async def localize(
    job_id: UUID,
    session: SessionDep,
    pipeline: CompanyIntelligencePipelineDep,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyHeader = None,
) -> Response:
    return await _execute_step(
        job_id, "localize", session, pipeline, authorization, idempotency_key
    )
