import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

import httpx
from rq import Retry
from sqlmodel import Session, create_engine, select

from app.chat.indexing import FilingIndexService, LangChainEmbeddingProvider
from app.core.ai_clients import create_chat_model, create_embedding_model
from app.core.config import settings
from app.filings.sec_client import SecClient
from app.jobs._filing_index import FilingIndexJobPipeline
from app.jobs.errors import PipelineStepError
from app.jobs.pipeline import CompanyIntelligencePipeline
from app.jobs.state import prior_state
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.quota.repository import (
    PostgresQuotaRepository,
    QuotaRepository,
    SQLiteQuotaRepository,
)
from app.quota.service import rereserve_job_analysis
from app.research.openai_generator import OpenAIIntelligenceGenerator
from app.supply_chain.artifacts import (
    S3GraphArtifactStore,
    VercelBlobGraphArtifactStore,
)
from app.supply_chain.collector import (
    OfficialSourceCollectorImpl,
    SourceCollectionError,
    extract_pdf_text,
)
from app.supply_chain.contracts import GraphArtifactStore
from app.supply_chain.entity_resolver import (
    CompanyDirectoryEntry,
    DeterministicEntityResolver,
)
from app.supply_chain.openai_agent import OpenAISupplyChainAgent, SupplyChainAgentError
from app.supply_chain.pipeline import (
    SupplyChainGraphPipeline,
    SupplyChainPipelineServices,
)
from app.supply_chain.repository import (
    GraphPublicationError,
    SqlSupplyChainGraphRepository,
)
from app.supply_chain.source_policy import PinnedDnsTransport, PinningHostResolver
from app.supply_chain.validator import validate_for_publication

engine = create_engine(settings.SYNC_DATABASE_URI)


def run_company_intelligence(job_id: str) -> Retry | None:
    try:
        asyncio.run(_run_pipeline(UUID(job_id)))
    except PipelineStepError as error:
        if error.retryable:
            return _bounded_retry()
    return None


def run_supply_chain_graph(job_id: str) -> Retry | None:
    try:
        asyncio.run(_run_graph_pipeline(UUID(job_id)))
    except (SourceCollectionError, SupplyChainAgentError) as error:
        if error.retryable:
            return _bounded_retry()
    except GraphPublicationError:
        return _bounded_retry()
    return None


def run_filing_index(job_id: str) -> Retry | None:
    try:
        asyncio.run(_run_filing_index_pipeline(UUID(job_id)))
    except PipelineStepError as error:
        if error.retryable:
            return _bounded_retry()
    return None


async def _run_pipeline(job_id: UUID) -> None:
    async with pipeline_context(job_id) as pipeline:
        await pipeline.download(job_id)
        await pipeline.parse(job_id)
        await pipeline.index(job_id)
        await pipeline.analyze(job_id)
        await pipeline.verify(job_id)
        await pipeline.localize(job_id)


async def _run_graph_pipeline(job_id: UUID) -> None:
    async with graph_pipeline_context(job_id) as pipeline:
        await pipeline.run(job_id)


async def _run_filing_index_pipeline(job_id: UUID) -> None:
    async with filing_index_pipeline_context(job_id) as pipeline:
        await pipeline.run(job_id)


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
            model = create_chat_model(model=settings.RESEARCH_MODEL)
            generator = OpenAIIntelligenceGenerator(
                model,
                settings.RESEARCH_MODEL,
                structured_output_method=(
                    settings.LLM_STRUCTURED_OUTPUT_METHOD.value
                ),
            )
            yield CompanyIntelligencePipeline(
                session,
                sec,
                generator,
                schema_version=settings.RESEARCH_SCHEMA_VERSION,
                prompt_version=settings.RESEARCH_PROMPT_VERSION,
                max_filing_bytes=settings.MAX_FILING_BYTES,
                indexer=_filing_indexer(session),
            )


@asynccontextmanager
async def filing_index_pipeline_context(
    job_id: UUID,
) -> AsyncIterator[FilingIndexJobPipeline]:
    with Session(engine) as session:
        _prepare_retry(session, job_id)
        yield FilingIndexJobPipeline(session, _filing_indexer(session))


