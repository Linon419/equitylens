import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlmodel import Session, select

from app.auth.errors import AuthError
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    parse_refresh_token,
)
from app.models.auth_model import AuthSession
from app.models.user_model import User


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    token_family_id: UUID
    record_id: UUID
    access_expires_in: int
    refresh_expires_in: int


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def issue_session(
    session: Session,
    user_id: int,
    *,
    family_id: UUID | None = None,
    now: datetime | None = None,
) -> IssuedTokens:
    issued_at = now or datetime.now(UTC)
    record_id = uuid4()
    token_family_id = family_id or uuid4()
    refresh_token, token_hash = create_refresh_token(record_id)
    refresh_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    record = AuthSession(
        id=record_id,
        user_id=user_id,
        token_hash=token_hash,
        token_family_id=token_family_id,
        expires_at=issued_at + timedelta(seconds=refresh_seconds),
        created_at=issued_at,
    )
    session.add(record)
    session.flush()
    return IssuedTokens(
        access_token=create_access_token(
            user_id,
            token_family_id,
            now=issued_at,
        ),
        refresh_token=refresh_token,
        token_family_id=token_family_id,
        record_id=record_id,
        access_expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=refresh_seconds,
    )


def _revoke_family(session: Session, family_id: UUID, now: datetime) -> None:
    records = session.exec(
        select(AuthSession).where(AuthSession.token_family_id == family_id)
    ).all()
    for record in records:
        record.revoked_at = now
        session.add(record)


def refresh_session(
    session: Session,
    raw_token: str,
    *,
    now: datetime | None = None,
) -> IssuedTokens:
    refreshed_at = now or datetime.now(UTC)
    try:
        parts = parse_refresh_token(raw_token)
    except ValueError as error:
        raise AuthError("AUTH_SESSION_EXPIRED", 401) from error

    statement = (
        select(AuthSession).where(AuthSession.id == parts.record_id).with_for_update()
    )
    record = session.exec(statement).one_or_none()
    if record is None or not hmac.compare_digest(
        record.token_hash,
        parts.token_hash,
    ):
        raise AuthError("AUTH_SESSION_EXPIRED", 401)
    if record.revoked_at is not None:
        raise AuthError("AUTH_SESSION_EXPIRED", 401)
    if record.rotated_at is not None:
        elapsed = refreshed_at - _utc(record.rotated_at)
        grace = timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS)
        if elapsed <= grace:
            raise AuthError("AUTH_REFRESH_STALE", 409)
        _revoke_family(session, record.token_family_id, refreshed_at)
        session.commit()
        raise AuthError("AUTH_SESSION_REUSED", 401)
    if _utc(record.expires_at) <= refreshed_at:
        record.revoked_at = refreshed_at
        session.add(record)
        session.commit()
        raise AuthError("AUTH_SESSION_EXPIRED", 401)

    user = session.get(User, record.user_id)
    if user is None or not user.is_active:
        _revoke_family(session, record.token_family_id, refreshed_at)
        session.commit()
        raise AuthError("AUTH_ACCOUNT_DISABLED", 403)

    successor = issue_session(
        session,
        record.user_id,
        family_id=record.token_family_id,
        now=refreshed_at,
    )
    record.rotated_at = refreshed_at
    record.replaced_by_id = successor.record_id
    session.add(record)
    session.commit()
    return successor


def revoke_session(
    session: Session,
    raw_token: str,
    *,
    now: datetime | None = None,
) -> None:
    revoked_at = now or datetime.now(UTC)
    try:
        parts = parse_refresh_token(raw_token)
    except ValueError:
        return
    record = session.exec(
        select(AuthSession).where(AuthSession.id == parts.record_id).with_for_update()
    ).one_or_none()
    if record is None or not hmac.compare_digest(
        record.token_hash,
        parts.token_hash,
    ):
        return
    _revoke_family(session, record.token_family_id, revoked_at)
    session.commit()
