from collections.abc import AsyncIterator, Callable, Generator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from openai import AsyncOpenAI
from sqlmodel import Session, create_engine, select

from app.auth.contracts import GoogleVerifier
from app.auth.errors import AuthError
from app.auth.google import GoogleTokenVerifier
from app.chat.artifacts import (
    ChatArtifactStore,
    S3ChatArtifactStore,
    VercelBlobChatArtifactStore,
    WebArtifactArchive,
)
from app.chat.contracts import StructuredContextProvider
from app.chat.evidence_pipeline import (
    CompanyResearchEvidencePipeline,
    DeterministicConversationSummarizer,
)
from app.chat.indexing import FilingIndexService, LangChainEmbeddingProvider
from app.chat.openai_agent import (
    ChatCompletionsPlanningModel,
    ChatCompletionsRoutingModel,
    CitationBoundAnswerAgent,
    ModelDirectedIntentRouter,
    OpenAIResponsesPlanningModel,
    OpenAIResponsesRoutingModel,
)
from app.chat.quota import ChatQuotaService, SqlChatQuotaRepository
from app.chat.repository import ConversationRepository
from app.chat.retrieval import (
    HybridFilingRetriever,
    OpenAIQueryRewriter,
    SqlFilingChunkRepository,
)
from app.chat.service import CompanyResearchChatService
from app.chat.structured_context import StructuredContextService
from app.chat.structured_repository import SqlStructuredContextRepository
from app.chat.tavily_discovery import TavilyWebSearchProvider
from app.chat.web_discovery import OpenAIWebSearchProvider, SourceClassifier
from app.chat.web_fetcher import PinnedWebPageFetcher
from app.chat.web_search import BoundedWebSearchService
from app.core.ai_clients import (
    create_chat_model,
    create_embedding_model,
    create_responses_client,
)
from app.core.config import settings
from app.core.errors import DomainError
from app.core.security import decode_access_token
from app.filings.sec_client import SecClient
from app.jobs._filing_index import FilingIndexJobPipeline
from app.jobs.pipeline import CompanyIntelligencePipeline
from app.jobs.rq_backend import RQJobBackend
from app.jobs.schemas import JobBackend
from app.jobs.service import (
    GraphSynchronizationServices,
    UnconfiguredJobBackend,
)
from app.jobs.vercel_backend import VercelWorkflowBackend
from app.market_data.yahoo import YahooMarketDataProvider
from app.models.auth_model import AuthSession
from app.models.company_model import Company
from app.models.user_model import User
from app.providers.market import MarketDataProvider
from app.providers.sec import SecDataProvider
from app.quota.identity import RequestPrincipal, principal_from_assertion
from app.quota.repository import (
    PostgresQuotaRepository,
    QuotaRepository,
    SQLiteQuotaRepository,
)
from app.research.openai_generator import OpenAIIntelligenceGenerator
from app.research.service import IntelligenceGenerator
from app.supply_chain.artifacts import (
    S3GraphArtifactStore,
    VercelBlobGraphArtifactStore,
)
from app.supply_chain.collector import OfficialSourceCollectorImpl, extract_pdf_text
from app.supply_chain.contracts import (
    EntityResolver,
    GraphArtifactStore,
    OfficialSourceCollector,
    SupplyChainAgent,
)
from app.supply_chain.entity_resolver import (
    CompanyDirectoryEntry,
    DeterministicEntityResolver,
)
from app.supply_chain.openai_agent import OpenAISupplyChainAgent
from app.supply_chain.pipeline import (
    SupplyChainGraphPipeline,
    SupplyChainPipelineServices,
)
from app.supply_chain.repository import SqlSupplyChainGraphRepository
from app.supply_chain.service import SupplyChainGraphService
from app.supply_chain.source_policy import PinnedDnsTransport, PinningHostResolver
from app.supply_chain.validator import validate_for_publication

