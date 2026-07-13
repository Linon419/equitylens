# Phase 0 Engineering Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a tested engineering baseline that runs the same Next.js and FastAPI application through Vercel and Docker deployment profiles.

**Architecture:** Keep domain code inside the FastAPI application and place deployment-specific behavior behind typed provider contracts. Use a lightweight Python 3.12 API bundle for Vercel, an optional worker dependency group for Docker, one PostgreSQL schema managed by Alembic, and one Next.js standalone build shared by Vercel and containers.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic Settings, SQLModel, Alembic, pytest, Next.js App Router, React, TypeScript, pnpm, Vitest, Docker Compose, PostgreSQL/pgvector, Redis, MinIO, Vercel Python Runtime.

---

## Scope and execution prerequisites

This plan implements Phase 0 from the approved product specification. Registration, internationalization, company research, SEC ingestion, RAG, and production provider adapters receive separate implementation plans in Phases 1–6.

Execution requires:

- permission to replace the obsolete `backend/poetry.lock` with `backend/uv.lock`;
- Docker Desktop or another Docker Engine with Compose v2 for container verification;
- a Vercel account session for `vercel pull` and Preview deployment verification;
- Node.js 22 with Corepack; and
- `uv`, which can provision Python 3.12 automatically.

## File map

### Repository root

- Modify `.gitignore`: track the frontend, JSON configuration, and safe environment templates.
- Create `.node-version`: pin the frontend development runtime.
- Create `.env.example`: document shared Docker-profile configuration.
- Create `docker-compose.yml`: define the Docker deployment profile.
- Modify `README.md`: replace the prototype setup instructions with verified Phase 0 commands.
- Create `scripts/smoke.sh`: run the same health checks against Docker and Vercel URLs.
- Create `deploy/docker/README.md`: document Docker lifecycle and health checks.
- Create `deploy/vercel/README.md`: document the two-project Vercel layout.

### Backend

- Create `backend/.python-version`: pin Vercel and local Python to 3.12.
- Modify `backend/pyproject.toml`: migrate metadata to PEP 621, split API and worker dependencies, and configure tests and linting.
- Delete `backend/poetry.lock`: retire the former package-manager lock after explicit approval.
- Create `backend/uv.lock`: lock Python 3.12 dependencies.
- Modify `backend/Dockerfile`: build lightweight API and worker targets.
- Create `backend/vercel.json`: configure the FastAPI function bundle.
- Create `backend/app/app.py`: expose the Vercel-compatible ASGI entry point.
- Modify `backend/app/main.py`: expose an application factory.
- Modify `backend/app/api/deps.py`: remove the unused NextAuth dependency from the API import path.
- Modify `backend/app/core/config.py`: add deployment/provider configuration and validation.
- Create `backend/app/providers/__init__.py`: export provider types.
- Create `backend/app/providers/contracts.py`: define storage, job, cache, and parser contracts.
- Create `backend/app/api/routes/health.py`: expose liveness and readiness endpoints.
- Modify `backend/app/api/main.py`: register health routes.
- Create `backend/alembic.ini`: configure migrations.
- Create `backend/app/migrations/env.py`: connect Alembic to application metadata and `DATABASE_URL`.
- Create `backend/app/migrations/script.py.mako`: define revision rendering.
- Create `backend/app/migrations/versions/20260713_0001_initial.py`: create pgvector, user, and item schema.
- Create `backend/tests/conftest.py`: provide deterministic test configuration.
- Create `backend/tests/core/test_config.py`: verify deployment-provider combinations.
- Create `backend/tests/providers/test_contracts.py`: verify shared provider value objects.
- Create `backend/tests/api/test_health.py`: verify health endpoints and ASGI entry point.
- Create `backend/tests/test_migrations.py`: verify a single Alembic head.
- Create `backend/tests/test_vercel_config.py`: verify Vercel entry point and bundle exclusions.

### Frontend

- Create `frontend/` with the official Next.js App Router scaffold.
- Modify `frontend/package.json`: add test and verification scripts.
- Modify `frontend/next.config.ts`: enable the standalone Docker output.
- Modify `frontend/src/app/page.tsx`: provide the Phase 0 baseline page.
- Create `frontend/src/app/page.test.tsx`: verify the baseline page.
- Create `frontend/src/app/api/health/route.ts`: expose a frontend health endpoint.
- Create `frontend/src/app/api/health/route.test.ts`: verify the health response.
- Create `frontend/src/test/setup.ts`: load DOM matchers.
- Create `frontend/vitest.config.ts`: configure Vitest and the `@` alias.
- Create `frontend/Dockerfile`: build and run the Next.js standalone server.

