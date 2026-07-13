from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_db, get_google_verifier
from app.auth.contracts import GoogleIdentity
from app.auth.errors import AuthError
from app.main import create_app
from app.models import auth_model, user_model  # noqa: F401


class FakeVerifier:
    def verify(self, credential: str) -> GoogleIdentity:
        if credential == "invalid":
            raise AuthError("AUTH_INVALID_GOOGLE_TOKEN", 401)
        return GoogleIdentity(
            subject="google-sub-1",
            email="investor@example.com",
            email_verified=True,
            full_name="Investor One",
            picture=None,
        )


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    app = create_app()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_google_verifier] = FakeVerifier
    return TestClient(app)


def test_google_login_me_refresh_preferences_and_logout() -> None:
    client = build_client()
    login = client.post(
        "/api/v1/auth/google",
        json={"credential": "valid", "preferred_locale": "zh-CN"},
    )
    assert login.status_code == 200
    tokens = login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "investor@example.com"

    preference = client.patch(
        "/api/v1/auth/me/preferences",
        headers=headers,
        json={"preferred_locale": "en-US"},
    )
    assert preference.status_code == 200
    assert preference.json()["preferred_locale"] == "en-US"

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

    logout = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed.json()["refresh_token"]},
    )
    assert logout.status_code == 204

    logged_out_me = client.get("/api/v1/auth/me", headers=headers)
    assert logged_out_me.status_code == 401
    assert logged_out_me.json()["code"] == "AUTH_REQUIRED"


def test_invalid_google_token_has_stable_error_shape() -> None:
    response = build_client().post(
        "/api/v1/auth/google",
        headers={"x-request-id": "test-request-id"},
        json={"credential": "invalid", "preferred_locale": "en-US"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "AUTH_INVALID_GOOGLE_TOKEN",
        "request_id": "test-request-id",
    }
    assert response.headers["x-request-id"] == "test-request-id"


def test_protected_route_requires_bearer_token() -> None:
    response = build_client().get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"
    assert response.json()["request_id"]


def test_google_login_rejects_unsupported_locale() -> None:
    response = build_client().post(
        "/api/v1/auth/google",
        json={"credential": "valid", "preferred_locale": "fr-FR"},
    )

    assert response.status_code == 422


def test_legacy_password_route_is_unmounted() -> None:
    response = build_client().post("/api/v1/login/access-token")

    assert response.status_code == 404