engine = create_engine(settings.SYNC_DATABASE_URI)
bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def get_google_verifier() -> GoogleVerifier:
    return GoogleTokenVerifier(settings.GOOGLE_CLIENT_ID)


GoogleVerifierDep = Annotated[GoogleVerifier, Depends(get_google_verifier)]
TokenDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_market_data_provider() -> MarketDataProvider:
    return YahooMarketDataProvider()


async def get_sec_data_provider() -> AsyncIterator[SecDataProvider]:
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        yield SecClient(
            client=client,
            user_agent=settings.SEC_USER_AGENT,
            max_filing_bytes=settings.MAX_FILING_BYTES,
        )


MarketDataProviderDep = Annotated[
    MarketDataProvider,
    Depends(get_market_data_provider),
]
SecDataProviderDep = Annotated[SecDataProvider, Depends(get_sec_data_provider)]


def resolve_user_from_token(session: Session, token: str) -> User:
    try:
        claims = decode_access_token(token)
    except (JWTError, KeyError, TypeError, ValueError) as error:
        raise AuthError("AUTH_REQUIRED", 401) from error

    active_session = session.exec(
        select(AuthSession.id).where(
            AuthSession.token_family_id == claims.session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    ).first()
    user = session.get(User, claims.user_id)
    if active_session is None or user is None:
        raise AuthError("AUTH_REQUIRED", 401)
    if not user.is_active:
        raise AuthError("AUTH_ACCOUNT_DISABLED", 403)
    return user


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    if token is None:
        raise AuthError("AUTH_REQUIRED", 401)
    return resolve_user_from_token(session, token.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_optional_current_user(
    session: SessionDep,
    token: TokenDep,
) -> User | None:
    if token is None:
        return None
    return resolve_user_from_token(session, token.credentials)


OptionalCurrentUser = Annotated[
    User | None,
    Depends(get_optional_current_user),
]


def get_agent_principal(
    request: Request,
    user: OptionalCurrentUser,
) -> RequestPrincipal:
    if user is not None:
        return RequestPrincipal.user(user.id, settings.QUOTA_HASH_SECRET)
    assertion = request.headers.get("x-guest-assertion")
    if assertion is None:
        raise DomainError("GUEST_ASSERTION_REQUIRED", 401)
    try:
        return principal_from_assertion(
            assertion,
            signing_secret=settings.GUEST_SIGNING_SECRET,
            hash_secret=settings.QUOTA_HASH_SECRET,
        )
    except ValueError as error:
        raise DomainError("GUEST_ASSERTION_INVALID", 401) from error


AgentPrincipal = Annotated[
    RequestPrincipal,
    Depends(get_agent_principal),
]


def get_quota_repository(session: SessionDep) -> QuotaRepository:
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        return PostgresQuotaRepository(session)
    return SQLiteQuotaRepository(session)


QuotaRepositoryDep = Annotated[
    QuotaRepository,
    Depends(get_quota_repository),
]


async def get_job_backend() -> AsyncIterator[JobBackend]:
    if settings.JOB_BACKEND.value == "rq":
        from redis import Redis
        from rq import Queue

        if settings.REDIS_URL is None:
            raise RuntimeError("REDIS_URL is required for the RQ backend")
        queue = Queue(
            "company-intelligence",
            connection=Redis.from_url(settings.REDIS_URL),
        )
        yield RQJobBackend(queue)
        return
    if settings.JOB_BACKEND.value == "vercel_workflow":
        if (
            settings.WORKFLOW_TRIGGER_URL is None
            or settings.SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL is None
            or settings.CHAT_INDEX_WORKFLOW_TRIGGER_URL is None
        ):
            raise RuntimeError("Workflow trigger URLs are required")
        async with httpx.AsyncClient(timeout=15) as client:
            yield VercelWorkflowBackend(
                client,
                settings.WORKFLOW_TRIGGER_URL,
                settings.INTERNAL_JOB_SECRET,
                supply_chain_trigger_url=(settings.SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL),
                filing_index_trigger_url=(settings.CHAT_INDEX_WORKFLOW_TRIGGER_URL),
            )
        return
    yield UnconfiguredJobBackend()


JobBackendDep = Annotated[JobBackend, Depends(get_job_backend)]


@lru_cache(maxsize=8)
def _get_s3_graph_client(
    endpoint_url: str,
    access_key_id: str,
    secret_access_key: str,
    region_name: str,
):
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        region_name=region_name,
    )


@lru_cache(maxsize=8)
def _get_vercel_blob_client(token: str):
    from vercel.blob import AsyncBlobClient

    return AsyncBlobClient(token=token)


def get_graph_artifact_store() -> GraphArtifactStore:
    if settings.OBJECT_STORAGE_PROVIDER.value == "s3":
        required = (
            settings.S3_ENDPOINT_URL,
            settings.S3_BUCKET,
            settings.S3_ACCESS_KEY_ID,
            settings.S3_SECRET_ACCESS_KEY,
        )
        if not all(required):
            raise RuntimeError("S3 graph artifact storage is not configured")
        endpoint, bucket, access_key, secret_key = required
        assert endpoint is not None
        assert bucket is not None
        assert access_key is not None
        assert secret_key is not None
        client = _get_s3_graph_client(
            endpoint,
            access_key,
            secret_key,
            "us-east-1",
        )
        return S3GraphArtifactStore(
            client=client,
            bucket=bucket,
            prefix=settings.GRAPH_ARTIFACT_PREFIX,
        )
    if settings.OBJECT_STORAGE_PROVIDER.value == "vercel_blob":
        token = settings.BLOB_READ_WRITE_TOKEN
        if token is None:
            raise RuntimeError("Vercel graph artifact storage is not configured")
        return VercelBlobGraphArtifactStore(
            client=_get_vercel_blob_client(token),
            prefix=settings.GRAPH_ARTIFACT_PREFIX,
        )
    raise RuntimeError("Graph artifact storage provider is unsupported")


GraphArtifactStoreDep = Annotated[
    GraphArtifactStore,
    Depends(get_graph_artifact_store),
]


def get_official_pdf_text_extractor() -> Callable[[bytes], str]:
    return extract_pdf_text


OfficialPdfTextExtractorDep = Annotated[
    Callable[[bytes], str],
    Depends(get_official_pdf_text_extractor),
]


async def get_official_source_collector(
    sec_provider: SecDataProviderDep,
    artifact_store: GraphArtifactStoreDep,
    pdf_text_extractor: OfficialPdfTextExtractorDep,
) -> AsyncIterator[OfficialSourceCollector]:
    resolver = PinningHostResolver()
    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=False,
        transport=PinnedDnsTransport(resolver),
    ) as client:
        yield OfficialSourceCollectorImpl(
            sec_provider=sec_provider,
            client=client,
            artifact_store=artifact_store,
            resolver=resolver,
            user_agent=settings.SEC_USER_AGENT,
            source_limit=settings.SUPPLY_CHAIN_GRAPH_SOURCE_LIMIT,
            per_source_bytes=min(
                settings.MAX_FILING_BYTES,
                settings.SUPPLY_CHAIN_GRAPH_SOURCE_BYTES,
            ),
            total_source_bytes=settings.SUPPLY_CHAIN_GRAPH_SOURCE_BYTES,
            min_host_interval=0.1,
            pdf_text_extractor=pdf_text_extractor,
        )