## Task 1: Track the new application structure and pin runtimes

**Files:**

- Modify: `.gitignore`
- Create: `.node-version`
- Create: `backend/.python-version`

- [x] **Step 1: Capture the current ignore failure**

Run:

```bash
git check-ignore -v frontend/package.json frontend/tsconfig.json .env.example
```

Expected: all three paths match broad ignore rules, proving that the frontend and environment template would be hidden from Git.

- [x] **Step 2: Replace the broad ignore rules**

Remove these lines from `.gitignore`:

```gitignore
*frontend
frontend/*
*.json
```

Add these exceptions immediately after the environment-file rules:

```gitignore
!.env.example
!**/.env.example
.vercel/
**/.vercel/
```

Create `.node-version`:

```text
22
```

Create `backend/.python-version`:

```text
3.12
```

- [x] **Step 3: Verify the paths are trackable**

Run:

```bash
test -z "$(git check-ignore frontend/package.json frontend/tsconfig.json .env.example 2>/dev/null)"
test "$(cat .node-version)" = "22"
test "$(cat backend/.python-version)" = "3.12"
```

Expected: exit code `0`.

- [x] **Step 4: Commit the runtime baseline**

```bash
git add .gitignore .node-version backend/.python-version
git commit -m "chore: pin frontend and backend runtimes"
```

## Task 2: Migrate the backend package baseline to uv

**Files:**

- Modify: `backend/pyproject.toml`
- Delete: `backend/poetry.lock`
- Create: `backend/uv.lock`

- [x] **Step 1: Record the current Python incompatibility**

Run:

```bash
cd backend
uv lock --check
```

Expected: FAIL because the repository has no `uv.lock` and the current Poetry metadata restricts Python to `<3.12`.

- [x] **Step 2: Replace `backend/pyproject.toml` with a PEP 621 project**

Use this complete file:

```toml
[project]
name = "us-equity-research-api"
version = "0.1.0"
description = "FastAPI backend for the US equity research knowledge base"
requires-python = ">=3.12,<3.13"
dependencies = [
  "asyncpg>=0.30,<1",
  "fastapi>=0.117.1,<1",
  "langchain>=0.3,<1",
  "langchain-community>=0.3,<1",
  "langchain-openai>=0.3,<1",
  "loguru>=0.7,<1",
  "passlib[bcrypt]>=1.7.4,<2",
  "pgvector>=0.3,<1",
  "psycopg2-binary>=2.9,<3",
  "pydantic-settings>=2.10,<3",
  "python-dotenv>=1,<2",
  "python-jose[cryptography]>=3.5,<4",
  "python-multipart>=0.0.20,<1",
  "pyyaml>=6,<7",
  "sqlalchemy>=2.0,<3",
  "sqlmodel>=0.0.24,<0.1",
  "uvicorn[standard]>=0.35,<1",
]

[dependency-groups]
dev = [
  "alembic>=1.16,<2",
  "httpx>=0.28,<1",
  "pytest>=8.4,<9",
  "pytest-asyncio>=1.0,<2",
  "pytest-cov>=6.2,<7",
  "ruff>=0.12,<1",
]
worker = [
  "boto3>=1.39,<2",
  "pymupdf>=1.26,<2",
  "pypdf>=5,<7",
  "rq>=2.4,<3",
  "unstructured[pdf]>=0.18,<1",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
addopts = "-q --strict-markers"
pythonpath = ["."]
testpaths = ["tests"]

[tool.coverage.run]
branch = true

[tool.coverage.report]
fail_under = 80
show_missing = true

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

- [x] **Step 3: Replace the package-manager lock**

After the deletion is explicitly approved, remove `backend/poetry.lock` through the file-editing workflow. Then run:

```bash
cd backend
uv lock
uv sync --frozen
uv sync --frozen --group worker
```

Expected: `uv.lock` is created, Python 3.12 is selected, and both API and worker dependency sets resolve successfully.

- [x] **Step 4: Verify the API dependency set**

Run:

```bash
cd backend
uv run python -c "import fastapi, langchain, sqlmodel; print('backend-dependencies-ok')"
uv lock --check
```

Expected:

```text
backend-dependencies-ok
```

- [x] **Step 5: Commit the package migration**

```bash
git add -A backend/pyproject.toml backend/poetry.lock backend/uv.lock
git commit -m "chore(backend): migrate to Python 3.12 and uv"
```

## Task 3: Define deployment configuration and provider contracts

**Files:**

- Modify: `backend/app/core/config.py`
- Create: `backend/app/providers/__init__.py`
- Create: `backend/app/providers/contracts.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/core/test_config.py`
- Create: `backend/tests/providers/test_contracts.py`

- [x] **Step 1: Write failing configuration tests**

Create `backend/tests/conftest.py`:

```python
import os


