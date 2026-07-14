import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import httpx
from langchain_openai import ChatOpenAI
from rq import Retry
from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.filings.sec_client import SecClient
from app.jobs.errors import PipelineStepError
from app.jobs.pipeline import CompanyIntelligencePipeline
from app.jobs.state import prior_state
from app.models.job_model import IngestionJob
from app.research.openai_generator import OpenAIIntelligenceGenerator

engine = create_engine(settings.SYNC_DATABASE_URI)
def run_company_intelligence(job_id: str) -> Retry | None:
    try:
        asyncio.run(_run_pipeline(UUID(job_id)))
    except PipelineStepError as error:
        if error.retryable:
            return Retry(max=3, interval=[30, 120, 300])
    return None


async def _run_pipeline(job_id: UUID) -> None:
    async with pipeline_context(job_id) as pipeline:
        await pipeline.download(job_id)
        await pipeline.parse(job_id)
        await pipeline.analyze(job_id)
        await pipeline.verify(job_id)
        await pipeline.localize(job_id)


@asynccontextmanager
async def pipeline_context(
    job_id: UUID,
) -> AsyncIterator[CompanyIntelligencePipeline]:
    with Session(engine) as session:
        _prepare_retry(session, job_id)
        async with httpx.AsyncClient(timeout=30) as client:
            sec = SecClient(
                client,
                settings.SEC_USER_AGENT,
                max_filing_bytes=settings.MAX_FILING_BYTES,
            )
            model = ChatOpenAI(model=settings.RESEARCH_MODEL)
            generator = OpenAIIntelligenceGenerator(
                model,
                settings.RESEARCH_MODEL,
            )
            yield CompanyIntelligencePipeline(
                session,
                sec,
                generator,
                schema_version=settings.RESEARCH_SCHEMA_VERSION,
                prompt_version=settings.RESEARCH_PROMPT_VERSION,
                max_filing_bytes=settings.MAX_FILING_BYTES,
            )


def _prepare_retry(session: Session, job_id: UUID) -> None:
    job = session.exec(
        select(IngestionJob)
        .where(IngestionJob.id == job_id)
        .with_for_update()
    ).first()
    if job is None:
        raise PipelineStepError("JOB_NOT_FOUND", retryable=False)
    if job.state != "failed":
        return
    if not job.retry_eligible:
        raise PipelineStepError(
            job.error_code or "JOB_RETRY_UNAVAILABLE",
            retryable=False,
        )
    job.state = prior_state(job.job_type, job.current_step)
    job.current_step = job.state
    job.attempt_count += 1
    job.error_code = None
    session.add(job)
    session.commit()
