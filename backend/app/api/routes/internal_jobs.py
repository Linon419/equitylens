import hmac
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Response, status

from app.api.deps import (
    CompanyIntelligencePipelineDep,
    SessionDep,
    SupplyChainGraphPipelineDep,
)
from app.core.config import settings
from app.core.errors import DomainError
from app.jobs.state import has_reached
from app.models.job_model import IngestionJob
from app.supply_chain.collector import SourceCollectionError
from app.supply_chain.openai_agent import SupplyChainAgentError
from app.supply_chain.repository import GraphPublicationError

router = APIRouter(prefix="/internal/jobs")
Step = Literal["download", "parse", "index", "analyze", "verify", "localize"]
GraphStep = Literal["collect", "extract", "resolve", "verify", "localize", "publish"]
TARGET_STATE = {
    "download": "downloading",
    "parse": "parsing",
    "index": "indexing",
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


async def _execute_graph_step(
    job_id: UUID,
    step: GraphStep,
    session: SessionDep,
    pipeline: SupplyChainGraphPipelineDep,
    authorization: str | None,
    idempotency_key: str | None,
) -> Response:
    _authorize(authorization)
    expected_key = f"{job_id}:supply-chain-graph:{step}:v1"
    if idempotency_key != expected_key:
        raise DomainError("INTERNAL_JOB_IDEMPOTENCY_INVALID", 400)
    job = session.get(IngestionJob, job_id)
    if job is None:
        raise DomainError("JOB_NOT_FOUND", 404)
    if job.job_type != "supply_chain_graph":
        raise DomainError("JOB_TYPE_CONFLICT", 409)
    if job.state == "failed":
        pipeline.resume_retry(job_id)
    if pipeline.is_step_complete(job_id, step):
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    method = getattr(pipeline, step)
    try:
        await method(job_id)
    except DomainError:
        raise
    except (SourceCollectionError, SupplyChainAgentError) as error:
        raise DomainError(
            error.code,
            503 if error.retryable else 422,
            {"retryable": error.retryable},
        ) from error
    except GraphPublicationError as error:
        raise DomainError(error.code, 503, {"retryable": True}) from error
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


@router.post("/{job_id}/index", status_code=204)
async def index(
    job_id: UUID,
    session: SessionDep,
    pipeline: CompanyIntelligencePipelineDep,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyHeader = None,
) -> Response:
    return await _execute_step(
        job_id, "index", session, pipeline, authorization, idempotency_key
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


@router.post(
    "/{job_id}/supply-chain-graph/{step}",
    status_code=204,
)
async def supply_chain_graph_step(
    job_id: UUID,
    step: GraphStep,
    session: SessionDep,
    pipeline: SupplyChainGraphPipelineDep,
    authorization: AuthorizationHeader = None,
    idempotency_key: IdempotencyHeader = None,
) -> Response:
    return await _execute_graph_step(
        job_id,
        step,
        session,
        pipeline,
        authorization,
        idempotency_key,
    )