TEST_ENV = {
    "SECRET_KEY_ACCESS_API": "test-secret-key-with-at-least-32-characters",
    "DATABASE_URL": "postgresql://app:app@localhost:5432/app",
    "OPENAI_API_KEY": "test-openai-key",
    "OPENAI_ORGANIZATION": "test-organization",
    "FIRST_SUPERUSER": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "test-password",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_BUCKET": "filings",
    "S3_ACCESS_KEY_ID": "test-access-key",
    "S3_SECRET_ACCESS_KEY": "test-secret-key",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
```

Create `backend/tests/core/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from app.core.config import Settings


BASE = {
    "SECRET_KEY_ACCESS_API": "x" * 32,
    "DATABASE_URL": "postgresql://app:app@localhost:5432/app",
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
```

Create `backend/tests/providers/test_contracts.py`:

```python
from datetime import UTC, datetime

from app.providers.contracts import JobState, UploadIntent


def test_upload_intent_is_immutable() -> None:
    intent = UploadIntent(
        object_key="users/1/documents/report.pdf",
        upload_url="https://uploads.example.com/report.pdf",
        headers={"content-type": "application/pdf"},
        expires_at=datetime(2026, 7, 13, tzinfo=UTC),
    )

    assert intent.object_key.endswith("report.pdf")
    assert intent.headers == {"content-type": "application/pdf"}


def test_job_state_has_stable_wire_values() -> None:
    assert [state.value for state in JobState] == [
        "queued",
        "downloading",
        "parsing",
        "embedding",
        "analyzing",
        "completed",
        "failed",
    ]
```

- [x] **Step 2: Run the tests to verify failure**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py tests/providers/test_contracts.py -v
```

Expected: FAIL because the deployment enums and provider contracts do not exist.

- [x] **Step 3: Implement provider contracts**

Create `backend/app/providers/contracts.py`:

```python
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class JobState(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class UploadIntent:
    object_key: str
    upload_url: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class JobSubmission:
    job_id: str
    state: JobState


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str


class ObjectStorageProvider(Protocol):
    async def create_upload_intent(
        self, *, object_key: str, content_type: str
    ) -> UploadIntent: ...

    async def open(self, *, object_key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, *, object_key: str) -> None: ...


class JobBackend(Protocol):
    async def enqueue(
        self, *, job_type: str, payload: dict[str, str]
    ) -> JobSubmission: ...

    async def get_state(self, *, job_id: str) -> JobState: ...


class CacheProvider(Protocol):
    async def get(self, *, key: str) -> bytes | None: ...

    async def set(self, *, key: str, value: bytes, ttl_seconds: int) -> None: ...


class DocumentParser(Protocol):
    async def parse(self, *, object_key: str) -> list[ParsedPage]: ...
```

Create `backend/app/providers/__init__.py`:

```python
from app.providers.contracts import (
    CacheProvider,
    DocumentParser,
    JobBackend,
    JobState,
    ObjectStorageProvider,
    ParsedPage,
    UploadIntent,
)

__all__ = [
    "CacheProvider",
    "DocumentParser",
    "JobBackend",
    "JobState",
    "ObjectStorageProvider",
    "ParsedPage",
    "UploadIntent",
]
```

- [x] **Step 4: Implement validated settings**

Replace `backend/app/core/config.py` with:

```python
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
    PROJECT_NAME: str = "us-equity-research"
    CORS_ORIGINS: CorsOrigins = ["http://localhost:3000"]

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

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

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
```

- [x] **Step 5: Run tests and lint**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py tests/providers/test_contracts.py -v
uv run ruff check app/core/config.py app/providers tests/core tests/providers
```

Expected: all tests pass and Ruff reports no violations.

- [x] **Step 6: Commit the contracts**

```bash
git add backend/app/core/config.py backend/app/providers backend/tests
git commit -m "feat(backend): define deployment config and contracts"
```

## Task 4: Add the application factory and health endpoints

**Files:**

- Create: `backend/app/app.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/api/main.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/tests/api/test_health.py`

- [x] **Step 1: Write failing health tests**

Create `backend/tests/api/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.app import app


client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_exposes_active_profile() -> None:
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "deployment_target": "docker",
    }
```

- [x] **Step 2: Run the test to verify failure**

Run:

```bash
cd backend
uv run pytest tests/api/test_health.py -v
```

Expected: FAIL because `app.app` and the health routes do not exist.

- [x] **Step 3: Implement health routes**

Create `backend/app/api/routes/health.py`:

```python
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings


router = APIRouter(prefix="/health")


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ready"] = "ready"
    deployment_target: str


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse()


@router.get("/ready", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse:
    return ReadinessResponse(deployment_target=settings.DEPLOYMENT_TARGET.value)
```

Modify `backend/app/api/main.py`:

```python
from fastapi import APIRouter

from app.api.routes import health, login, qa


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(login.router, tags=["login"])
api_router.include_router(qa.router, prefix="/qa", tags=["qa"])
```

- [x] **Step 4: Implement the application factory and ASGI entry point**

Replace `backend/app/main.py` with:

```python
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.API_V1_STR)

    @application.get("/")
    async def root() -> dict[str, Any]:
        return {"name": settings.PROJECT_NAME, "status": "ok"}

    return application
```

Create `backend/app/app.py`:

```python
from app.main import create_app


app = create_app()
```

- [x] **Step 5: Remove the unused NextAuth import path**

Replace `backend/app/api/deps.py` with:

```python
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlmodel import Session, create_engine

from app.core import security
from app.core.config import settings
from app.models.user_model import TokenPayload, User


engine = create_engine(settings.SYNC_DATABASE_URI)
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY_ACCESS_API,
            algorithms=[security.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError) as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from error
    user = session.get(User, token_data.sub)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=400,
            detail="The user doesn't have enough privileges",
        )
    return current_user
