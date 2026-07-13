from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, GoogleVerifierDep, SessionDep
from app.auth.account_service import authenticate_google
from app.auth.session_service import refresh_session, revoke_session
from app.schemas.auth_schema import (
    AuthResponse,
    GoogleAuthRequest,
    LogoutRequest,
    PreferencesUpdate,
    RefreshRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth")


@router.post("/google", response_model=AuthResponse)
def google_login(
    payload: GoogleAuthRequest,
    session: SessionDep,
    verifier: GoogleVerifierDep,
) -> AuthResponse:
    result = authenticate_google(
        session,
        verifier,
        payload.credential,
        payload.preferred_locale,
    )
    return AuthResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        access_expires_in=result.tokens.access_expires_in,
        refresh_expires_in=result.tokens.refresh_expires_in,
        user=UserPublic.model_validate(result.user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, session: SessionDep) -> TokenResponse:
    tokens = refresh_session(session, payload.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_expires_in=tokens.access_expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, session: SessionDep) -> Response:
    revoke_session(session, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserPublic)
def me(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.patch("/me/preferences", response_model=UserPublic)
def update_preferences(
    payload: PreferencesUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> UserPublic:
    current_user.preferred_locale = payload.preferred_locale
    current_user.updated_at = datetime.now(UTC)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UserPublic.model_validate(current_user)
