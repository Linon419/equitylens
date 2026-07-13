import os
from collections.abc import Generator
from pathlib import Path

TEST_DATABASE = Path("/tmp/equitylens-auth-e2e.db")
TEST_DATABASE.unlink(missing_ok=True)

ENV = {
    "SECRET_KEY_ACCESS_API": "e2e-secret-key-with-at-least-32-characters",
    "DATABASE_URL": f"sqlite:///{TEST_DATABASE}",
    "OPENAI_API_KEY": "e2e-openai-key",
    "OPENAI_ORGANIZATION": "e2e-organization",
    "FIRST_SUPERUSER": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "e2e-password",
    "GOOGLE_CLIENT_ID": "e2e-client",
    "FRONTEND_URL": "http://127.0.0.1:3000",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_BUCKET": "filings",
    "S3_ACCESS_KEY_ID": "e2e-key",
    "S3_SECRET_ACCESS_KEY": "e2e-secret",
}
for key, value in ENV.items():
    os.environ.setdefault(key, value)

from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app.api.deps import get_db, get_google_verifier  # noqa: E402
from app.auth.contracts import GoogleIdentity  # noqa: E402
from app.auth.errors import AuthError  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import auth_model, user_model  # noqa: E402, F401

engine = create_engine(
    f"sqlite:///{TEST_DATABASE}",
    connect_args={"check_same_thread": False},
)
SQLModel.metadata.create_all(engine)


class E2EGoogleVerifier:
    def verify(self, credential: str) -> GoogleIdentity:
        if credential != "e2e-google-token":
            raise AuthError("AUTH_INVALID_GOOGLE_TOKEN", 401)
        return GoogleIdentity(
            subject="e2e-google-sub",
            email="investor@example.com",
            email_verified=True,
            full_name="E2E Investor",
            picture=None,
        )


def override_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


app = create_app()
app.dependency_overrides[get_db] = override_db
app.dependency_overrides[get_google_verifier] = E2EGoogleVerifier