```

- [x] **Step 6: Run the focused and backend suites**

Run:

```bash
cd backend
uv run pytest tests/api/test_health.py -v
uv run ruff check app/app.py app/main.py app/core/config.py app/providers app/api/deps.py app/api/main.py app/api/routes/health.py tests
```

Expected: health tests pass and Ruff reports no violations in the Phase 0 files.

- [x] **Step 7: Commit the application baseline**

```bash
git add backend/app/app.py backend/app/main.py backend/app/api backend/tests/api
git commit -m "feat(backend): add app factory and health checks"
```

## Task 5: Introduce Alembic as the schema authority

**Files:**

- Create: `backend/alembic.ini`
- Create: `backend/app/migrations/env.py`
- Create: `backend/app/migrations/script.py.mako`
- Create: `backend/app/migrations/versions/20260713_0001_initial.py`
- Create: `backend/tests/test_migrations.py`

- [x] **Step 1: Write a failing single-head test**

Create `backend/tests/test_migrations.py`:

```python
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_migrations_have_one_expected_head() -> None:
    root = Path(__file__).resolve().parents[1]
    config = Config(root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["20260713_0001"]
```

- [x] **Step 2: Run the test to verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_migrations.py -v
```

Expected: FAIL because `alembic.ini` and the migration directory do not exist.

- [x] **Step 3: Add Alembic configuration**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = %(here)s/app/migrations
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `backend/app/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from app.core.config import settings
from app.models import user_model  # noqa: F401


config = context.config
config.set_main_option("sqlalchemy.url", settings.SYNC_DATABASE_URI)

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.SYNC_DATABASE_URI,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `backend/app/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [x] **Step 4: Add the initial migration**

Create `backend/app/migrations/versions/20260713_0001_initial.py`:

```python
"""Create the initial application schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260713_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "user",
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_table(
        "item",
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("item")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
```

- [x] **Step 5: Verify migration metadata and SQL rendering**

Run:

```bash
cd backend
uv run pytest tests/test_migrations.py -v
uv run alembic heads
DATABASE_URL=postgresql://app:app@localhost:5432/app uv run alembic upgrade head --sql > /tmp/equity-research-migration.sql
rg -n 'CREATE EXTENSION|CREATE TABLE|20260713_0001' /tmp/equity-research-migration.sql
```

Expected: one head named `20260713_0001`; offline SQL contains the extension and both tables.

- [x] **Step 6: Commit migrations**

```bash
git add backend/alembic.ini backend/app/migrations backend/tests/test_migrations.py
git commit -m "feat(backend): manage schema with Alembic"
```

## Task 6: Scaffold and test the Next.js frontend

The implemented baseline also includes localized `en-US` and `zh-CN` routes,
browser-language detection, a persistent language selector, and focused i18n tests.

**Files:**

- Create: `frontend/` through `create-next-app`
- Modify: `frontend/package.json`
- Modify: `frontend/next.config.ts`
- Modify: `frontend/src/app/page.tsx`
- Create: `frontend/src/app/page.test.tsx`
- Create: `frontend/src/app/api/health/route.ts`
- Create: `frontend/src/app/api/health/route.test.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/vitest.config.ts`

- [x] **Step 1: Generate the official scaffold**

Run from the repository root:

```bash
corepack enable
pnpm dlx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias '@/*' --use-pnpm --yes
cd frontend
pnpm add --save-dev vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom
```

Expected: a TypeScript App Router application with `pnpm-lock.yaml`.

- [x] **Step 2: Add test scripts and Vitest configuration**

Add these scripts to `frontend/package.json` while preserving the generated dependency versions:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

Create `frontend/vitest.config.ts`:

```typescript
import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

Create `frontend/src/test/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

- [x] **Step 3: Write failing frontend tests**

Create `frontend/src/app/page.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "./page";

describe("Home", () => {
  it("identifies the product baseline", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", { name: "US Equity Research" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Engineering baseline ready")).toBeInTheDocument();
  });
});
```

Create `frontend/src/app/api/health/route.test.ts`:

```typescript
import { describe, expect, it } from "vitest";

import { GET } from "./route";

describe("GET /api/health", () => {
  it("returns a stable liveness response", async () => {
    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ok" });
  });
});
```

- [x] **Step 4: Run the tests to verify failure**

Run:

```bash
cd frontend
pnpm test
```

Expected: FAIL because the generated page has different content and the health route does not exist.

- [x] **Step 5: Implement the baseline page and health route**

Replace `frontend/src/app/page.tsx` with:

```tsx
export default function Home() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-slate-50">
      <section className="max-w-2xl text-center">
        <p className="mb-4 text-sm font-medium uppercase tracking-[0.24em] text-emerald-400">
          Engineering baseline ready
        </p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-6xl">
          US Equity Research
        </h1>
        <p className="mt-6 text-lg leading-8 text-slate-300">
          Research companies, filings, financial performance, and valuation with
          traceable evidence.
        </p>
      </section>
    </main>
  );
}
```

Create `frontend/src/app/api/health/route.ts`:

```typescript
export async function GET() {
  return Response.json({ status: "ok" });
}
```

Replace `frontend/next.config.ts` with:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
};

