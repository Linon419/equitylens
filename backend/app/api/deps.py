from collections.abc import AsyncIterator, Generator
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from langchain_openai import ChatOpenAI
from sqlmodel import Session, create_engine, select

from app.auth.contracts import GoogleVerifier
from app.auth.errors import AuthError
from app.auth.google import GoogleTokenVerifier
from app.core.config import settings
from app.core.errors import DomainError
from app.core.security import decode_access_token
from app.filings.sec_client import SecClient
from app.jobs.pipeline import CompanyIntelligencePipeline
from app.jobs.rq_backend import RQJobBackend
from app.jobs.schemas import JobBackend
from app.jobs.service import UnconfiguredJobBackend
from app.jobs.vercel_backend import VercelWorkflowBackend
from app.market_data.yahoo import YahooMarketDataProvider
from app.models.auth_model import AuthSession
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
    async with httpx.AsyncClient(timeout=30) as client:
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
        if settings.WORKFLOW_TRIGGER_URL is None:
            raise RuntimeError("WORKFLOW_TRIGGER_URL is required")
        async with httpx.AsyncClient(timeout=15) as client:
            yield VercelWorkflowBackend(
                client,
                settings.WORKFLOW_TRIGGER_URL,
                settings.INTERNAL_JOB_SECRET,
            )
        return
    yield UnconfiguredJobBackend()


JobBackendDep = Annotated[JobBackend, Depends(get_job_backend)]


def get_intelligence_generator() -> IntelligenceGenerator:
    return OpenAIIntelligenceGenerator(
        ChatOpenAI(model=settings.RESEARCH_MODEL),
        settings.RESEARCH_MODEL,
    )


IntelligenceGeneratorDep = Annotated[
    IntelligenceGenerator,
    Depends(get_intelligence_generator),
]


def get_company_intelligence_pipeline(
    session: SessionDep,
    sec_provider: SecDataProviderDep,
    generator: IntelligenceGeneratorDep,
) -> CompanyIntelligencePipeline:
    return CompanyIntelligencePipeline(
        session,
        sec_provider,
        generator,
        schema_version=settings.RESEARCH_SCHEMA_VERSION,
        prompt_version=settings.RESEARCH_PROMPT_VERSION,
        max_filing_bytes=settings.MAX_FILING_BYTES,
    )


CompanyIntelligencePipelineDep = Annotated[
    CompanyIntelligencePipeline,
    Depends(get_company_intelligence_pipeline),
]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise AuthError("AUTH_REQUIRED", 403)
    return current_user
