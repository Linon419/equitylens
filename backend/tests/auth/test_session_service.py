from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app.auth.errors import AuthError
from app.auth.session_service import issue_session, refresh_session, revoke_session
from app.models.auth_model import AuthSession
from app.models.user_model import User


def create_user(session: Session) -> User:
    user = User(email="investor@example.com", hashed_password=None)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_issue_stores_only_refresh_token_hash(db_session: Session) -> None:
    user = create_user(db_session)

    issued = issue_session(db_session, user.id)
    record = db_session.get(AuthSession, issued.record_id)

    assert record is not None
    assert record.token_hash not in issued.refresh_token
    assert len(record.token_hash) == 64


def test_refresh_rotates_token_and_preserves_family(db_session: Session) -> None:
    user = create_user(db_session)
    now = datetime(2026, 7, 13, tzinfo=UTC)
    first = issue_session(db_session, user.id, now=now)
    db_session.commit()

    second = refresh_session(
        db_session,
        first.refresh_token,
        now=now + timedelta(minutes=1),
    )

    assert second.refresh_token != first.refresh_token
    assert second.token_family_id == first.token_family_id
    old = db_session.get(AuthSession, first.record_id)
    assert old is not None
    assert old.rotated_at is not None
    assert old.replaced_by_id == second.record_id


def test_concurrent_refresh_returns_stale_inside_grace(db_session: Session) -> None:
    user = create_user(db_session)
    now = datetime(2026, 7, 13, tzinfo=UTC)
    first = issue_session(db_session, user.id, now=now)
    db_session.commit()
    refresh_session(db_session, first.refresh_token, now=now + timedelta(seconds=1))

    with pytest.raises(AuthError, match="AUTH_REFRESH_STALE") as error:
        refresh_session(
            db_session,
            first.refresh_token,
            now=now + timedelta(seconds=5),
        )

    assert error.value.status_code == 409


def test_replay_after_grace_revokes_family(db_session: Session) -> None:
    user = create_user(db_session)
    now = datetime(2026, 7, 13, tzinfo=UTC)
    first = issue_session(db_session, user.id, now=now)
    db_session.commit()
    refresh_session(db_session, first.refresh_token, now=now + timedelta(seconds=1))

    with pytest.raises(AuthError, match="AUTH_SESSION_REUSED"):
        refresh_session(
            db_session,
            first.refresh_token,
            now=now + timedelta(seconds=12),
        )

    records = db_session.exec(
        select(AuthSession).where(AuthSession.token_family_id == first.token_family_id)
    ).all()
    assert records
    assert all(record.revoked_at is not None for record in records)


def test_logout_revokes_complete_family(db_session: Session) -> None:
    user = create_user(db_session)
    first = issue_session(db_session, user.id)
    db_session.commit()
    second = refresh_session(db_session, first.refresh_token)

    revoke_session(db_session, second.refresh_token)

    records = db_session.exec(
        select(AuthSession).where(AuthSession.token_family_id == first.token_family_id)
    ).all()
    assert records
    assert all(record.revoked_at is not None for record in records)


def test_expired_refresh_token_is_rejected(db_session: Session) -> None:
    user = create_user(db_session)
    issued = issue_session(
        db_session,
        user.id,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    db_session.commit()

    with pytest.raises(AuthError, match="AUTH_SESSION_EXPIRED"):
        refresh_session(
            db_session,
            issued.refresh_token,
            now=datetime(2026, 2, 1, tzinfo=UTC),
        )