OfficialSourceCollectorDep = Annotated[
    OfficialSourceCollector,
    Depends(get_official_source_collector),
]


def get_supply_chain_agent() -> SupplyChainAgent:
    model_id = settings.SUPPLY_CHAIN_GRAPH_MODEL
    return OpenAISupplyChainAgent(
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
        stage_timeout_seconds=settings.SUPPLY_CHAIN_GRAPH_STAGE_TIMEOUT_SECONDS,
        max_source_tokens=settings.SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET,
        structured_output_method=settings.LLM_STRUCTURED_OUTPUT_METHOD.value,
    )


SupplyChainAgentDep = Annotated[
    SupplyChainAgent,
    Depends(get_supply_chain_agent),
]


def get_supply_chain_entity_resolver(session: SessionDep) -> EntityResolver:
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


SupplyChainEntityResolverDep = Annotated[
    EntityResolver,
    Depends(get_supply_chain_entity_resolver),
]


def get_supply_chain_graph_pipeline(
    session: SessionDep,
    collector: OfficialSourceCollectorDep,
    agent: SupplyChainAgentDep,
    resolver: SupplyChainEntityResolverDep,
    quota_repository: QuotaRepositoryDep,
) -> SupplyChainGraphPipeline:
    return SupplyChainGraphPipeline(
        SupplyChainPipelineServices(
            session=session,
            collector=collector,
            agent=agent,
            resolver=resolver,
            repository=SqlSupplyChainGraphRepository(session),
            quota_repository=quota_repository,
            validator=validate_for_publication,
            schema_version=settings.SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION,
            prompt_version=settings.SUPPLY_CHAIN_GRAPH_PROMPT_VERSION,
            model_id=settings.SUPPLY_CHAIN_GRAPH_MODEL,
            min_nodes=settings.SUPPLY_CHAIN_GRAPH_MIN_NODES,
            max_nodes=settings.SUPPLY_CHAIN_GRAPH_MAX_NODES,
            evidence_threshold=settings.SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD,
        )
    )


