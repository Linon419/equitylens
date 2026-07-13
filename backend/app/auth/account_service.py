from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.auth.contracts import GoogleIdentity, GoogleVerifier
from app.auth.errors import AuthError
from app.auth.session_service import IssuedTokens, issue_session
from app.models.auth_model import ExternalIdentity
from app.models.user_model import User


@dataclass(frozen=True)
class AuthenticatedAccount:
    user: User
    tokens: IssuedTokens


def _create_user(
    session: Session,
    google: GoogleIdentity,
    locale: str,
    now: datetime,
) -> User:
    collision = session.exec(select(User).where(User.email == google.email)).first()
    if collision is not None:
        raise AuthError("AUTH_ACCOUNT_LINK_REQUIRED", 409)

    user = User(
        email=google.email,
        full_name=google.full_name,
        avatar_url=google.picture,
        preferred_locale=locale,
        hashed_password=None,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    session.flush()
    if user.id is None:
        raise RuntimeError("User identifier was not generated")
    session.add(
        ExternalIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=google.subject,
            provider_email=google.email,
            created_at=now,
            last_login_at=now,
        )
    )
    return user


def _update_user(
    session: Session,
    user: User,
    identity: ExternalIdentity,
    google: GoogleIdentity,
    now: datetime,
) -> None:
    identity.provider_email = google.email
    identity.last_login_at = now
    user.full_name = google.full_name
    user.avatar_url = google.picture
    user.updated_at = now
    session.add(identity)
    session.add(user)


def authenticate_google(
    session: Session,
    verifier: GoogleVerifier,
    credential: str,
    locale: str,
) -> AuthenticatedAccount:
    google = verifier.verify(credential)
    now = datetime.now(UTC)
    identity = session.exec(
        select(ExternalIdentity).where(
            ExternalIdentity.provider == "google",
            ExternalIdentity.provider_subject == google.subject,
        )
    ).one_or_none()

    if identity is None:
        user = _create_user(session, google, locale, now)
    else:
        user = session.get(User, identity.user_id)
        if user is None or not user.is_active:
            raise AuthError("AUTH_ACCOUNT_DISABLED", 403)
        _update_user(session, user, identity, google, now)

    if user.id is None:
        raise RuntimeError("User identifier is unavailable")
    tokens = issue_session(session, user.id, now=now)
    session.commit()
    session.refresh(user)
    return AuthenticatedAccount(user=user, tokens=tokens)
