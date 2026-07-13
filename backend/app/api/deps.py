from collections.abc import AsyncIterator, Generator
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlmodel import Session, create_engine, select

from app.auth.contracts import GoogleVerifier
from app.auth.errors import AuthError
from app.auth.google import GoogleTokenVerifier
from app.core.config import settings
from app.core.security import decode_access_token
from app.filings.sec_client import SecClient
from app.market_data.yahoo import YahooMarketDataProvider
from app.models.auth_model import AuthSession
from app.models.user_model import User
from app.providers.market import MarketDataProvider
from app.providers.sec import SecDataProvider

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


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    if token is None:
        raise AuthError("AUTH_REQUIRED", 401)
    try:
        claims = decode_access_token(token.credentials)
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


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise AuthError("AUTH_REQUIRED", 403)
    return current_user