export default nextConfig;
```

- [x] **Step 6: Verify tests, lint, and production build**

Run:

```bash
cd frontend
pnpm test
pnpm lint
pnpm build
```

Expected: tests pass, ESLint reports no errors, and Next.js creates `.next/standalone`.

- [x] **Step 7: Commit the frontend baseline**

```bash
git add frontend
git commit -m "feat(frontend): create Next.js test baseline"
```

## Task 7: Build the Docker deployment profile

**Files:**

- Modify: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `deploy/docker/README.md`

- [x] **Step 1: Replace the backend Dockerfile with API and worker targets**

Use this complete `backend/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS api-build

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app

FROM api-build AS worker-build
RUN uv sync --frozen --no-dev --group worker

FROM python:3.12-slim AS api
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=api-build /app /app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')"
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.12-slim AS worker
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=worker-build /app /app
CMD ["rq", "worker", "--url", "redis://redis:6379/0", "ingestion"]
```

- [x] **Step 2: Add the Next.js standalone Dockerfile**

Create `frontend/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-alpine AS base
ENV PNPM_HOME="/pnpm" PATH="$PNPM_HOME:$PATH"
RUN corepack enable
WORKDIR /app

FROM base AS dependencies
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:22-alpine AS runtime
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
WORKDIR /app
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=build --chown=nextjs:nodejs /app/public ./public
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD wget -qO- http://localhost:3000/api/health >/dev/null || exit 1
CMD ["node", "server.js"]
```

- [x] **Step 3: Add the safe environment template**

Create `.env.example`:

```dotenv
DEPLOYMENT_TARGET=docker
OBJECT_STORAGE_PROVIDER=s3
JOB_BACKEND=rq
DOCUMENT_PARSER=local

