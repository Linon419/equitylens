import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {
    "SECRET_KEY_ACCESS_API": "x" * 32,
    "DATABASE_URL": "postgresql://app:app@localhost:5432/equitylens",
    "OPENAI_API_KEY": "test",
    "OPENAI_ORGANIZATION": "test",
    "FIRST_SUPERUSER": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "test-password",
}

DOCKER_PROVIDERS = {
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_BUCKET": "filings",
    "S3_ACCESS_KEY_ID": "test-access-key",
    "S3_SECRET_ACCESS_KEY": "test-secret-key",
}

VERCEL_PROVIDERS = {
    "BLOB_READ_WRITE_TOKEN": "test-blob-token",
    "MANAGED_PARSER_API_KEY": "test-parser-key",
}


def test_docker_profile_accepts_docker_providers() -> None:
    settings = Settings(
        **BASE,
        **DOCKER_PROVIDERS,
        DEPLOYMENT_TARGET="docker",
        OBJECT_STORAGE_PROVIDER="s3",
        JOB_BACKEND="rq",
        DOCUMENT_PARSER="local",
    )

    assert settings.DEPLOYMENT_TARGET == "docker"
    assert settings.PROJECT_NAME == "equitylens-api"
    assert settings.SYNC_DATABASE_URI.startswith("postgresql+psycopg2://")
    assert settings.ASYNC_DATABASE_URI.startswith("postgresql+asyncpg://")
    assert "app:app@" in settings.SYNC_DATABASE_URI
    assert "app:app@" in settings.ASYNC_DATABASE_URI


def test_vercel_profile_accepts_vercel_providers() -> None:
    settings = Settings(
        **BASE,
        **VERCEL_PROVIDERS,
        DEPLOYMENT_TARGET="vercel",
        OBJECT_STORAGE_PROVIDER="vercel_blob",
        JOB_BACKEND="vercel_workflow",
        DOCUMENT_PARSER="managed",
    )

    assert settings.DEPLOYMENT_TARGET == "vercel"


def test_profile_rejects_mixed_provider_configuration() -> None:
    with pytest.raises(ValidationError, match="Docker profile requires"):
        Settings(
            **BASE,
            **DOCKER_PROVIDERS,
            DEPLOYMENT_TARGET="docker",
            OBJECT_STORAGE_PROVIDER="vercel_blob",
            JOB_BACKEND="rq",
            DOCUMENT_PARSER="local",
        )