SupplyChainGraphPipelineDep = Annotated[
    SupplyChainGraphPipeline,
    Depends(get_supply_chain_graph_pipeline),
]


def get_supply_chain_graph_service(
    session: SessionDep,
    quota_repository: QuotaRepositoryDep,
) -> SupplyChainGraphService:
    return SupplyChainGraphService(
        session=session,
        repository=SqlSupplyChainGraphRepository(session),
        quota_repository=quota_repository,
        guest_limit=settings.GUEST_DAILY_ANALYSIS_LIMIT,
        user_limit=settings.USER_DAILY_ANALYSIS_LIMIT,
    )


SupplyChainGraphServiceDep = Annotated[
    SupplyChainGraphService,
    Depends(get_supply_chain_graph_service),
]


def get_graph_synchronization_services(
    quota_repository: QuotaRepositoryDep,
    backend: JobBackendDep,
) -> GraphSynchronizationServices:
    return GraphSynchronizationServices(
        quota_repository=quota_repository,
        job_backend=backend,
        schema_version=settings.SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION,
        prompt_version=settings.SUPPLY_CHAIN_GRAPH_PROMPT_VERSION,
        model_id=settings.SUPPLY_CHAIN_GRAPH_MODEL,
        guest_limit=settings.GUEST_DAILY_ANALYSIS_LIMIT,
        user_limit=settings.USER_DAILY_ANALYSIS_LIMIT,
        ip_limit=settings.IP_DAILY_ANALYSIS_LIMIT,
    )


GraphSynchronizationServicesDep = Annotated[
    GraphSynchronizationServices,
    Depends(get_graph_synchronization_services),
]


def get_intelligence_generator() -> IntelligenceGenerator:
    return OpenAIIntelligenceGenerator(
        create_chat_model(model=settings.RESEARCH_MODEL),
        settings.RESEARCH_MODEL,
        structured_output_method=settings.LLM_STRUCTURED_OUTPUT_METHOD.value,
    )


IntelligenceGeneratorDep = Annotated[
    IntelligenceGenerator,
    Depends(get_intelligence_generator),
]


def get_chat_embedding_provider() -> LangChainEmbeddingProvider:
    return LangChainEmbeddingProvider(
        create_embedding_model(
            model=settings.CHAT_EMBEDDING_MODEL,
            dimensions=settings.CHAT_EMBEDDING_DIMENSIONS,
        ),
        model_id=settings.CHAT_EMBEDDING_MODEL,
        dimensions=settings.CHAT_EMBEDDING_DIMENSIONS,
    )