SECRET_KEY_ACCESS_API=replace-with-at-least-32-random-characters
DATABASE_URL=postgresql://app:app@db:5432/app
REDIS_URL=redis://redis:6379/0

POSTGRES_DB=app
POSTGRES_USER=app
POSTGRES_PASSWORD=app

S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET=filings
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

OPENAI_API_KEY=replace-with-openai-key
OPENAI_ORGANIZATION=replace-with-openai-organization
FIRST_SUPERUSER=admin@example.com
FIRST_SUPERUSER_PASSWORD=replace-with-admin-password
CORS_ORIGINS=http://localhost:3000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [x] **Step 4: Define the Compose stack**

Create `docker-compose.yml`:

```yaml
name: us-equity-research

services:
  db:
    image: pgvector/pgvector:0.8.2-pg17-bookworm
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-app}
      POSTGRES_USER: ${POSTGRES_USER:-app}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-app}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:8.8.0-alpine
    command: ["redis-server", "--save", "60", "1"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    volumes:
      - redis_data:/data

  minio:
    image: quay.io/minio/minio:RELEASE.2025-07-23T15-54-02Z
    command: ["server", "/data", "--console-address", ":9001"]
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    ports:
      - "9001:9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 3s
      retries: 10
    volumes:
      - minio_data:/data

  migrate:
    build:
      context: ./backend
      target: api
    command: ["alembic", "upgrade", "head"]
    env_file: .env
    depends_on:
      db:
        condition: service_healthy

  api:
    build:
      context: ./backend
      target: api
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy

  worker:
    build:
      context: ./backend
      target: worker
    env_file: .env
    depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy

  web:
    build:
      context: ./frontend
    environment:
      NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000}
    ports:
      - "3000:3000"
    depends_on:
      api:
        condition: service_healthy

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

- [ ] **Step 5: Document and validate the Docker profile**

Static Docker profile tests and production dependency checks pass. Image build,
Compose startup, and container health verification require a local Docker CLI.

Create `deploy/docker/README.md`:

````markdown
# Docker deployment profile

Copy `.env.example` to `.env`, replace every secret, then run:

```bash
docker compose config
docker compose build
docker compose up --wait
```

Health endpoints:

- Frontend: `http://localhost:3000/api/health`
- Backend: `http://localhost:8000/api/v1/health/live`

Stop the containers started by this profile with:

```bash
docker compose down
```
````

Run:

```bash
cp .env.example .env
docker compose config --quiet
docker compose build
docker compose up --wait
curl --fail http://localhost:8000/api/v1/health/live
curl --fail http://localhost:3000/api/health
docker compose down
```

Expected: all images build, migration completes, services become healthy, and both requests return `{"status":"ok"}`.

- [x] **Step 6: Commit the Docker profile**

```bash
git add .env.example docker-compose.yml backend/Dockerfile frontend/Dockerfile deploy/docker
git commit -m "feat(deploy): add Docker deployment profile"
```

## Task 8: Add the Vercel deployment profile

**Files:**

- Create: `backend/vercel.json`
- Create: `backend/tests/test_vercel_config.py`
- Create: `deploy/vercel/README.md`

- [x] **Step 1: Write a failing Vercel configuration test**

Create `backend/tests/test_vercel_config.py`:

```python
import json
from pathlib import Path

from fastapi import FastAPI

from app.app import app


def test_vercel_entrypoint_exports_fastapi_app() -> None:
    assert isinstance(app, FastAPI)


def test_vercel_bundle_excludes_tests() -> None:
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "vercel.json").read_text())
    function = config["functions"]["app/app.py"]

    assert "tests/**" in function["excludeFiles"]
    assert function["maxDuration"] == 300
```

- [x] **Step 2: Run the test to verify failure**

Run:

```bash
cd backend
uv run pytest tests/test_vercel_config.py -v
```

Expected: the entry-point assertion passes and the configuration assertion fails because `vercel.json` is absent.

- [x] **Step 3: Add the Vercel function configuration**

Create `backend/vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": {
    "app/app.py": {
      "excludeFiles": "{tests/**,app/ingestion/**,data/**,**/__pycache__/**}",
      "maxDuration": 300
    }
  }
}
```

- [x] **Step 4: Document the two-project layout**

Create `deploy/vercel/README.md`:

````markdown
# Vercel deployment profile

Create two Vercel Projects from this Git repository:

| Project | Root directory | Framework |
|---|---|---|
| `equity-research-web` | `frontend` | Next.js |
| `equity-research-api` | `backend` | FastAPI |

Set the backend environment variables from the approved Vercel profile:

```dotenv
DEPLOYMENT_TARGET=vercel
OBJECT_STORAGE_PROVIDER=vercel_blob
JOB_BACKEND=vercel_workflow
DOCUMENT_PARSER=managed
```

Add `DATABASE_URL`, `SECRET_KEY_ACCESS_API`, OpenAI credentials, Vercel Blob credentials, and managed-parser credentials through Vercel Environment Variables.

Pull project settings and run local builds with Vercel CLI 48.1.8 or newer:

```bash
pnpm dlx vercel@latest pull --cwd frontend --yes --environment=preview
pnpm dlx vercel@latest build --cwd frontend
pnpm dlx vercel@latest pull --cwd backend --yes --environment=preview
pnpm dlx vercel@latest build --cwd backend
```
````

- [ ] **Step 5: Verify the Vercel profile**

Local configuration tests pass with Vercel CLI 55.0.0. Both builds require
project settings from the user's linked Vercel frontend and backend Projects.

Run:

```bash
cd backend
uv run pytest tests/test_vercel_config.py -v
cd ..
pnpm dlx vercel@latest pull --cwd frontend --yes --environment=preview
pnpm dlx vercel@latest build --cwd frontend
pnpm dlx vercel@latest pull --cwd backend --yes --environment=preview
pnpm dlx vercel@latest build --cwd backend
```

Expected: configuration tests pass and both Vercel builds complete. Account authentication and project linking happen through the Vercel account session.

- [x] **Step 6: Commit the Vercel profile**

```bash
git add backend/vercel.json backend/tests/test_vercel_config.py deploy/vercel
git commit -m "feat(deploy): add Vercel deployment profile"
```

## Task 9: Add shared smoke verification and operator documentation

**Files:**

- Create: `scripts/smoke.sh`
- Modify: `README.md`

- [ ] **Step 1: Create the shared smoke script**

Create `scripts/smoke.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

WEB_BASE_URL="${WEB_BASE_URL:-http://localhost:3000}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

web_response="$(curl --fail --silent --show-error "${WEB_BASE_URL}/api/health")"
api_response="$(curl --fail --silent --show-error "${API_BASE_URL}/api/v1/health/live")"

test "${web_response}" = '{"status":"ok"}'
test "${api_response}" = '{"status":"ok"}'

echo "Smoke checks passed for ${WEB_BASE_URL} and ${API_BASE_URL}"
```

Make it executable:

```bash
chmod +x scripts/smoke.sh
```

- [ ] **Step 2: Replace the README setup section**

Write the repository README with these sections and commands:

````markdown
# US Equity Research Knowledge Base

This repository contains a Next.js frontend, FastAPI backend, PostgreSQL/pgvector database, and asynchronous document-processing foundation for US equity research.

## Runtime profiles

- Vercel: `frontend/` and `backend/` deploy as two Vercel Projects.
- Docker: Next.js, FastAPI, RQ, PostgreSQL/pgvector, Redis, and MinIO run through Compose.