@asynccontextmanager
async def graph_pipeline_context(
    job_id: UUID,
) -> AsyncIterator[SupplyChainGraphPipeline]:
    with Session(engine) as session:
        quota = _quota_repository(session)
        _prepare_retry(session, job_id, quota_repository=quota)
        resolver = PinningHostResolver()
        async with (
            httpx.AsyncClient(timeout=30, follow_redirects=False) as sec_client,
            httpx.AsyncClient(
                timeout=30,
                follow_redirects=False,
                transport=PinnedDnsTransport(resolver),
            ) as source_client,
        ):
            sec = SecClient(
                sec_client,
                settings.SEC_USER_AGENT,
                max_filing_bytes=settings.MAX_FILING_BYTES,
            )
            collector = OfficialSourceCollectorImpl(
                sec_provider=sec,
                client=source_client,
                artifact_store=_graph_artifact_store(),
                resolver=resolver,
                user_agent=settings.SEC_USER_AGENT,
                source_limit=settings.SUPPLY_CHAIN_GRAPH_SOURCE_LIMIT,
                per_source_bytes=min(
                    settings.MAX_FILING_BYTES,
                    settings.SUPPLY_CHAIN_GRAPH_SOURCE_BYTES,
                ),
                total_source_bytes=settings.SUPPLY_CHAIN_GRAPH_SOURCE_BYTES,
                min_host_interval=0.1,
                pdf_text_extractor=extract_pdf_text,
            )
            model_id = settings.SUPPLY_CHAIN_GRAPH_MODEL
            agent = OpenAISupplyChainAgent(
                model=create_chat_model(
                    model=model_id,
                    temperature=0,
                    timeout=settings.SUPPLY_CHAIN_GRAPH_STAGE_TIMEOUT_SECONDS,
                    max_tokens=settings.SUPPLY_CHAIN_GRAPH_MAX_OUTPUT_TOKENS,
                    max_retries=0,
                ),
                model_id=model_id,
                schema_version=settings.SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION,
                prompt_version=settings.SUPPLY_CHAIN_GRAPH_PROMPT_VERSION,
                stage_timeout_seconds=(
                    settings.SUPPLY_CHAIN_GRAPH_STAGE_TIMEOUT_SECONDS
                ),
                max_source_tokens=(
                    settings.SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET
                ),
                structured_output_method=(
                    settings.LLM_STRUCTURED_OUTPUT_METHOD.value
                ),
            )
            yield SupplyChainGraphPipeline(
                SupplyChainPipelineServices(
                    session=session,
                    collector=collector,
                    agent=agent,
                    resolver=_entity_resolver(session),
                    repository=SqlSupplyChainGraphRepository(session),
                    quota_repository=quota,
                    validator=validate_for_publication,
                    schema_version=settings.SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION,
                    prompt_version=settings.SUPPLY_CHAIN_GRAPH_PROMPT_VERSION,
                    model_id=model_id,
                    min_nodes=settings.SUPPLY_CHAIN_GRAPH_MIN_NODES,
                    max_nodes=settings.SUPPLY_CHAIN_GRAPH_MAX_NODES,
                    evidence_threshold=(
                        settings.SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD
                    ),
                )
            )


def _prepare_retry(
    session: Session,
    job_id: UUID,
    *,
    quota_repository=None,
) -> None:
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
    if job.job_type == "supply_chain_graph" and (
        quota_repository is None
        or not rereserve_job_analysis(
            quota_repository,
            job.id,
            now=datetime.now(UTC),
        )
    ):
        raise PipelineStepError(
            "GRAPH_QUOTA_RERESERVATION_FAILED",
            retryable=False,
        )
    job.state = prior_state(job.job_type, job.current_step)
    job.current_step = job.state
    job.attempt_count += 1
    job.error_code = None
    session.add(job)
    session.commit()


def _quota_repository(session: Session) -> QuotaRepository:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        return PostgresQuotaRepository(session)
    return SQLiteQuotaRepository(session)


def _entity_resolver(session: Session) -> DeterministicEntityResolver:
    companies = session.exec(select(Company).order_by(Company.id)).all()
    return DeterministicEntityResolver(
        tuple(
            CompanyDirectoryEntry(
                company_id=company.id,
                symbol=company.symbol,
                cik=company.cik,
                legal_name=company.name,
            )
            for company in companies
            if company.id is not None
        )
    )


def _filing_indexer(session: Session) -> FilingIndexService:
    model = create_embedding_model(
        model=settings.CHAT_EMBEDDING_MODEL,
        dimensions=settings.CHAT_EMBEDDING_DIMENSIONS,
    )
    provider = LangChainEmbeddingProvider(
        model,
        model_id=settings.CHAT_EMBEDDING_MODEL,
        dimensions=settings.CHAT_EMBEDDING_DIMENSIONS,
    )
    return FilingIndexService(
        session,
        provider,
        chunk_schema_version=settings.CHAT_INDEX_SCHEMA_VERSION,
        target_tokens=settings.CHAT_CHUNK_TARGET_TOKENS,
        overlap_tokens=settings.CHAT_CHUNK_OVERLAP_TOKENS,
        minimum_final_tokens=settings.CHAT_CHUNK_MIN_FINAL_TOKENS,
    )


def _graph_artifact_store() -> GraphArtifactStore:
    if settings.OBJECT_STORAGE_PROVIDER.value == "s3":
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name="us-east-1",
        )
        assert settings.S3_BUCKET is not None
        return S3GraphArtifactStore(
            client=client,
            bucket=settings.S3_BUCKET,
            prefix=settings.GRAPH_ARTIFACT_PREFIX,
        )
    from vercel.blob import AsyncBlobClient

    assert settings.BLOB_READ_WRITE_TOKEN is not None
    return VercelBlobGraphArtifactStore(
        client=AsyncBlobClient(token=settings.BLOB_READ_WRITE_TOKEN),
        prefix=settings.GRAPH_ARTIFACT_PREFIX,
    )


def _bounded_retry() -> Retry:
    return Retry(max=3, interval=[30, 120, 300])
