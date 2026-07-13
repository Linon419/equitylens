import pytest
from sqlmodel import Session, select

from app.auth.account_service import authenticate_google
from app.auth.contracts import GoogleIdentity
from app.auth.errors import AuthError
from app.crud import user_crud
from app.models.auth_model import ExternalIdentity
from app.models.user_model import User


class FakeVerifier:
    def __init__(self, identity: GoogleIdentity) -> None:
        self.identity = identity

    def verify(self, credential: str) -> GoogleIdentity:
        return self.identity


IDENTITY = GoogleIdentity(
    subject="google-sub-1",
    email="investor@example.com",
    email_verified=True,
    full_name="Investor One",
    picture="https://example.com/avatar.png",
)


def test_first_google_login_creates_user_identity_and_session(
    db_session: Session,
) -> None:
    result = authenticate_google(
        db_session,
        FakeVerifier(IDENTITY),
        "credential",
        "zh-CN",
    )

    identity = db_session.exec(select(ExternalIdentity)).one()
    assert result.user.email == "investor@example.com"
    assert result.user.preferred_locale == "zh-CN"
    assert result.user.hashed_password is None
    assert identity.provider_subject == "google-sub-1"
    assert identity.provider_email == "investor@example.com"
    assert result.tokens.refresh_token


def test_repeat_login_reuses_user_and_preserves_locale(db_session: Session) -> None:
    first = authenticate_google(db_session, FakeVerifier(IDENTITY), "one", "zh-CN")
    changed = GoogleIdentity(
        subject=IDENTITY.subject,
        email="changed@example.com",
        email_verified=True,
        full_name="Updated Name",
        picture=None,
    )

    second = authenticate_google(db_session, FakeVerifier(changed), "two", "en-US")
    identity = db_session.exec(select(ExternalIdentity)).one()

    assert second.user.id == first.user.id
    assert second.user.email == "investor@example.com"
    assert second.user.preferred_locale == "zh-CN"
    assert second.user.full_name == "Updated Name"
    assert identity.provider_email == "changed@example.com"


def test_existing_email_requires_explicit_linking(db_session: Session) -> None:
    db_session.add(User(email=IDENTITY.email, hashed_password="legacy-hash"))
    db_session.commit()

    with pytest.raises(AuthError, match="AUTH_ACCOUNT_LINK_REQUIRED") as error:
        authenticate_google(
            db_session,
            FakeVerifier(IDENTITY),
            "credential",
            "en-US",
        )

    assert error.value.status_code == 409


def test_disabled_google_account_is_rejected(db_session: Session) -> None:
    first = authenticate_google(
        db_session,
        FakeVerifier(IDENTITY),
        "credential",
        "en-US",
    )
    first.user.is_active = False
    db_session.add(first.user)
    db_session.commit()

    with pytest.raises(AuthError, match="AUTH_ACCOUNT_DISABLED") as error:
        authenticate_google(
            db_session,
            FakeVerifier(IDENTITY),
            "credential",
            "en-US",
        )

    assert error.value.status_code == 403


def test_password_authentication_safely_ignores_google_user(
    db_session: Session,
) -> None:
    authenticate_google(
        db_session,
        FakeVerifier(IDENTITY),
        "credential",
        "en-US",
    )

    result = user_crud.authenticate(
        session=db_session,
        email=IDENTITY.email,
        password="irrelevant",
    )

    assert result is None
