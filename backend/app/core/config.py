import sys
from enum import StrEnum
from functools import cached_property
from typing import Annotated, Any, Self

from loguru import logger
from pydantic import BeforeValidator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class DeploymentTarget(StrEnum):
    VERCEL = "vercel"
    DOCKER = "docker"


class ObjectStorageProviderName(StrEnum):
    VERCEL_BLOB = "vercel_blob"
    S3 = "s3"


class JobBackendName(StrEnum):
    VERCEL_WORKFLOW = "vercel_workflow"
    RQ = "rq"


class DocumentParserName(StrEnum):
    MANAGED = "managed"
    LOCAL = "local"


def parse_cors(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return value
    raise ValueError("CORS_ORIGINS must be a comma-separated string or list")


CorsOrigins = Annotated[list[str], BeforeValidator(parse_cors)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    API_VERSION: str = "v1"
    PROJECT_NAME: str = "equitylens-api"
    CORS_ORIGINS: CorsOrigins = ["http://localhost:3000"]
    FRONTEND_URL: str = "http://localhost:3000"
    GOOGLE_CLIENT_ID: str

    SECRET_KEY_ACCESS_API: str
    DATABASE_URL: str
    OPENAI_API_KEY: str
    OPENAI_ORGANIZATION: str
    FIRST_SUPERUSER: str
    FIRST_SUPERUSER_PASSWORD: str

    DEPLOYMENT_TARGET: DeploymentTarget = DeploymentTarget.DOCKER
    OBJECT_STORAGE_PROVIDER: ObjectStorageProviderName = ObjectStorageProviderName.S3
    JOB_BACKEND: JobBackendName = JobBackendName.RQ
    DOCUMENT_PARSER: DocumentParserName = DocumentParserName.LOCAL

    REDIS_URL: str | None = None
    S3_ENDPOINT_URL: str | None = None
    S3_BUCKET: str | None = None
    S3_ACCESS_KEY_ID: str | None = None
    S3_SECRET_ACCESS_KEY: str | None = None
    BLOB_READ_WRITE_TOKEN: str | None = None
    MANAGED_PARSER_API_KEY: str | None = None

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_REUSE_GRACE_SECONDS: int = 10

    @property
    def API_V1_STR(self) -> str:
        return f"/api/{self.API_VERSION}"

    @cached_property
    def ASYNC_DATABASE_URI(self) -> str:
        return (
            make_url(self.DATABASE_URL)
            .set(drivername="postgresql+asyncpg")
            .render_as_string(hide_password=False)
        )

    @cached_property
    def SYNC_DATABASE_URI(self) -> str:
        return (
            make_url(self.DATABASE_URL)
            .set(drivername="postgresql+psycopg2")
            .render_as_string(hide_password=False)
        )

    @model_validator(mode="after")
    def validate_deployment_profile(self) -> Self:
        expected = {
            DeploymentTarget.DOCKER: (
                ObjectStorageProviderName.S3,
                JobBackendName.RQ,
                DocumentParserName.LOCAL,
            ),
            DeploymentTarget.VERCEL: (
                ObjectStorageProviderName.VERCEL_BLOB,
                JobBackendName.VERCEL_WORKFLOW,
                DocumentParserName.MANAGED,
            ),
        }
        actual = (
            self.OBJECT_STORAGE_PROVIDER,
            self.JOB_BACKEND,
            self.DOCUMENT_PARSER,
        )
        if actual != expected[self.DEPLOYMENT_TARGET]:
            label = "Docker" if self.DEPLOYMENT_TARGET == "docker" else "Vercel"
            raise ValueError(f"{label} profile requires its matching providers")

        required_credentials = {
            DeploymentTarget.DOCKER: (
                "REDIS_URL",
                "S3_ENDPOINT_URL",
                "S3_BUCKET",
                "S3_ACCESS_KEY_ID",
                "S3_SECRET_ACCESS_KEY",
            ),
            DeploymentTarget.VERCEL: (
                "BLOB_READ_WRITE_TOKEN",
                "MANAGED_PARSER_API_KEY",
            ),
        }
        missing = [
            field
            for field in required_credentials[self.DEPLOYMENT_TARGET]
            if not getattr(self, field)
        ]
        if missing:
            raise ValueError(
                f"{self.DEPLOYMENT_TARGET.value} profile is missing: "
                f"{', '.join(missing)}"
            )
        return self


class LogConfig:
    @staticmethod
    def configure_logging() -> None:
        logger.remove()
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level}</level> | <level>{message}</level>"
            ),
            level="DEBUG",
        )


LogConfig.configure_logging()
settings = Settings()