## Backend development

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn app.app:app --reload
```

## Frontend development

```bash
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm test
pnpm dev
```

## Docker profile

```bash
cp .env.example .env
docker compose build
docker compose up --wait
./scripts/smoke.sh
```

## Vercel profile

See `deploy/vercel/README.md` for the two-project configuration and Preview build commands.

## Quality checks

```bash
cd backend && uv run pytest --cov=app.core.config --cov=app.providers --cov=app.api.routes.health --cov=app.main --cov-report=term-missing && uv run ruff check app/app.py app/main.py app/core/config.py app/providers app/api/deps.py app/api/main.py app/api/routes/health.py app/migrations tests
cd frontend && pnpm test && pnpm lint && pnpm build
git diff --check
```
````

- [ ] **Step 3: Run the complete local quality gate**

Run:

```bash
cd backend
uv run pytest --cov=app.core.config --cov=app.providers --cov=app.api.routes.health --cov=app.main --cov-report=term-missing
uv run ruff check app/app.py app/main.py app/core/config.py app/providers app/api/deps.py app/api/main.py app/api/routes/health.py app/migrations tests
cd ../frontend
pnpm test
pnpm lint
pnpm build
cd ..
docker compose config --quiet
docker compose build
docker compose up --wait
./scripts/smoke.sh
docker compose down
git diff --check
```

Expected:

- backend tests pass with at least 80% statement and branch coverage;
- Ruff reports no violations;
- frontend tests, lint, and production build pass;
- Docker services become healthy and smoke checks pass; and
- Git reports no whitespace errors.

- [ ] **Step 4: Run the Vercel Preview smoke gate**

Deploy both projects and pass their returned Preview URLs to the smoke script:

```bash
WEB_PREVIEW_URL="$(pnpm dlx vercel@latest deploy --cwd frontend --yes)"
API_PREVIEW_URL="$(pnpm dlx vercel@latest deploy --cwd backend --yes)"
WEB_BASE_URL="${WEB_PREVIEW_URL}" \
API_BASE_URL="${API_PREVIEW_URL}" \
./scripts/smoke.sh
```

Expected: the script reports both Preview URLs as healthy. Record the actual Preview URLs in the delivery note.

- [ ] **Step 5: Commit operator documentation and smoke checks**

```bash
git add README.md scripts/smoke.sh
git commit -m "docs: document dual-deployment workflows"
```

## Task 10: Perform Phase 0 completion verification

**Files:**

- Verify: all files changed by Tasks 1–9
- Update: this plan's checkboxes while execution proceeds

- [ ] **Step 1: Verify repository state and migration head**

Run:

```bash
git status --short
cd backend
uv lock --check
uv run alembic heads
uv run pytest --cov=app.core.config --cov=app.providers --cov=app.api.routes.health --cov=app.main --cov-report=term-missing
uv run ruff check app/app.py app/main.py app/core/config.py app/providers app/api/deps.py app/api/main.py app/api/routes/health.py app/migrations tests
```

Expected: the lock is current, Alembic reports `20260713_0001 (head)`, tests pass at the coverage threshold, and Ruff reports no violations.

- [ ] **Step 2: Verify the frontend artifact**

Run:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm test
pnpm lint
pnpm build
test -f .next/standalone/server.js
```

Expected: every command exits `0` and the standalone server exists.

- [ ] **Step 3: Verify both deployment profiles**

Run the Docker commands from Task 9 and the two Vercel build commands from Task 8. Then run `scripts/smoke.sh` once against Docker and once against the actual Vercel Preview URLs.

Expected: both profiles satisfy the same health contract.

- [ ] **Step 4: Check the final diff**

Run:

```bash
git diff --check
git status --short
git log --oneline -10
```

Expected: no whitespace errors; the status contains only intentional Phase 0 changes; the log contains the task-level commits listed above.

## Phase 0 exit criteria

- Python 3.12 and Node.js 22 are pinned.
- Backend dependencies resolve from `uv.lock`; Vercel installs only API dependencies and Docker can install the worker group.
- Deployment/provider combinations are validated at startup.
- FastAPI and Next.js expose stable health endpoints with unit tests.
- Alembic has one initial migration head and creates the pgvector extension.
- Backend tests and frontend tests exist and pass their configured gates.
- The Next.js standalone artifact builds successfully.
- Docker Compose reaches healthy status and passes shared smoke checks.
- Both Vercel projects build and their Preview URLs pass the same shared smoke checks.
- Phase 1 can begin from a reproducible dual-deployment baseline.

## Source references

- [Next.js App Router installation](https://nextjs.org/docs/app/getting-started/installation)
- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vercel Python Runtime](https://vercel.com/docs/functions/runtimes/python)
- [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
- [pgvector Docker images](https://github.com/pgvector/pgvector#docker)
- [MinIO container deployment](https://min.io/docs/minio/container/index.html)