ChatEmbeddingProviderDep = Annotated[
    LangChainEmbeddingProvider,
    Depends(get_chat_embedding_provider),
]


def get_filing_index_service(
    session: SessionDep,
    embeddings: ChatEmbeddingProviderDep,
) -> FilingIndexService:
    return FilingIndexService(
        session,
        embeddings,
        chunk_schema_version=settings.CHAT_INDEX_SCHEMA_VERSION,
        target_tokens=settings.CHAT_CHUNK_TARGET_TOKENS,
        overlap_tokens=settings.CHAT_CHUNK_OVERLAP_TOKENS,
        minimum_final_tokens=settings.CHAT_CHUNK_MIN_FINAL_TOKENS,
    )


FilingIndexServiceDep = Annotated[
    FilingIndexService,
    Depends(get_filing_index_service),
]


def get_filing_index_pipeline(
    session: SessionDep,
    indexer: FilingIndexServiceDep,
) -> FilingIndexJobPipeline:
    return FilingIndexJobPipeline(session, indexer)


FilingIndexJobPipelineDep = Annotated[
    FilingIndexJobPipeline,
    Depends(get_filing_index_pipeline),
]


def get_company_intelligence_pipeline(
    session: SessionDep,
    sec_provider: SecDataProviderDep,
    generator: IntelligenceGeneratorDep,
    indexer: FilingIndexServiceDep,
) -> CompanyIntelligencePipeline:
    return CompanyIntelligencePipeline(
        session,
        sec_provider,
        generator,
        schema_version=settings.RESEARCH_SCHEMA_VERSION,
        prompt_version=settings.RESEARCH_PROMPT_VERSION,
        max_filing_bytes=settings.MAX_FILING_BYTES,
        indexer=indexer,
    )


CompanyIntelligencePipelineDep = Annotated[
    CompanyIntelligencePipeline,
    Depends(get_company_intelligence_pipeline),
]


def get_chat_repository(session: SessionDep) -> ConversationRepository:
    return ConversationRepository(session)


ChatRepositoryDep = Annotated[
    ConversationRepository,
    Depends(get_chat_repository),
]


def get_chat_quota_service(session: SessionDep) -> ChatQuotaService:
    return ChatQuotaService(
        SqlChatQuotaRepository(session),
        guest_limit=settings.CHAT_GUEST_DAILY_LIMIT,
        user_limit=settings.CHAT_USER_DAILY_LIMIT,
    )


ChatQuotaServiceDep = Annotated[
    ChatQuotaService,
    Depends(get_chat_quota_service),
]


def get_chat_context_provider(session: SessionDep) -> StructuredContextProvider:
    return StructuredContextService(session)


ChatContextProviderDep = Annotated[
    StructuredContextProvider,
    Depends(get_chat_context_provider),
]


async def get_chat_openai_client() -> AsyncIterator[AsyncOpenAI | None]:
    if settings.LLM_API_KEY is not None or settings.LLM_BASE_URL is not None:
        yield None
        return
    client = create_responses_client()
    try:
        yield client
    finally:
        await client.close()


ChatOpenAIClientDep = Annotated[
    AsyncOpenAI | None,
    Depends(get_chat_openai_client),
]


