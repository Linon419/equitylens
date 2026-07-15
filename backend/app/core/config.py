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


class MarketDataProviderName(StrEnum):
    YAHOO = "yahoo"


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
    WORKFLOW_TRIGGER_URL: str | None = None
    SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL: str | None = None

    MARKET_DATA_PROVIDER: MarketDataProviderName = MarketDataProviderName.YAHOO
    SEC_USER_AGENT: str
    RESEARCH_MODEL: str = "gpt-5-mini"
    RESEARCH_SCHEMA_VERSION: str = "company-intelligence-v1"
    RESEARCH_PROMPT_VERSION: str = "company-intelligence-2026-07-13"
    SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE: str | None = None
    SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION: str = "supply-chain-graph.v1"
    SUPPLY_CHAIN_GRAPH_PROMPT_VERSION: str = "supply-chain-graph.2026-07-14"
    SUPPLY_CHAIN_GRAPH_MIN_NODES: int = 25
    SUPPLY_CHAIN_GRAPH_MAX_NODES: int = 40
    SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD: float = 0.75
    SUPPLY_CHAIN_GRAPH_CACHE_TTL_HOURS: int = 24
    SUPPLY_CHAIN_GRAPH_SOURCE_LIMIT: int = 24
    SUPPLY_CHAIN_GRAPH_SOURCE_BYTES: int = 8_000_000
    SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET: int = 100_000
    GRAPH_ARTIFACT_PREFIX: str = "supply-chain"
    CHAT_GUEST_DAILY_LIMIT: int = 2
    CHAT_USER_DAILY_LIMIT: int = 10
    CHAT_GUEST_RETENTION_DAYS: int = 7
    CHAT_MAX_MESSAGE_CHARS: int = 2_000
    CHAT_MAX_HISTORY_MESSAGES: int = 8
    CHAT_CHUNK_TARGET_TOKENS: int = 700
    CHAT_CHUNK_OVERLAP_TOKENS: int = 100
    CHAT_CHUNK_MIN_FINAL_TOKENS: int = 120
    CHAT_RETRIEVAL_CANDIDATES: int = 20
    CHAT_RETRIEVAL_MAX_CHUNKS: int = 8
    CHAT_RETRIEVAL_MAX_PER_SECTION: int = 3
    CHAT_RETRIEVAL_TOKEN_BUDGET: int = 6_000
    CHAT_RRF_K: int = 60
    CHAT_WEB_MAX_QUERIES: int = 3
    CHAT_WEB_MAX_PAGES: int = 8
    CHAT_WEB_SEARCH_PROVIDER: str = "openai"
    CHAT_EMBEDDING_MODEL: str = "text-embedding-3-small"
    CHAT_EMBEDDING_DIMENSIONS: int = 1_536
    CHAT_MODEL_OVERRIDE: str | None = None
    CHAT_PROMPT_VERSION: str = "company-chat.2026-07-14"
    CHAT_ANSWER_SCHEMA_VERSION: str = "company-chat.v1"
    CHAT_INDEX_SCHEMA_VERSION: str = "filing-chunk.v1"
    CHAT_INDEX_WORKFLOW_TRIGGER_URL: str | None = None
    CHAT_WEB_ARTIFACT_PREFIX: str = "chat-web"
    GUEST_SIGNING_SECRET: str
    QUOTA_HASH_SECRET: str
    INTERNAL_JOB_SECRET: str

    MARKET_QUOTE_TTL_SECONDS: int = 15 * 60
    COMPANY_PROFILE_TTL_SECONDS: int = 7 * 24 * 60 * 60
    SEC_SUBMISSIONS_TTL_SECONDS: int = 60 * 60
    FINANCIALS_TTL_SECONDS: int = 24 * 60 * 60
    GUEST_DAILY_ANALYSIS_LIMIT: int = 2
    USER_DAILY_ANALYSIS_LIMIT: int = 10
    IP_DAILY_ANALYSIS_LIMIT: int = 10
    MAX_FILING_BYTES: int = 15 * 1024 * 1024

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_REUSE_GRACE_SECONDS: int = 10

    @property
    def API_V1_STR(self) -> str:
        return f"/api/{self.API_VERSION}"

    @property
    def SUPPLY_CHAIN_GRAPH_MODEL(self) -> str:
        return self.SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE or self.RESEARCH_MODEL

    @property
    def CHAT_MODEL(self) -> str:
        return self.CHAT_MODEL_OVERRIDE or self.RESEARCH_MODEL

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
        self._validate_chat_settings()
        if self.SUPPLY_CHAIN_GRAPH_MIN_NODES < 1:
            raise ValueError("SUPPLY_CHAIN_GRAPH_MIN_NODES must be at least 1")
        if self.SUPPLY_CHAIN_GRAPH_MAX_NODES < self.SUPPLY_CHAIN_GRAPH_MIN_NODES:
            raise ValueError(
                "SUPPLY_CHAIN_GRAPH_MAX_NODES must be greater than or equal to "
                "SUPPLY_CHAIN_GRAPH_MIN_NODES"
            )
        if not 0 <= self.SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD <= 1:
            raise ValueError(
                "SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD must be between 0 and 1"
            )
        if self.SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET < 1:
            raise ValueError(
                "SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET must be at least 1"
            )

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
                "WORKFLOW_TRIGGER_URL",
                "SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL",
                "CHAT_INDEX_WORKFLOW_TRIGGER_URL",
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

        short_secrets = [
            field
            for field in (
                "GUEST_SIGNING_SECRET",
                "QUOTA_HASH_SECRET",
                "INTERNAL_JOB_SECRET",
            )
            if len(getattr(self, field)) < 32
        ]
        if short_secrets:
            raise ValueError(
                "Phase 2 secrets require at least 32 characters: "
                f"{', '.join(short_secrets)}"
            )
        return self

    def _validate_chat_settings(self) -> None:
        positive_fields = (
            "CHAT_GUEST_DAILY_LIMIT",
            "CHAT_USER_DAILY_LIMIT",
            "CHAT_GUEST_RETENTION_DAYS",
            "CHAT_MAX_MESSAGE_CHARS",
            "CHAT_MAX_HISTORY_MESSAGES",
            "CHAT_CHUNK_TARGET_TOKENS",
            "CHAT_CHUNK_MIN_FINAL_TOKENS",
            "CHAT_RETRIEVAL_CANDIDATES",
            "CHAT_RETRIEVAL_MAX_CHUNKS",
            "CHAT_RETRIEVAL_MAX_PER_SECTION",
            "CHAT_RETRIEVAL_TOKEN_BUDGET",
            "CHAT_RRF_K",
            "CHAT_WEB_MAX_QUERIES",
            "CHAT_WEB_MAX_PAGES",
        )
        for field in positive_fields:
            if getattr(self, field) < 1:
                raise ValueError(f"{field} must be at least 1")
        if not 0 <= self.CHAT_CHUNK_OVERLAP_TOKENS < self.CHAT_CHUNK_TARGET_TOKENS:
            raise ValueError(
                "CHAT_CHUNK_OVERLAP_TOKENS must be below CHAT_CHUNK_TARGET_TOKENS"
            )
        if self.CHAT_CHUNK_MIN_FINAL_TOKENS > self.CHAT_CHUNK_TARGET_TOKENS:
            raise ValueError(
                "CHAT_CHUNK_MIN_FINAL_TOKENS must not exceed CHAT_CHUNK_TARGET_TOKENS"
            )
        if self.CHAT_RETRIEVAL_MAX_CHUNKS > self.CHAT_RETRIEVAL_CANDIDATES:
            raise ValueError(
                "CHAT_RETRIEVAL_MAX_CHUNKS must not exceed CHAT_RETRIEVAL_CANDIDATES"
            )
        if self.CHAT_RETRIEVAL_MAX_PER_SECTION > self.CHAT_RETRIEVAL_MAX_CHUNKS:
            raise ValueError(
                "CHAT_RETRIEVAL_MAX_PER_SECTION must not exceed "
                "CHAT_RETRIEVAL_MAX_CHUNKS"
            )
        if (
            self.CHAT_INDEX_SCHEMA_VERSION == "filing-chunk.v1"
            and self.CHAT_EMBEDDING_DIMENSIONS != 1_536
        ):
            raise ValueError(
                "CHAT_EMBEDDING_DIMENSIONS must be 1536 for filing-chunk.v1"
            )


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