def get_chat_retriever(
    session: SessionDep,
    embeddings: ChatEmbeddingProviderDep,
) -> HybridFilingRetriever:
    rewriter = OpenAIQueryRewriter(
        create_chat_model(
            model=settings.CHAT_MODEL,
            temperature=0,
            timeout=60,
            max_retries=0,
        ),
        structured_output_method=settings.LLM_STRUCTURED_OUTPUT_METHOD.value,
    )
    return HybridFilingRetriever(
        SqlFilingChunkRepository(
            session,
            embedding_dimensions=settings.CHAT_EMBEDDING_DIMENSIONS,
        ),
        embeddings,
        rewriter,
        candidate_limit=settings.CHAT_RETRIEVAL_CANDIDATES,
        max_chunks=settings.CHAT_RETRIEVAL_MAX_CHUNKS,
        max_per_section=settings.CHAT_RETRIEVAL_MAX_PER_SECTION,
        token_budget=settings.CHAT_RETRIEVAL_TOKEN_BUDGET,
        rrf_k=settings.CHAT_RRF_K,
    )


ChatRetrieverDep = Annotated[
    HybridFilingRetriever,
    Depends(get_chat_retriever),
]


def get_chat_artifact_store() -> ChatArtifactStore:
    prefix = settings.CHAT_WEB_ARTIFACT_PREFIX
    if settings.OBJECT_STORAGE_PROVIDER.value == "s3":
        required = (
            settings.S3_ENDPOINT_URL,
            settings.S3_BUCKET,
            settings.S3_ACCESS_KEY_ID,
            settings.S3_SECRET_ACCESS_KEY,
        )
        if not all(required):
            raise RuntimeError("S3 chat artifact storage is not configured")
        endpoint, bucket, access_key, secret_key = required
        assert endpoint and bucket and access_key and secret_key
        return S3ChatArtifactStore(
            _get_s3_graph_client(
                endpoint,
                access_key,
                secret_key,
                "us-east-1",
            ),
            bucket=bucket,
            prefix=prefix,
        )
    token = settings.BLOB_READ_WRITE_TOKEN
    if settings.OBJECT_STORAGE_PROVIDER.value == "vercel_blob" and token:
        return VercelBlobChatArtifactStore(
            _get_vercel_blob_client(token),
            prefix=prefix,
        )
    raise RuntimeError("Chat artifact storage provider is unsupported")


ChatArtifactStoreDep = Annotated[
    ChatArtifactStore,
    Depends(get_chat_artifact_store),
]


async def get_chat_web_search_service(
    store: ChatArtifactStoreDep,
) -> AsyncIterator[BoundedWebSearchService]:
    fetcher = PinnedWebPageFetcher.create(
        user_agent=settings.SEC_USER_AGENT,
        max_bytes=min(settings.MAX_FILING_BYTES, 1_500_000),
        max_model_chars=40_000,
        min_host_interval=0.25,
    )
    provider_client: httpx.AsyncClient | AsyncOpenAI | None = None
    try:
        if settings.CHAT_WEB_SEARCH_PROVIDER.value == "tavily":
            provider_client = httpx.AsyncClient(timeout=30)
            provider = TavilyWebSearchProvider(
                create_chat_model(
                    model=settings.CHAT_MODEL,
                    temperature=0,
                    timeout=60,
                    max_retries=0,
                ),
                provider_client,
                api_key=settings.TAVILY_API_KEY,
                model_id=settings.CHAT_MODEL,
                max_queries=settings.CHAT_WEB_MAX_QUERIES,
                max_results=settings.CHAT_TAVILY_MAX_RESULTS,
                search_depth=settings.CHAT_TAVILY_SEARCH_DEPTH.value,
                structured_output_method=(settings.LLM_STRUCTURED_OUTPUT_METHOD.value),
            )
        else:
            provider_client = create_responses_client()
            provider = OpenAIWebSearchProvider(
                provider_client,
                model_id=settings.CHAT_MODEL,
                max_queries=settings.CHAT_WEB_MAX_QUERIES,
            )
        yield BoundedWebSearchService(
            provider,
            fetcher,
            WebArtifactArchive(
                store,
                prefix=settings.CHAT_WEB_ARTIFACT_PREFIX,
            ),
            classifier=SourceClassifier(
                trusted_secondary_hosts=(
                    "reuters.com",
                    "ft.com",
                    "wsj.com",
                    "bloomberg.com",
                    "finance.yahoo.com",
                )
            ),
            max_queries=settings.CHAT_WEB_MAX_QUERIES,
            max_pages=settings.CHAT_WEB_MAX_PAGES,
        )
    finally:
        await fetcher.aclose()
        if isinstance(provider_client, httpx.AsyncClient):
            await provider_client.aclose()
        elif provider_client is not None:
            await provider_client.close()


ChatWebSearchServiceDep = Annotated[
    BoundedWebSearchService,
    Depends(get_chat_web_search_service),
]


def get_chat_evidence_pipeline(
    session: SessionDep,
    retriever: ChatRetrieverDep,
    web_search: ChatWebSearchServiceDep,
) -> CompanyResearchEvidencePipeline:
    return CompanyResearchEvidencePipeline(
        SqlStructuredContextRepository(session),
        retriever,
        web_search,
    )


ChatEvidencePipelineDep = Annotated[
    CompanyResearchEvidencePipeline,
    Depends(get_chat_evidence_pipeline),
]


def get_chat_answer_agent(
    client: ChatOpenAIClientDep,
) -> CitationBoundAnswerAgent:
    if settings.LLM_API_KEY is not None or settings.LLM_BASE_URL is not None:
        return CitationBoundAnswerAgent(
            ChatCompletionsPlanningModel(
                create_chat_model(
                    model=settings.CHAT_MODEL,
                    temperature=0,
                    timeout=55,
                    max_tokens=4_000,
                    max_retries=0,
                ),
                model_id=settings.CHAT_MODEL,
                structured_output_method=(settings.LLM_STRUCTURED_OUTPUT_METHOD.value),
            )
        )
    if client is None:
        raise RuntimeError("OpenAI Responses client is unavailable")
    return CitationBoundAnswerAgent(
        OpenAIResponsesPlanningModel(
            client,
            model_id=settings.CHAT_MODEL,
        )
    )


ChatAnswerAgentDep = Annotated[
    CitationBoundAnswerAgent,
    Depends(get_chat_answer_agent),
]


def get_chat_intent_router(
    client: ChatOpenAIClientDep,
) -> ModelDirectedIntentRouter:
    if settings.LLM_API_KEY is not None or settings.LLM_BASE_URL is not None:
        return ModelDirectedIntentRouter(
            ChatCompletionsRoutingModel(
                create_chat_model(
                    model=settings.CHAT_MODEL,
                    temperature=0,
                    timeout=15,
                    max_tokens=1_000,
                    max_retries=0,
                ),
                model_id=settings.CHAT_MODEL,
                structured_output_method=(settings.LLM_STRUCTURED_OUTPUT_METHOD.value),
            )
        )
    if client is None:
        raise RuntimeError("OpenAI Responses client is unavailable")
    return ModelDirectedIntentRouter(
        OpenAIResponsesRoutingModel(
            client,
            model_id=settings.CHAT_MODEL,
        )
    )


ChatIntentRouterDep = Annotated[
    ModelDirectedIntentRouter,
    Depends(get_chat_intent_router),
]


def get_chat_service(
    session: SessionDep,
    repository: ChatRepositoryDep,
    quota: ChatQuotaServiceDep,
    context_provider: ChatContextProviderDep,
    evidence_pipeline: ChatEvidencePipelineDep,
    intent_router: ChatIntentRouterDep,
    answer_agent: ChatAnswerAgentDep,
) -> CompanyResearchChatService:
    return CompanyResearchChatService(
        session,
        repository=repository,
        quota=quota,
        context_provider=context_provider,
        evidence_pipeline=evidence_pipeline,
        intent_router=intent_router,
        answer_agent=answer_agent,
        summarizer=DeterministicConversationSummarizer(),
    )


ChatServiceDep = Annotated[
    CompanyResearchChatService,
    Depends(get_chat_service),
]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise AuthError("AUTH_REQUIRED", 403)
    return current_user
