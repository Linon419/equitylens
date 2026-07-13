# Phase 1 Google Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Google-only sign-in, rotating EquityLens sessions, protected bilingual pages, locale preferences, and logout across Vercel and Docker profiles.

**Architecture:** Google Identity Services returns an ID-token credential to the React login page. The Next.js BFF validates same-origin CSRF state, forwards the credential to FastAPI, stores EquityLens access and refresh tokens in HttpOnly cookies, and proxies authenticated calls. FastAPI validates Google identity, owns users and sessions in PostgreSQL, rotates opaque refresh tokens, and authorizes private resources.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Alembic, PostgreSQL, python-jose, google-auth, pytest, Next.js 16 App Router, React 19, TypeScript 5.9, Vitest, React Testing Library, Playwright, pnpm, Docker Compose, Vercel.

---

## Scope and execution prerequisites

This plan implements the approved specification at `docs/superpowers/specs/2026-07-13-phase-1-google-authentication-design.md`.

Execution requires:

- a Google Cloud OAuth web client ID for manual verification;
- Node.js 22 with Corepack and pnpm 11;
- Python 3.12 with uv;
- PostgreSQL for migration and integration verification; and
- Docker Compose for the final Docker-profile smoke test.

The verified starting point on 2026-07-13 is:

```text
backend: 21 passed
frontend: 6 files, 10 tests passed
```

The existing integer `User.id` remains stable. `ExternalIdentity.id`, `AuthSession.id`, and `AuthSession.token_family_id` use UUIDs. The legacy password route remains in the repository and leaves the mounted API surface.

## File map

### Backend configuration and persistence

- Modify `backend/pyproject.toml`: add the official Google token-verification dependency.
- Modify `backend/uv.lock`: lock the new dependency.
- Modify `backend/.env.example`, `.env.example`, and `docker-compose.yml`: document and inject authentication settings.
- Modify `backend/app/core/config.py`: add Google, token lifetime, and refresh-grace settings.
- Modify `backend/tests/conftest.py` and `backend/tests/core/test_config.py`: supply deterministic auth settings.
- Create `backend/tests/core/test_auth_config.py`: validate authentication configuration.
- Modify `backend/app/models/user_model.py`: add user profile, locale, and audit fields; make the legacy password hash nullable.
- Create `backend/app/models/auth_model.py`: define Google identities and refresh-session token versions.
- Modify `backend/app/models/__init__.py` and `backend/app/migrations/env.py`: register authentication metadata.
- Create `backend/app/migrations/versions/20260713_0002_google_auth.py`: migrate the schema safely.
- Modify `backend/tests/test_migrations.py`: assert the new migration head.
- Create `backend/tests/models/test_auth_models.py`: verify model constraints and field types.

### Backend authentication domain and API

- Modify `backend/app/core/security.py`: issue and decode access tokens; create, parse, and hash opaque refresh tokens.
- Create `backend/app/auth/__init__.py`: expose authentication domain types.
- Create `backend/app/auth/contracts.py`: define verified Google identity and verifier protocol.
- Create `backend/app/auth/errors.py`: define stable authentication exceptions.
- Create `backend/app/auth/google.py`: adapt the official Google verifier.
- Create `backend/app/auth/session_service.py`: create, rotate, and revoke session families.
- Create `backend/app/auth/account_service.py`: resolve Google identities and create/update users.
- Create `backend/app/schemas/auth_schema.py`: define API request and response models.
- Modify `backend/app/api/deps.py`: replace the password bearer dependency and inject the Google verifier.
- Create `backend/app/api/routes/auth.py`: expose Google, refresh, logout, current-user, and preference routes.
- Modify `backend/app/api/main.py`: mount `/auth` and retire the password route from the API surface.
- Modify `backend/app/main.py`: add request IDs and the stable auth-error response handler.
- Modify `backend/app/crud/user_crud.py`: handle nullable legacy password hashes safely.
- Create `backend/tests/auth/conftest.py`: build an isolated authentication test database and fake Google verifier.
- Create `backend/tests/auth/test_security.py`: test token primitives.
- Create `backend/tests/auth/test_google.py`: test Google claim normalization.
- Create `backend/tests/auth/test_account_service.py`: test identity and user behavior.
- Create `backend/tests/auth/test_session_service.py`: test rotation, expiry, replay, and logout.
- Create `backend/tests/api/test_auth.py`: test the public authentication contract.

### Next.js BFF and interface

- Create `frontend/.env.example`: document browser and server authentication settings.
- Create `frontend/src/lib/auth/types.ts`: share BFF authentication types.
- Create `frontend/src/lib/auth/config.ts`: validate runtime authentication configuration.
- Create `frontend/src/lib/auth/cookies.ts`: set and clear HttpOnly session cookies.
- Create `frontend/src/lib/auth/backend.ts`: call FastAPI and perform one refresh-and-retry cycle.
- Create `frontend/src/lib/auth/security.ts`: validate origin, CSRF, locale, and return paths.
- Create `frontend/src/app/api/auth/csrf/route.ts`: issue login CSRF state.
- Create `frontend/src/app/api/auth/google/callback/route.ts`: exchange Google credentials for an EquityLens session.
- Create `frontend/src/app/api/auth/me/route.ts`: resolve and refresh the current session.
- Create `frontend/src/app/api/auth/refresh/route.ts`: expose explicit refresh.
- Create `frontend/src/app/api/auth/logout/route.ts`: revoke and clear the session.
- Create `frontend/src/app/api/auth/preferences/route.ts`: persist locale changes.
- Create route and library unit tests beside each BFF module.
- Create `frontend/src/types/google-identity.d.ts`: type the official Google browser API.
- Create `frontend/src/components/google-sign-in-button.tsx`: render and handle Google sign-in.
- Create `frontend/src/app/[lang]/login/page.tsx`: render the localized login experience.
- Create `frontend/src/components/session-provider.tsx`: resolve the current user and protect the app shell.
- Create `frontend/src/components/app-shell.tsx`: render authenticated navigation and logout.
- Create `frontend/src/app/[lang]/(app)/layout.tsx`: protect dashboard and settings.
- Create `frontend/src/app/[lang]/(app)/dashboard/page.tsx`: provide the authenticated Phase 1 dashboard shell.
- Create `frontend/src/app/[lang]/(app)/settings/page.tsx`: provide language settings.
- Modify `frontend/src/components/language-switcher.tsx`: synchronize authenticated locale changes.
- Modify `frontend/src/dictionaries/index.ts`: add bilingual authentication and app-shell copy.
- Modify `frontend/src/app/[lang]/page.tsx`: link the primary action to login.
- Modify `frontend/src/app/globals.css`: style login and protected pages in the existing visual system.

### End-to-end and delivery verification

- Modify `frontend/package.json` and `frontend/pnpm-lock.yaml`: add Playwright and the `test:e2e` script.
- Create `frontend/playwright.config.ts`: run the test-only FastAPI app and Next.js together.
- Create `backend/tests/e2e_app.py`: inject a deterministic Google verifier and isolated SQLite database.
- Create `frontend/e2e/auth.spec.ts`: verify sign-in, protection, locale persistence, refresh, and logout.
- Modify `README.md` and deployment guides: document Google Cloud, Vercel, Docker, and local settings.

## Task 1: Add authentication dependencies and configuration

**Files:**

- Modify: `backend/pyproject.toml:7-27`
- Modify: `backend/uv.lock`
- Modify: `backend/app/core/config.py:43-76`
- Modify: `backend/tests/conftest.py:3-24`
- Modify: `backend/tests/core/test_config.py:5-29`
- Create: `backend/tests/core/test_auth_config.py`
- Modify: `backend/.env.example`
- Modify: `.env.example`
- Create: `frontend/.env.example`
- Modify: `docker-compose.yml:82-90`
- Modify: `backend/tests/test_docker_profile.py`

- [ ] **Step 1: Write failing authentication configuration tests**

Create `backend/tests/core/test_auth_config.py`:

```python
from app.core.config import Settings


def test_authentication_defaults_are_short_lived() -> None:
    settings = Settings()

    assert settings.GOOGLE_CLIENT_ID == "test-google-client-id"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
    assert settings.REFRESH_REUSE_GRACE_SECONDS == 10
    assert settings.FRONTEND_URL == "http://localhost:3000"
```

Add these entries to `TEST_ENV` in `backend/tests/conftest.py`:

```python
"GOOGLE_CLIENT_ID": "test-google-client-id",
"FRONTEND_URL": "http://localhost:3000",
```

Add `"GOOGLE_CLIENT_ID": "test-google-client-id"` and `"FRONTEND_URL": "http://localhost:3000"` to `BASE` in `backend/tests/core/test_config.py`.

Extend `test_environment_template_contains_placeholders_only` in `backend/tests/test_docker_profile.py`:

```python
assert "GOOGLE_CLIENT_ID=replace-with-google-client-id" in template
assert "BACKEND_URL=http://api:8000" in template
assert "NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id" in template
```

- [ ] **Step 2: Run the targeted tests and verify the failure**

Run:

```bash
cd backend
uv run pytest tests/core/test_auth_config.py tests/core/test_config.py tests/test_docker_profile.py -q
```

Expected: FAIL because `Settings` lacks Google and refresh-session fields and the environment templates lack the new keys.

- [ ] **Step 3: Add the backend dependency and settings**

Add this project dependency in `backend/pyproject.toml`:

```toml
"google-auth[requests]>=2.40,<3",
```

Add these fields after `CORS_ORIGINS` in `Settings`:

```python
FRONTEND_URL: str = "http://localhost:3000"
GOOGLE_CLIENT_ID: str
```

Replace the existing access-token lifetime with:

```python
ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
REFRESH_TOKEN_EXPIRE_DAYS: int = 30
REFRESH_REUSE_GRACE_SECONDS: int = 10
```

Run:

```bash
cd backend
uv lock
uv sync --frozen
uv lock --check
```

Expected: `google-auth` and its HTTP transport dependencies are locked and the lock check exits `0`.

- [ ] **Step 4: Add deployable environment templates**

Append to both `.env.example` and `backend/.env.example`:

```dotenv
GOOGLE_CLIENT_ID=replace-with-google-client-id
FRONTEND_URL=http://localhost:3000
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
REFRESH_REUSE_GRACE_SECONDS=10
```

Create `frontend/.env.example`:

```dotenv
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id
COOKIE_SECURE=false
```

Add to the root `.env.example`:

```dotenv
BACKEND_URL=http://api:8000
NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id
COOKIE_SECURE=false
```

Replace the `web.environment` block in `docker-compose.yml` with:

```yaml
environment:
  BACKEND_URL: ${BACKEND_URL:-http://api:8000}
  FRONTEND_URL: ${FRONTEND_URL:-http://localhost:3000}
  NEXT_PUBLIC_GOOGLE_CLIENT_ID: ${NEXT_PUBLIC_GOOGLE_CLIENT_ID}
  COOKIE_SECURE: ${COOKIE_SECURE:-false}
```

- [ ] **Step 5: Run configuration regression tests**

Run:

```bash
cd backend
uv run pytest tests/core/test_auth_config.py tests/core/test_config.py tests/test_docker_profile.py -q
uv run ruff check app/core/config.py tests/core/test_auth_config.py tests/core/test_config.py
```

Expected: all selected tests pass and Ruff reports success.

- [ ] **Step 6: Commit authentication configuration**

```bash
git add .env.example docker-compose.yml backend/.env.example backend/pyproject.toml backend/uv.lock backend/app/core/config.py backend/tests/conftest.py backend/tests/core/test_config.py backend/tests/core/test_auth_config.py backend/tests/test_docker_profile.py frontend/.env.example
git commit -m "feat(auth): configure Google authentication"
```

## Task 2: Add identity and session persistence

**Files:**

- Modify: `backend/app/models/user_model.py:1-57`
- Create: `backend/app/models/auth_model.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/migrations/env.py:8-9`
- Create: `backend/app/migrations/versions/20260713_0002_google_auth.py`
- Modify: `backend/tests/test_migrations.py`
- Create: `backend/tests/models/test_auth_models.py`

- [ ] **Step 1: Write failing model and migration tests**

Create `backend/tests/models/test_auth_models.py`:

```python
from app.models.auth_model import AuthSession, ExternalIdentity
from app.models.user_model import User


def test_google_auth_models_preserve_integer_user_ids() -> None:
    assert User.model_fields["id"].annotation == int | None
    assert ExternalIdentity.model_fields["user_id"].annotation is int
    assert AuthSession.model_fields["user_id"].annotation is int


def test_federated_user_fields_exist() -> None:
    assert User.model_fields["hashed_password"].is_required() is False
    assert User.model_fields["preferred_locale"].default == "en-US"
    assert "avatar_url" in User.model_fields
    assert "created_at" in User.model_fields
    assert "updated_at" in User.model_fields


def test_identity_and_session_constraints_are_named() -> None:
    identity_constraints = {
        constraint.name for constraint in ExternalIdentity.__table__.constraints
    }
    session_indexes = {index.name for index in AuthSession.__table__.indexes}

    assert "uq_external_identity_provider_subject" in identity_constraints
    assert "uq_external_identity_user_provider" in identity_constraints
    assert "ix_auth_session_token_family_id" in session_indexes
```

Change the expected head in `backend/tests/test_migrations.py`:

```python
assert scripts.get_heads() == ["20260713_0002"]
```

- [ ] **Step 2: Run the tests and verify the failure**

Run:

```bash
cd backend
uv run pytest tests/models/test_auth_models.py tests/test_migrations.py -q
```

Expected: FAIL because the auth models and migration revision do not exist.

- [ ] **Step 3: Extend the user model**

Add imports and a UTC helper at the top of `backend/app/models/user_model.py`:

```python
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)
```

Replace `UserBase` and `User` with:

```python
class UserBase(SQLModel):
    email: str = Field(unique=True, index=True)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = None
    avatar_url: str | None = None
    preferred_locale: str = Field(default="en-US", max_length=5)


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    hashed_password: str | None = None
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    items: list["Item"] = Relationship(back_populates="owner")
```

Keep the legacy request and item models unchanged. Add `avatar_url`, `preferred_locale`, `created_at`, and `updated_at` to the public `UserOut` contract through its inheritance from `UserBase` and explicit fields:

```python
class UserOut(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: Create focused authentication models**

Create `backend/app/models/auth_model.py`:

```python
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class ExternalIdentity(SQLModel, table=True):
    __tablename__ = "external_identity"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_external_identity_provider_subject",
        ),
        UniqueConstraint(
            "user_id",
            "provider",
            name="uq_external_identity_user_provider",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    provider: str = Field(max_length=32)
    provider_subject: str = Field(max_length=255)
    provider_email: str = Field(max_length=320)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_login_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_session"
    __table_args__ = (
        Index("ix_auth_session_token_family_id", "token_family_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(max_length=64)
    token_family_id: UUID = Field(default_factory=uuid4)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    rotated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    replaced_by_id: UUID | None = Field(
        default=None,
        foreign_key="auth_session.id",
    )
```

Export both models from `backend/app/models/__init__.py`:

```python
from app.models.auth_model import AuthSession, ExternalIdentity
from app.models.user_model import Item, User

__all__ = ["AuthSession", "ExternalIdentity", "Item", "User"]
```

Replace the model import in `backend/app/migrations/env.py` with:

```python
from app.models import auth_model, user_model  # noqa: F401
```

- [ ] **Step 5: Create the Alembic migration**

Create `backend/app/migrations/versions/20260713_0002_google_auth.py`:

```python
"""Add Google identities and rotating authentication sessions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_0002"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=True)
    op.add_column("user", sa.Column("avatar_url", sa.String(), nullable=True))
    op.add_column(
        "user",
        sa.Column("preferred_locale", sa.String(length=5), server_default="en-US", nullable=False),
    )
    op.add_column(
        "user",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "user",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_check_constraint(
        "ck_user_preferred_locale",
        "user",
        "preferred_locale IN ('en-US', 'zh-CN')",
    )

    op.create_table(
        "external_identity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_subject", name="uq_external_identity_provider_subject"
        ),
        sa.UniqueConstraint(
            "user_id", "provider", name="uq_external_identity_user_provider"
        ),
    )
    op.create_index("ix_external_identity_user_id", "external_identity", ["user_id"])

    op.create_table(
        "auth_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["auth_session.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])
    op.create_index(
        "ix_auth_session_token_family_id", "auth_session", ["token_family_id"]
    )


def downgrade() -> None:
    null_passwords = op.get_bind().execute(
        sa.text('SELECT count(*) FROM "user" WHERE hashed_password IS NULL')
    ).scalar_one()
    if null_passwords:
        raise RuntimeError(
            "Link or remove federated users before downgrading authentication schema"
        )
    op.drop_index("ix_auth_session_token_family_id", table_name="auth_session")
    op.drop_index("ix_auth_session_user_id", table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_index("ix_external_identity_user_id", table_name="external_identity")
    op.drop_table("external_identity")
    op.drop_constraint("ck_user_preferred_locale", "user", type_="check")
    op.drop_column("user", "updated_at")
    op.drop_column("user", "created_at")
    op.drop_column("user", "preferred_locale")
    op.drop_column("user", "avatar_url")
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=False)
```

- [ ] **Step 6: Run model and migration checks**

Run:

```bash
cd backend
uv run pytest tests/models/test_auth_models.py tests/test_migrations.py -q
uv run ruff check app/models app/migrations/versions/20260713_0002_google_auth.py tests/models/test_auth_models.py
uv run alembic heads
```

Expected: tests pass, Ruff succeeds, and Alembic prints `20260713_0002 (head)`.

- [ ] **Step 7: Commit the authentication schema**

```bash
git add backend/app/models backend/app/migrations/env.py backend/app/migrations/versions/20260713_0002_google_auth.py backend/tests/models/test_auth_models.py backend/tests/test_migrations.py
git commit -m "feat(auth): add identity and session schema"
```

## Task 3: Implement access and refresh token primitives

**Files:**

- Modify: `backend/app/core/security.py`
- Modify: `backend/app/api/main.py`
- Create: `backend/tests/auth/test_security.py`

- [ ] **Step 1: Write failing token primitive tests**

Create `backend/tests/auth/test_security.py`:

```python
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    parse_refresh_token,
)


def test_access_token_contains_user_session_and_type() -> None:
    family_id = uuid4()
    now = datetime(2026, 7, 13, tzinfo=UTC)

    token = create_access_token(42, family_id, now=now)
    claims = decode_access_token(token)

    assert claims.user_id == 42
    assert claims.session_id == family_id
    assert claims.token_type == "access"


def test_refresh_token_round_trips_record_id_and_hash() -> None:
    record_id = uuid4()

    raw_token, token_hash = create_refresh_token(record_id)
    parsed = parse_refresh_token(raw_token)

    assert parsed.record_id == record_id
    assert parsed.token_hash == token_hash


def test_access_token_rejects_wrong_type() -> None:
    family_id = uuid4()
    token = create_access_token(42, family_id, now=datetime.now(UTC))
    payload = token.rsplit(".", 1)

    with pytest.raises((JWTError, ValueError)):
        decode_access_token(".".join([payload[0], "invalid-signature"]))


def test_access_token_rejects_expired_claims() -> None:
    token = create_access_token(
        42,
        uuid4(),
        now=datetime.now(UTC) - timedelta(hours=2),
        expires_delta=timedelta(minutes=1),
    )

    with pytest.raises(JWTError):
        decode_access_token(token)
```

- [ ] **Step 2: Run the tests and verify the failure**

Run:

```bash
cd backend
uv run pytest tests/auth/test_security.py -q
```

Expected: FAIL because session-aware access-token and refresh-token functions are missing.

- [ ] **Step 3: Replace the token portion of the security module**

Keep the existing password hashing helpers and replace the access-token implementation in `backend/app/core/security.py` with:

```python
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    session_id: UUID
    token_type: str


@dataclass(frozen=True)
class RefreshTokenParts:
    record_id: UUID
    token_hash: str


def create_access_token(
    user_id: int,
    session_id: UUID,
    *,
    now: datetime | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    lifetime = expires_delta or timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "type": "access",
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + lifetime).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY_ACCESS_API, algorithm=ALGORITHM)


def decode_access_token(token: str) -> AccessTokenClaims:
    payload = jwt.decode(
        token,
        settings.SECRET_KEY_ACCESS_API,
        algorithms=[ALGORITHM],
    )
    if payload.get("type") != "access":
        raise JWTError("Unexpected token type")
    return AccessTokenClaims(
        user_id=int(payload["sub"]),
        session_id=UUID(payload["sid"]),
        token_type=payload["type"],
    )


def create_refresh_token(record_id: UUID) -> tuple[str, str]:
    raw_token = f"{record_id}.{token_urlsafe(48)}"
    return raw_token, hash_refresh_token(raw_token)


def hash_refresh_token(raw_token: str) -> str:
    return sha256(raw_token.encode("utf-8")).hexdigest()


def parse_refresh_token(raw_token: str) -> RefreshTokenParts:
    record_text, separator, secret = raw_token.partition(".")
    if separator != "." or not secret:
        raise ValueError("Malformed refresh token")
    return RefreshTokenParts(
        record_id=UUID(record_text),
        token_hash=hash_refresh_token(raw_token),
    )
```

Keep `verify_password` and `get_password_hash` below these functions. Replace `backend/app/api/main.py` at the same time so the legacy password route cannot call the retired token signature:

```python
from fastapi import APIRouter

from app.api.routes import health, qa

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(qa.router, prefix="/qa", tags=["qa"])
```

- [ ] **Step 4: Run token tests and lint**

Run:

```bash
cd backend
uv run pytest tests/auth/test_security.py -q
uv run ruff check app/core/security.py tests/auth/test_security.py
```

Expected: all token tests pass and Ruff succeeds.

- [ ] **Step 5: Commit token primitives**

```bash
git add backend/app/core/security.py backend/app/api/main.py backend/tests/auth/test_security.py
git commit -m "feat(auth): add session token primitives"
```

## Task 4: Verify Google identity claims through an adapter

**Files:**

- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/contracts.py`
- Create: `backend/app/auth/errors.py`
- Create: `backend/app/auth/google.py`
- Create: `backend/tests/auth/test_google.py`

- [ ] **Step 1: Write failing Google-verifier tests**

Create `backend/tests/auth/test_google.py`:

```python
import pytest

from app.auth.errors import AuthError
from app.auth.google import GoogleTokenVerifier


def test_google_verifier_normalizes_required_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.auth.google.google_id_token.verify_oauth2_token",
        lambda credential, request, audience: {
            "sub": "google-sub-1",
            "email": "investor@example.com",
            "email_verified": True,
            "name": "Investor One",
            "picture": "https://example.com/avatar.png",
        },
    )

    identity = GoogleTokenVerifier("client-id").verify("credential")

    assert identity.subject == "google-sub-1"
    assert identity.email == "investor@example.com"
    assert identity.full_name == "Investor One"
    assert identity.picture == "https://example.com/avatar.png"


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"sub": "sub", "email": "a@example.com", "email_verified": False},
    ],
)
def test_google_verifier_rejects_incomplete_identity(
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, object],
) -> None:
    monkeypatch.setattr(
        "app.auth.google.google_id_token.verify_oauth2_token",
        lambda credential, request, audience: claims,
    )

    with pytest.raises(AuthError, match="AUTH_INVALID_GOOGLE_TOKEN"):
        GoogleTokenVerifier("client-id").verify("credential")


def test_google_verifier_maps_library_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(credential, request, audience):
        raise ValueError("wrong audience")

    monkeypatch.setattr(
        "app.auth.google.google_id_token.verify_oauth2_token",
        reject,
    )
    with pytest.raises(AuthError, match="AUTH_INVALID_GOOGLE_TOKEN"):
        GoogleTokenVerifier("client-id").verify("credential")
```

- [ ] **Step 2: Run the test and verify the failure**

Run:

```bash
cd backend
uv run pytest tests/auth/test_google.py -q
```

Expected: FAIL because the authentication adapter package does not exist.

- [ ] **Step 3: Define stable domain contracts and errors**

Create `backend/app/auth/contracts.py`:

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    full_name: str | None
    picture: str | None


class GoogleVerifier(Protocol):
    def verify(self, credential: str) -> GoogleIdentity: ...
```

Create `backend/app/auth/errors.py`:

```python
class AuthError(Exception):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
```

Create `backend/app/auth/__init__.py`:

```python
from app.auth.contracts import GoogleIdentity, GoogleVerifier
from app.auth.errors import AuthError

__all__ = ["AuthError", "GoogleIdentity", "GoogleVerifier"]
```

- [ ] **Step 4: Implement the official Google verifier adapter**

Create `backend/app/auth/google.py`:

```python
from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token

from app.auth.contracts import GoogleIdentity
from app.auth.errors import AuthError


class GoogleTokenVerifier:
    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.request = Request()

    def verify(self, credential: str) -> GoogleIdentity:
        try:
            claims = google_id_token.verify_oauth2_token(
                credential,
                self.request,
                self.client_id,
            )
        except ValueError as error:
            raise AuthError("AUTH_INVALID_GOOGLE_TOKEN", 401) from error

        subject = claims.get("sub")
        email = claims.get("email")
        email_verified = claims.get("email_verified") is True
        if not subject or not email or not email_verified:
            raise AuthError("AUTH_INVALID_GOOGLE_TOKEN", 401)

        return GoogleIdentity(
            subject=str(subject),
            email=str(email).lower(),
            email_verified=True,
            full_name=str(claims["name"]) if claims.get("name") else None,
            picture=str(claims["picture"]) if claims.get("picture") else None,
        )
```

- [ ] **Step 5: Run adapter tests and lint**

Run:

```bash
cd backend
uv run pytest tests/auth/test_google.py -q
uv run ruff check app/auth tests/auth/test_google.py
```

Expected: all Google-verifier tests pass and Ruff succeeds.

- [ ] **Step 6: Commit the Google adapter**

```bash
git add backend/app/auth backend/tests/auth/test_google.py
git commit -m "feat(auth): verify Google identity tokens"
```

## Task 5: Implement rotating session families

**Files:**

- Create: `backend/app/auth/session_service.py`
- Create: `backend/tests/auth/conftest.py`
- Create: `backend/tests/auth/test_session_service.py`

- [ ] **Step 1: Create an isolated authentication database fixture**

Create `backend/tests/auth/conftest.py`:

```python
from collections.abc import Generator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import auth_model, user_model  # noqa: F401


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)
```

- [ ] **Step 2: Write failing session lifecycle tests**

Create `backend/tests/auth/test_session_service.py`:

```python
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


def test_refresh_rotates_token_and_preserves_family(db_session: Session) -> None:
    user = create_user(db_session)
    now = datetime(2026, 7, 13, tzinfo=UTC)
    first = issue_session(db_session, user.id, now=now)
    db_session.commit()

    second = refresh_session(db_session, first.refresh_token, now=now + timedelta(minutes=1))

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

    with pytest.raises(AuthError, match="AUTH_REFRESH_STALE"):
        refresh_session(db_session, first.refresh_token, now=now + timedelta(seconds=5))


def test_replay_after_grace_revokes_family(db_session: Session) -> None:
    user = create_user(db_session)
    now = datetime(2026, 7, 13, tzinfo=UTC)
    first = issue_session(db_session, user.id, now=now)
    db_session.commit()
    refresh_session(db_session, first.refresh_token, now=now + timedelta(seconds=1))

    with pytest.raises(AuthError, match="AUTH_SESSION_REUSED"):
        refresh_session(db_session, first.refresh_token, now=now + timedelta(seconds=12))

    records = db_session.exec(
        select(AuthSession).where(AuthSession.token_family_id == first.token_family_id)
    ).all()
    assert all(record.revoked_at is not None for record in records)


def test_logout_revokes_complete_family(db_session: Session) -> None:
    user = create_user(db_session)
    issued = issue_session(db_session, user.id)
    db_session.commit()

    revoke_session(db_session, issued.refresh_token)

    records = db_session.exec(
        select(AuthSession).where(AuthSession.token_family_id == issued.token_family_id)
    ).all()
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
```

- [ ] **Step 3: Run the tests and verify the failure**

Run:

```bash
cd backend
uv run pytest tests/auth/test_session_service.py -q
```

Expected: FAIL because `session_service` does not exist.

- [ ] **Step 4: Implement transactional session rotation**

Create `backend/app/auth/session_service.py`:

```python
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlmodel import Session, select

from app.auth.errors import AuthError
from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, parse_refresh_token
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
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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
        access_token=create_access_token(user_id, token_family_id, now=issued_at),
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
        select(AuthSession)
        .where(AuthSession.id == parts.record_id)
        .with_for_update()
    )
    record = session.exec(statement).one_or_none()
    if record is None or not hmac.compare_digest(record.token_hash, parts.token_hash):
        raise AuthError("AUTH_SESSION_EXPIRED", 401)
    if record.revoked_at is not None:
        raise AuthError("AUTH_SESSION_EXPIRED", 401)
    if record.rotated_at is not None:
        elapsed = refreshed_at - _utc(record.rotated_at)
        if elapsed <= timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS):
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


def revoke_session(session: Session, raw_token: str, *, now: datetime | None = None) -> None:
    revoked_at = now or datetime.now(UTC)
    try:
        parts = parse_refresh_token(raw_token)
    except ValueError:
        return
    record = session.exec(
        select(AuthSession)
        .where(AuthSession.id == parts.record_id)
        .with_for_update()
    ).one_or_none()
    if record is None or not hmac.compare_digest(record.token_hash, parts.token_hash):
        return
    _revoke_family(session, record.token_family_id, revoked_at)
    session.commit()
```

- [ ] **Step 5: Run session tests and lint**

Run:

```bash
cd backend
uv run pytest tests/auth/test_session_service.py -q
uv run ruff check app/auth/session_service.py tests/auth/conftest.py tests/auth/test_session_service.py
```

Expected: four session lifecycle tests pass and Ruff succeeds.

- [ ] **Step 6: Commit session rotation**

```bash
git add backend/app/auth/session_service.py backend/tests/auth/conftest.py backend/tests/auth/test_session_service.py
git commit -m "feat(auth): rotate refresh sessions"
```

## Task 6: Resolve Google accounts into EquityLens users

**Files:**

- Create: `backend/app/auth/account_service.py`
- Create: `backend/tests/auth/test_account_service.py`

- [ ] **Step 1: Write failing account-service tests**

Create `backend/tests/auth/test_account_service.py`:

```python
from sqlmodel import Session, select

from app.auth.account_service import authenticate_google
from app.auth.contracts import GoogleIdentity
from app.auth.errors import AuthError
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


def test_first_google_login_creates_user_identity_and_session(db_session: Session) -> None:
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

    assert second.user.id == first.user.id
    assert second.user.email == "investor@example.com"
    assert second.user.preferred_locale == "zh-CN"
    assert second.user.full_name == "Updated Name"


def test_existing_email_requires_explicit_linking(db_session: Session) -> None:
    db_session.add(User(email=IDENTITY.email, hashed_password="legacy-hash"))
    db_session.commit()

    try:
        authenticate_google(db_session, FakeVerifier(IDENTITY), "credential", "en-US")
    except AuthError as error:
        assert error.code == "AUTH_ACCOUNT_LINK_REQUIRED"
    else:
        raise AssertionError("Expected account-link requirement")
```

- [ ] **Step 2: Run the tests and verify the failure**

Run:

```bash
cd backend
uv run pytest tests/auth/test_account_service.py -q
```

Expected: FAIL because `account_service` does not exist.

- [ ] **Step 3: Implement account resolution**

Create `backend/app/auth/account_service.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.auth.contracts import GoogleVerifier
from app.auth.errors import AuthError
from app.auth.session_service import IssuedTokens, issue_session
from app.models.auth_model import ExternalIdentity
from app.models.user_model import User


@dataclass(frozen=True)
class AuthenticatedAccount:
    user: User
    tokens: IssuedTokens


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

    if identity is not None:
        user = session.get(User, identity.user_id)
        if user is None or not user.is_active:
            raise AuthError("AUTH_ACCOUNT_DISABLED", 403)
        identity.provider_email = google.email
        identity.last_login_at = now
        user.full_name = google.full_name
        user.avatar_url = google.picture
        user.updated_at = now
        session.add(identity)
        session.add(user)
    else:
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
        identity = ExternalIdentity(
            user_id=user.id,
            provider="google",
            provider_subject=google.subject,
            provider_email=google.email,
            created_at=now,
            last_login_at=now,
        )
        session.add(identity)

    tokens = issue_session(session, user.id, now=now)
    session.commit()
    session.refresh(user)
    return AuthenticatedAccount(user=user, tokens=tokens)
```

- [ ] **Step 4: Run account tests and lint**

Run:

```bash
cd backend
uv run pytest tests/auth/test_account_service.py -q
uv run ruff check app/auth/account_service.py tests/auth/test_account_service.py
```

Expected: all account-resolution tests pass and Ruff succeeds.

- [ ] **Step 5: Commit account resolution**

```bash
git add backend/app/auth/account_service.py backend/tests/auth/test_account_service.py
git commit -m "feat(auth): resolve Google user accounts"
```

## Task 7: Expose the FastAPI authentication contract

**Files:**

- Create: `backend/app/schemas/auth_schema.py`
- Modify: `backend/app/api/deps.py`
- Create: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/crud/user_crud.py`
- Create: `backend/tests/api/test_auth.py`

- [ ] **Step 1: Write failing API contract tests**

Create `backend/tests/api/test_auth.py` with a SQLite override and fake verifier:

```python
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


def test_invalid_google_token_has_stable_error_shape() -> None:
    response = build_client().post(
        "/api/v1/auth/google",
        json={"credential": "invalid", "preferred_locale": "en-US"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_INVALID_GOOGLE_TOKEN"
    assert response.json()["request_id"]


def test_legacy_password_route_is_unmounted() -> None:
    response = build_client().post("/api/v1/login/access-token")

    assert response.status_code == 404
```

- [ ] **Step 2: Run the API test and verify the failure**

Run:

```bash
cd backend
uv run pytest tests/api/test_auth.py -q
```

Expected: FAIL because the new schemas, dependencies, error handler, and routes are missing.

- [ ] **Step 3: Define request and response schemas**

Create `backend/app/schemas/auth_schema.py`:

```python
from datetime import datetime
from typing import Literal

from sqlmodel import SQLModel


Locale = Literal["en-US", "zh-CN"]


class GoogleAuthRequest(SQLModel):
    credential: str
    preferred_locale: Locale


class RefreshRequest(SQLModel):
    refresh_token: str


class LogoutRequest(SQLModel):
    refresh_token: str


class PreferencesUpdate(SQLModel):
    preferred_locale: Locale


class UserPublic(SQLModel):
    id: int
    email: str
    full_name: str | None
    avatar_url: str | None
    preferred_locale: Locale
    created_at: datetime


class TokenResponse(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_in: int
    refresh_expires_in: int


class AuthResponse(TokenResponse):
    user: UserPublic
```

- [ ] **Step 4: Replace password bearer dependencies**

Replace `backend/app/api/deps.py` with:

```python
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlmodel import Session, create_engine, select

from app.auth.contracts import GoogleVerifier
from app.auth.errors import AuthError
from app.auth.google import GoogleTokenVerifier
from app.core.config import settings
from app.core.security import decode_access_token
from app.models.auth_model import AuthSession
from app.models.user_model import User

engine = create_engine(settings.SYNC_DATABASE_URI)
bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]


def get_google_verifier() -> GoogleVerifier:
    return GoogleTokenVerifier(settings.GOOGLE_CLIENT_ID)


GoogleVerifierDep = Annotated[GoogleVerifier, Depends(get_google_verifier)]
TokenDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    if token is None:
        raise AuthError("AUTH_REQUIRED", 401)
    try:
        claims = decode_access_token(token.credentials)
    except (JWTError, KeyError, TypeError, ValueError) as error:
        raise AuthError("AUTH_REQUIRED", 401) from error

    active_session = session.exec(
        select(AuthSession.id).where(
            AuthSession.token_family_id == claims.session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    ).first()
    user = session.get(User, claims.user_id)
    if active_session is None or user is None:
        raise AuthError("AUTH_REQUIRED", 401)
    if not user.is_active:
        raise AuthError("AUTH_ACCOUNT_DISABLED", 403)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise AuthError("AUTH_REQUIRED", 403)
    return current_user
```

- [ ] **Step 5: Create the authentication router**

Create `backend/app/api/routes/auth.py`:

```python
from datetime import UTC, datetime

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, GoogleVerifierDep, SessionDep
from app.auth.account_service import authenticate_google
from app.auth.session_service import refresh_session, revoke_session
from app.schemas.auth_schema import (
    AuthResponse,
    GoogleAuthRequest,
    LogoutRequest,
    PreferencesUpdate,
    RefreshRequest,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth")


def public_user(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)


@router.post("/google", response_model=AuthResponse)
def google_login(
    payload: GoogleAuthRequest,
    session: SessionDep,
    verifier: GoogleVerifierDep,
) -> AuthResponse:
    result = authenticate_google(
        session,
        verifier,
        payload.credential,
        payload.preferred_locale,
    )
    return AuthResponse(
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
        access_expires_in=result.tokens.access_expires_in,
        refresh_expires_in=result.tokens.refresh_expires_in,
        user=UserPublic.model_validate(result.user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, session: SessionDep) -> TokenResponse:
    tokens = refresh_session(session, payload.refresh_token)
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        access_expires_in=tokens.access_expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, session: SessionDep) -> Response:
    revoke_session(session, payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserPublic)
def me(current_user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(current_user)


@router.patch("/me/preferences", response_model=UserPublic)
def update_preferences(
    payload: PreferencesUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> UserPublic:
    current_user.preferred_locale = payload.preferred_locale
    current_user.updated_at = datetime.now(UTC)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UserPublic.model_validate(current_user)
```

- [ ] **Step 6: Mount routes and stable error handling**

Replace `backend/app/api/main.py` with:

```python
from fastapi import APIRouter

from app.api.routes import auth, health, qa

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(qa.router, prefix="/qa", tags=["qa"])
```

Add these imports to `backend/app/main.py`:

```python
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from app.auth.errors import AuthError
```

Inside `create_app`, before router registration, add:

```python
@application.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or str(uuid4())
    response = await call_next(request)
    response.headers["x-request-id"] = request.state.request_id
    return response

@application.exception_handler(AuthError)
async def auth_error_handler(request: Request, error: AuthError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=error.status_code,
        content={"code": error.code, "request_id": request_id},
        headers={"x-request-id": request_id},
    )
```

Update `authenticate` in `backend/app/crud/user_crud.py`:

```python
if not db_user or db_user.hashed_password is None:
    return None
```

- [ ] **Step 7: Run API and backend regression tests**

Run:

```bash
cd backend
uv run pytest tests/api/test_auth.py tests/auth tests/api/test_health.py -q
uv run ruff check app tests/api/test_auth.py
```

Expected: authentication tests pass, health tests remain green, and Ruff succeeds.

- [ ] **Step 8: Commit the FastAPI authentication API**

```bash
git add backend/app/api backend/app/auth backend/app/core backend/app/crud/user_crud.py backend/app/main.py backend/app/schemas/auth_schema.py backend/tests/api/test_auth.py
git commit -m "feat(auth): expose Google session API"
```

## Task 8: Build the server-only BFF authentication library

**Files:**

- Create: `frontend/src/lib/auth/types.ts`
- Create: `frontend/src/lib/auth/config.ts`
- Create: `frontend/src/lib/auth/security.ts`
- Create: `frontend/src/lib/auth/cookies.ts`
- Create: `frontend/src/lib/auth/backend.ts`
- Create: `frontend/src/lib/auth/config.test.ts`
- Create: `frontend/src/lib/auth/security.test.ts`
- Create: `frontend/src/lib/auth/cookies.test.ts`
- Create: `frontend/src/lib/auth/backend.test.ts`

- [ ] **Step 1: Write failing BFF library tests**

Create `frontend/src/lib/auth/security.test.ts`:

```typescript
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { isSameOrigin, isValidCsrf, safeReturnPath } from "./security";

describe("auth security", () => {
  it("allows internal return paths and rejects external paths", () => {
    expect(safeReturnPath("/zh-CN/dashboard", "/en-US/dashboard")).toBe(
      "/zh-CN/dashboard",
    );
    expect(safeReturnPath("//evil.example", "/en-US/dashboard")).toBe(
      "/en-US/dashboard",
    );
    expect(safeReturnPath("https://evil.example", "/en-US/dashboard")).toBe(
      "/en-US/dashboard",
    );
  });

  it("requires matching request and application origins", () => {
    const request = new NextRequest("https://equitylens.example/api/auth/logout", {
      headers: { origin: "https://equitylens.example" },
    });
    expect(isSameOrigin(request)).toBe(true);
  });

  it("compares complete CSRF values", () => {
    expect(isValidCsrf("token-value", "token-value")).toBe(true);
    expect(isValidCsrf("token-value", "different")).toBe(false);
  });
});
```

Create `frontend/src/lib/auth/cookies.test.ts`:

```typescript
import { NextResponse } from "next/server";
import { describe, expect, it } from "vitest";

import { accessCookieName, refreshCookieName, setSessionCookies } from "./cookies";

describe("session cookies", () => {
  it("sets HttpOnly same-site token cookies", () => {
    const response = NextResponse.json({ ok: true });
    setSessionCookies(response, {
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
      access_expires_in: 900,
      refresh_expires_in: 2_592_000,
    });

    expect(response.cookies.get(accessCookieName)?.httpOnly).toBe(true);
    expect(response.cookies.get(accessCookieName)?.sameSite).toBe("lax");
    expect(response.cookies.get(refreshCookieName)?.httpOnly).toBe(true);
  });
});
```

Create `frontend/src/lib/auth/backend.test.ts`:

```typescript
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authenticatedBackendRequest } from "./backend";

describe("authenticated backend requests", () => {
  afterEach(() => vi.restoreAllMocks());

  it("refreshes once after an expired access token", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ code: "AUTH_REQUIRED" }, { status: 401 }))
      .mockResolvedValueOnce(
        Response.json({
          access_token: "new-access",
          refresh_token: "new-refresh",
          token_type: "bearer",
          access_expires_in: 900,
          refresh_expires_in: 2_592_000,
        }),
      )
      .mockResolvedValueOnce(Response.json({ id: 1, email: "a@example.com" }));
    const request = new NextRequest("https://example.com/api/auth/me", {
      headers: {
        cookie: "equitylens_access=old-access; equitylens_refresh=old-refresh",
      },
    });

    const result = await authenticatedBackendRequest(request, "/auth/me");

    expect(result.response.status).toBe(200);
    expect(result.rotatedTokens?.access_token).toBe("new-access");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});
```

Create `frontend/src/lib/auth/config.test.ts`:

```typescript
import { afterEach, describe, expect, it } from "vitest";

import { authConfig } from "./config";

describe("authConfig", () => {
  const original = process.env;
  afterEach(() => {
    process.env = original;
  });

  it("uses server-only backend URL and parses cookie security", () => {
    process.env = {
      ...original,
      BACKEND_URL: "http://api:8000/",
      COOKIE_SECURE: "false",
    };

    expect(authConfig()).toEqual({
      backendUrl: "http://api:8000",
      cookieSecure: false,
    });
  });
});
```

- [ ] **Step 2: Run tests and verify the failure**

Run:

```bash
cd frontend
corepack pnpm test -- src/lib/auth
```

Expected: FAIL because the BFF library files are missing.

- [ ] **Step 3: Define shared authentication types and config**

Create `frontend/src/lib/auth/types.ts`:

```typescript
import type { Locale } from "@/lib/i18n";

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  access_expires_in: number;
  refresh_expires_in: number;
};

export type AuthUser = {
  id: number;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  preferred_locale: Locale;
  created_at: string;
};

export type AuthResponse = AuthTokens & { user: AuthUser };
export type AuthError = { code: string; request_id: string };
```

Create `frontend/src/lib/auth/config.ts`:

```typescript
export function authConfig() {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    throw new Error("BACKEND_URL is required");
  }
  return {
    backendUrl: backendUrl.replace(/\/$/, ""),
    cookieSecure: process.env.COOKIE_SECURE !== "false",
  };
}
```

- [ ] **Step 4: Implement return-path, origin, and CSRF validation**

Create `frontend/src/lib/auth/security.ts`:

```typescript
import { timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";

export function safeReturnPath(value: unknown, fallback: string): string {
  if (typeof value !== "string" || !value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }
  try {
    const parsed = new URL(value, "https://equitylens.local");
    return parsed.origin === "https://equitylens.local"
      ? `${parsed.pathname}${parsed.search}${parsed.hash}`
      : fallback;
  } catch {
    return fallback;
  }
}

export function isSameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  return origin === request.nextUrl.origin;
}

export function isValidCsrf(cookieValue: string | null, bodyValue: unknown): boolean {
  if (!cookieValue || typeof bodyValue !== "string") return false;
  const left = Buffer.from(cookieValue);
  const right = Buffer.from(bodyValue);
  return left.length === right.length && timingSafeEqual(left, right);
}
```

- [ ] **Step 5: Implement cookie lifecycle helpers**

Create `frontend/src/lib/auth/cookies.ts`:

```typescript
import type { NextResponse } from "next/server";

import { authConfig } from "./config";
import type { AuthTokens } from "./types";

export const accessCookieName = "equitylens_access";
export const refreshCookieName = "equitylens_refresh";
export const csrfCookieName = "equitylens_auth_csrf";

export function setSessionCookies(response: NextResponse, tokens: AuthTokens): void {
  const common = {
    httpOnly: true,
    secure: authConfig().cookieSecure,
    sameSite: "lax" as const,
    path: "/",
  };
  response.cookies.set(accessCookieName, tokens.access_token, {
    ...common,
    maxAge: tokens.access_expires_in,
  });
  response.cookies.set(refreshCookieName, tokens.refresh_token, {
    ...common,
    maxAge: tokens.refresh_expires_in,
  });
}

export function clearSessionCookies(response: NextResponse): void {
  response.cookies.set(accessCookieName, "", { maxAge: 0, path: "/" });
  response.cookies.set(refreshCookieName, "", { maxAge: 0, path: "/" });
}
```

- [ ] **Step 6: Implement backend calls and refresh retry**

Create `frontend/src/lib/auth/backend.ts`:

```typescript
import type { NextRequest } from "next/server";

import { accessCookieName, refreshCookieName } from "./cookies";
import { authConfig } from "./config";
import type { AuthTokens } from "./types";

export type BackendResult = {
  response: Response;
  rotatedTokens?: AuthTokens;
};

export function backendRequest(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");
  return fetch(`${authConfig().backendUrl}/api/v1${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

function withBearer(init: RequestInit, token: string): RequestInit {
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${token}`);
  return { ...init, headers };
}

export async function refreshFromRequest(request: NextRequest): Promise<Response> {
  const refreshToken = request.cookies.get(refreshCookieName)?.value;
  if (!refreshToken) {
    return Response.json({ code: "AUTH_REQUIRED", request_id: "bff" }, { status: 401 });
  }
  return backendRequest("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function authenticatedBackendRequest(
  request: NextRequest,
  path: string,
  init: RequestInit = {},
): Promise<BackendResult> {
  const accessToken = request.cookies.get(accessCookieName)?.value;
  if (!accessToken) {
    return {
      response: Response.json(
        { code: "AUTH_REQUIRED", request_id: "bff" },
        { status: 401 },
      ),
    };
  }

  const first = await backendRequest(path, withBearer(init, accessToken));
  if (first.status !== 401) return { response: first };

  const refresh = await refreshFromRequest(request);
  if (!refresh.ok) return { response: refresh };
  const tokens = (await refresh.json()) as AuthTokens;
  const retry = await backendRequest(path, withBearer(init, tokens.access_token));
  return { response: retry, rotatedTokens: tokens };
}
```

- [ ] **Step 7: Run BFF library tests and static checks**

Run:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false corepack pnpm test -- src/lib/auth
corepack pnpm lint
```

Expected: all BFF library tests pass and ESLint succeeds.

- [ ] **Step 8: Commit the BFF authentication library**

```bash
git add frontend/src/lib/auth
git commit -m "feat(auth): add BFF session library"
```

## Task 9: Add Next.js authentication Route Handlers

**Files:**

- Create: `frontend/src/app/api/auth/csrf/route.ts`
- Create: `frontend/src/app/api/auth/csrf/route.test.ts`
- Create: `frontend/src/app/api/auth/google/callback/route.ts`
- Create: `frontend/src/app/api/auth/google/callback/route.test.ts`
- Create: `frontend/src/app/api/auth/me/route.ts`
- Create: `frontend/src/app/api/auth/refresh/route.ts`
- Create: `frontend/src/app/api/auth/logout/route.ts`
- Create: `frontend/src/app/api/auth/preferences/route.ts`
- Create: `frontend/src/app/api/auth/session-routes.test.ts`

- [ ] **Step 1: Write failing CSRF and callback route tests**

Create `frontend/src/app/api/auth/csrf/route.test.ts`:

```typescript
import { describe, expect, it } from "vitest";

import { csrfCookieName } from "@/lib/auth/cookies";
import { GET } from "./route";

describe("GET /api/auth/csrf", () => {
  it("returns a token and sets an HttpOnly strict cookie", async () => {
    const response = await GET();
    const body = await response.json();

    expect(body.token).toHaveLength(43);
    expect(response.cookies.get(csrfCookieName)?.value).toBe(body.token);
    expect(response.cookies.get(csrfCookieName)?.httpOnly).toBe(true);
    expect(response.cookies.get(csrfCookieName)?.sameSite).toBe("strict");
  });
});
```

Create `frontend/src/app/api/auth/google/callback/route.test.ts`:

```typescript
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { accessCookieName, csrfCookieName } from "@/lib/auth/cookies";
import { POST } from "./route";

describe("POST /api/auth/google/callback", () => {
  afterEach(() => vi.restoreAllMocks());

  it("exchanges a valid credential and sets session cookies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({
        access_token: "access",
        refresh_token: "refresh",
        token_type: "bearer",
        access_expires_in: 900,
        refresh_expires_in: 2_592_000,
        user: { id: 1, email: "a@example.com", preferred_locale: "en-US" },
      }),
    );
    const request = new NextRequest("https://example.com/api/auth/google/callback", {
      method: "POST",
      headers: {
        origin: "https://example.com",
        cookie: `${csrfCookieName}=csrf-token`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        credential: "google-token",
        csrf_token: "csrf-token",
        preferred_locale: "en-US",
      }),
    });

    const response = await POST(request);

    expect(response.status).toBe(200);
    expect(response.cookies.get(accessCookieName)?.value).toBe("access");
  });
});
```

- [ ] **Step 2: Run route tests and verify the failure**

Run:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false corepack pnpm test -- src/app/api/auth
```

Expected: FAIL because the authentication Route Handlers are missing.

- [ ] **Step 3: Implement the CSRF and Google callback routes**

Create `frontend/src/app/api/auth/csrf/route.ts`:

```typescript
import { randomBytes } from "node:crypto";
import { NextResponse } from "next/server";

import { authConfig } from "@/lib/auth/config";
import { csrfCookieName } from "@/lib/auth/cookies";

export async function GET() {
  const token = randomBytes(32).toString("base64url");
  const response = NextResponse.json({ token });
  response.cookies.set(csrfCookieName, token, {
    httpOnly: true,
    secure: authConfig().cookieSecure,
    sameSite: "strict",
    path: "/",
    maxAge: 600,
  });
  return response;
}
```

Create `frontend/src/app/api/auth/google/callback/route.ts`:

```typescript
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/auth/backend";
import { csrfCookieName, setSessionCookies } from "@/lib/auth/cookies";
import { isSameOrigin, isValidCsrf } from "@/lib/auth/security";
import type { AuthResponse } from "@/lib/auth/types";
import { isLocale } from "@/lib/i18n";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (
    !body ||
    !isSameOrigin(request) ||
    !isValidCsrf(request.cookies.get(csrfCookieName)?.value ?? null, body.csrf_token) ||
    typeof body.credential !== "string" ||
    !isLocale(body.preferred_locale)
  ) {
    return NextResponse.json(
      { code: "VALIDATION_ERROR", request_id: "bff" },
      { status: 400 },
    );
  }

  const backend = await backendRequest("/auth/google", {
    method: "POST",
    body: JSON.stringify({
      credential: body.credential,
      preferred_locale: body.preferred_locale,
    }),
  });
  const payload = await backend.json();
  if (!backend.ok) return NextResponse.json(payload, { status: backend.status });

  const auth = payload as AuthResponse;
  const response = NextResponse.json({ user: auth.user });
  setSessionCookies(response, auth);
  response.cookies.set(csrfCookieName, "", { maxAge: 0, path: "/" });
  return response;
}
```

- [ ] **Step 4: Implement current-user, refresh, logout, and preference routes**

Create `frontend/src/app/api/auth/me/route.ts`:

```typescript
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authenticatedBackendRequest } from "@/lib/auth/backend";
import { clearSessionCookies, setSessionCookies } from "@/lib/auth/cookies";

export async function GET(request: NextRequest) {
  const result = await authenticatedBackendRequest(request, "/auth/me");
  const payload = await result.response.json();
  const response = NextResponse.json(payload, { status: result.response.status });
  if (result.rotatedTokens) setSessionCookies(response, result.rotatedTokens);
  if (result.response.status === 401 || result.response.status === 403) {
    clearSessionCookies(response);
  }
  return response;
}
```

Create `frontend/src/app/api/auth/refresh/route.ts`:

```typescript
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { refreshFromRequest } from "@/lib/auth/backend";
import { clearSessionCookies, setSessionCookies } from "@/lib/auth/cookies";
import { isSameOrigin } from "@/lib/auth/security";
import type { AuthTokens } from "@/lib/auth/types";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return NextResponse.json({ code: "VALIDATION_ERROR" }, { status: 400 });
  }
  const backend = await refreshFromRequest(request);
  const payload = await backend.json();
  const response = NextResponse.json(payload, { status: backend.status });
  if (backend.ok) setSessionCookies(response, payload as AuthTokens);
  if (!backend.ok && backend.status !== 409) clearSessionCookies(response);
  return response;
}
```

Create `frontend/src/app/api/auth/logout/route.ts`:

```typescript
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { backendRequest } from "@/lib/auth/backend";
import { clearSessionCookies, refreshCookieName } from "@/lib/auth/cookies";
import { isSameOrigin } from "@/lib/auth/security";

export async function POST(request: NextRequest) {
  if (!isSameOrigin(request)) {
    return NextResponse.json({ code: "VALIDATION_ERROR" }, { status: 400 });
  }
  const refreshToken = request.cookies.get(refreshCookieName)?.value;
  if (refreshToken) {
    await backendRequest("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  }
  const response = new NextResponse(null, { status: 204 });
  clearSessionCookies(response);
  return response;
}
```

Create `frontend/src/app/api/auth/preferences/route.ts`:

```typescript
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { authenticatedBackendRequest } from "@/lib/auth/backend";
import { clearSessionCookies, setSessionCookies } from "@/lib/auth/cookies";
import { isSameOrigin } from "@/lib/auth/security";
import { isLocale } from "@/lib/i18n";

export async function PATCH(request: NextRequest) {
  const body = await request.json().catch(() => null);
  if (!body || !isSameOrigin(request) || !isLocale(body.preferred_locale)) {
    return NextResponse.json({ code: "VALIDATION_ERROR" }, { status: 400 });
  }
  const result = await authenticatedBackendRequest(request, "/auth/me/preferences", {
    method: "PATCH",
    body: JSON.stringify({ preferred_locale: body.preferred_locale }),
  });
  const payload = await result.response.json();
  const response = NextResponse.json(payload, { status: result.response.status });
  if (result.rotatedTokens) setSessionCookies(response, result.rotatedTokens);
  if (result.response.status === 401 || result.response.status === 403) {
    clearSessionCookies(response);
  }
  return response;
}
```

- [ ] **Step 5: Add route lifecycle tests**

Create `frontend/src/app/api/auth/session-routes.test.ts`:

```typescript
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { accessCookieName, refreshCookieName } from "@/lib/auth/cookies";
import { POST as logout } from "./logout/route";
import { GET as me } from "./me/route";
import { PATCH as preferences } from "./preferences/route";
import { POST as refresh } from "./refresh/route";

const tokens = {
  access_token: "new-access",
  refresh_token: "new-refresh",
  token_type: "bearer",
  access_expires_in: 900,
  refresh_expires_in: 2_592_000,
};

describe("session Route Handlers", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns the current user", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ id: 1, email: "investor@example.com" }),
    );
    const request = new NextRequest("https://example.com/api/auth/me", {
      headers: { cookie: `${accessCookieName}=access` },
    });
    const response = await me(request);
    expect(response.status).toBe(200);
    expect((await response.json()).email).toBe("investor@example.com");
  });

  it("rotates refresh cookies", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json(tokens));
    const request = new NextRequest("https://example.com/api/auth/refresh", {
      method: "POST",
      headers: {
        origin: "https://example.com",
        cookie: `${refreshCookieName}=old-refresh`,
      },
    });
    const response = await refresh(request);
    expect(response.cookies.get(accessCookieName)?.value).toBe("new-access");
    expect(response.cookies.get(refreshCookieName)?.value).toBe("new-refresh");
  });

  it("clears cookies after logout", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    const request = new NextRequest("https://example.com/api/auth/logout", {
      method: "POST",
      headers: {
        origin: "https://example.com",
        cookie: `${refreshCookieName}=refresh`,
      },
    });
    const response = await logout(request);
    expect(response.status).toBe(204);
    expect(response.cookies.get(refreshCookieName)?.maxAge).toBe(0);
  });

  it("persists locale preferences", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ id: 1, email: "investor@example.com", preferred_locale: "zh-CN" }),
    );
    const request = new NextRequest("https://example.com/api/auth/preferences", {
      method: "PATCH",
      headers: {
        origin: "https://example.com",
        cookie: `${accessCookieName}=access`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ preferred_locale: "zh-CN" }),
    });
    const response = await preferences(request);
    expect(response.status).toBe(200);
    expect((await response.json()).preferred_locale).toBe("zh-CN");
  });
});
```

- [ ] **Step 6: Run route tests, type checking, and lint**

Run:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false corepack pnpm test -- src/app/api/auth src/lib/auth
corepack pnpm exec tsc --noEmit
corepack pnpm lint
```

Expected: all BFF tests pass, TypeScript reports zero errors, and ESLint succeeds.

- [ ] **Step 7: Commit BFF authentication routes**

```bash
git add frontend/src/app/api/auth frontend/src/lib/auth
git commit -m "feat(auth): add session BFF routes"
```

## Task 10: Build the localized Google login experience

**Files:**

- Create: `frontend/src/types/google-identity.d.ts`
- Create: `frontend/src/components/google-sign-in-button.tsx`
- Create: `frontend/src/components/google-sign-in-button.test.tsx`
- Create: `frontend/src/app/[lang]/login/page.tsx`
- Create: `frontend/src/app/[lang]/login/page.test.tsx`
- Modify: `frontend/src/dictionaries/index.ts`
- Modify: `frontend/src/app/[lang]/page.tsx`
- Modify: `frontend/src/app/[lang]/page.test.tsx`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Write failing localized login-page tests**

Create `frontend/src/app/[lang]/login/page.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

vi.mock("@/components/google-sign-in-button", () => ({
  GoogleSignInButton: ({ label }: { label: string }) => <button>{label}</button>,
}));
vi.mock("next/navigation", () => ({ notFound: () => undefined }));

describe("localized login page", () => {
  it("renders English Google login copy", async () => {
    render(
      await LoginPage({
        params: Promise.resolve({ lang: "en-US" }),
        searchParams: Promise.resolve({}),
      }),
    );
    expect(screen.getByRole("heading", { name: "Start with the source." })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeInTheDocument();
  });

  it("renders Chinese Google login copy", async () => {
    render(
      await LoginPage({
        params: Promise.resolve({ lang: "zh-CN" }),
        searchParams: Promise.resolve({}),
      }),
    );
    expect(screen.getByRole("heading", { name: "从原始资料开始研究。" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "使用 Google 继续" })).toBeInTheDocument();
  });
});
```

Create `frontend/src/components/google-sign-in-button.test.tsx`:

```typescript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GoogleSignInButton } from "./google-sign-in-button";

vi.mock("next/script", () => ({
  default: ({ onReady }: { onReady: () => void }) => (
    <button onClick={onReady}>load-google</button>
  ),
}));

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

describe("GoogleSignInButton", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    replace.mockReset();
  });

  it("exchanges the Google credential and redirects internally", async () => {
    let googleCallback: (response: { credential: string }) => void = () => undefined;
    Object.assign(window, {
      google: {
        accounts: {
          id: {
            initialize: vi.fn(({ callback }) => {
              googleCallback = callback;
            }),
            renderButton: vi.fn(),
          },
        },
      },
    });
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(Response.json({ token: "csrf-token" }))
      .mockResolvedValueOnce(Response.json({ user: { id: 1 } }));

    render(
      <GoogleSignInButton
        clientId="client-id"
        errorMessages={{
          accountLink: "Link this account first",
          disabled: "Account disabled",
          generic: "Try again",
        }}
        label="Continue with Google"
        locale="en-US"
        returnTo="/en-US/dashboard"
      />,
    );
    fireEvent.click(screen.getByText("load-google"));
    await waitFor(() => expect(window.google.accounts.id.initialize).toHaveBeenCalled());
    googleCallback({ credential: "google-token" });
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en-US/dashboard"));
  });
});
```

- [ ] **Step 2: Run login tests and verify the failure**

Run:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false corepack pnpm test -- src/app/\[lang\]/login src/components/google-sign-in-button.test.tsx
```

Expected: FAIL because the login page, Google types, component, and dictionary copy are missing.

- [ ] **Step 3: Add Google browser API types**

Create `frontend/src/types/google-identity.d.ts`:

```typescript
type GoogleCredentialResponse = { credential: string };

type GoogleIdApi = {
  initialize(config: {
    client_id: string;
    callback(response: GoogleCredentialResponse): void;
  }): void;
  renderButton(
    parent: HTMLElement,
    options: {
      locale: string;
      shape: "rectangular";
      size: "large";
      text: "continue_with";
      theme: "outline";
      width: number;
    },
  ): void;
};

interface Window {
  google: { accounts: { id: GoogleIdApi } };
}
```

- [ ] **Step 4: Implement the Google sign-in component**

Create `frontend/src/components/google-sign-in-button.tsx`:

```typescript
"use client";

import Script from "next/script";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import type { Locale } from "@/lib/i18n";

type Props = {
  clientId: string;
  errorMessages: {
    accountLink: string;
    disabled: string;
    generic: string;
  };
  label: string;
  locale: Locale;
  returnTo: string;
};

export function GoogleSignInButton({
  clientId,
  errorMessages,
  label,
  locale,
  returnTo,
}: Props) {
  const router = useRouter();
  const target = useRef<HTMLDivElement>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/auth/csrf", { cache: "no-store" })
      .then((response) => response.json())
      .then(({ token }) => setCsrfToken(token))
      .catch(() => setError(errorMessages.generic));
  }, [errorMessages.generic]);

  const exchangeCredential = useCallback(
    async ({ credential }: GoogleCredentialResponse) => {
      if (!csrfToken) return;
      setError(null);
      const response = await fetch("/api/auth/google/callback", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          credential,
          csrf_token: csrfToken,
          preferred_locale: locale,
        }),
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({ code: "" }));
        const message = {
          AUTH_ACCOUNT_DISABLED: errorMessages.disabled,
          AUTH_ACCOUNT_LINK_REQUIRED: errorMessages.accountLink,
        }[payload.code as string];
        setError(message ?? errorMessages.generic);
        return;
      }
      router.replace(returnTo);
    },
    [csrfToken, errorMessages, locale, returnTo, router],
  );

  useEffect(() => {
    if (!scriptReady || !csrfToken || !target.current || !window.google) return;
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: exchangeCredential,
    });
    window.google.accounts.id.renderButton(target.current, {
      locale,
      shape: "rectangular",
      size: "large",
      text: "continue_with",
      theme: "outline",
      width: 320,
    });
  }, [clientId, csrfToken, exchangeCredential, locale, scriptReady]);

  return (
    <div className="google-login">
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={() => setScriptReady(true)}
      />
      <span className="sr-only">{label}</span>
      <div aria-label={label} ref={target} />
      {error ? <p className="auth-error" role="alert">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 5: Add bilingual authentication copy**

Add this `auth` object to the English dictionary:

```typescript
auth: {
  eyebrow: "Investor workspace / secure access",
  title: "Start with the source.",
  description: "Sign in to save companies, filings, research notes, and evidence-backed conversations.",
  google: "Continue with Google",
  privacy: "EquityLens stores an application session in a secure browser cookie.",
  back: "Back to research overview",
  genericError: "Sign-in could not be completed. Try again.",
  accountLinkError: "This email belongs to an existing EquityLens account. Complete account linking before sign-in.",
  disabledError: "This EquityLens account is disabled.",
},
```

Add this `auth` object to the Chinese dictionary:

```typescript
auth: {
  eyebrow: "投资者工作台 / 安全访问",
  title: "从原始资料开始研究。",
  description: "登录后保存公司、财报、研究笔记和带有证据引用的对话。",
  google: "使用 Google 继续",
  privacy: "EquityLens 使用安全浏览器 Cookie 保存应用会话。",
  back: "返回研究概览",
  genericError: "登录未完成，请重试。",
  accountLinkError: "该邮箱已属于现有 EquityLens 账户，请先完成账户绑定。",
  disabledError: "该 EquityLens 账户已停用。",
},
```

- [ ] **Step 6: Create the localized login page**

Create `frontend/src/app/[lang]/login/page.tsx`:

```typescript
import { notFound } from "next/navigation";

import { GoogleSignInButton } from "@/components/google-sign-in-button";
import { LanguageSwitcher } from "@/components/language-switcher";
import { getDictionary } from "@/dictionaries";
import { safeReturnPath } from "@/lib/auth/security";
import { isLocale } from "@/lib/i18n";

type Props = {
  params: Promise<{ lang: string }>;
  searchParams: Promise<{ returnTo?: string }>;
};

export default async function LoginPage({ params, searchParams }: Props) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const copy = getDictionary(lang);
  const query = await searchParams;
  const returnTo = safeReturnPath(query.returnTo, `/${lang}/dashboard`);
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId) throw new Error("NEXT_PUBLIC_GOOGLE_CLIENT_ID is required");

  return (
    <main className="auth-page">
      <div className="ambient-grid" aria-hidden="true" />
      <header className="auth-masthead">
        <a className="wordmark" href={`/${lang}`}>
          <span className="wordmark__seal">E</span>
          <span>EquityLens</span>
        </a>
        <LanguageSwitcher locale={lang} label={copy.language} />
      </header>
      <section className="auth-panel">
        <div className="auth-panel__copy">
          <p className="eyebrow">{copy.auth.eyebrow}</p>
          <h1>{copy.auth.title}</h1>
          <p>{copy.auth.description}</p>
        </div>
        <div className="auth-panel__action">
          <GoogleSignInButton
            clientId={clientId}
            errorMessages={{
              accountLink: copy.auth.accountLinkError,
              disabled: copy.auth.disabledError,
              generic: copy.auth.genericError,
            }}
            label={copy.auth.google}
            locale={lang}
            returnTo={returnTo}
          />
          <p>{copy.auth.privacy}</p>
          <a href={`/${lang}`}>← {copy.auth.back}</a>
        </div>
      </section>
    </main>
  );
}
```

Change the primary home action in `frontend/src/app/[lang]/page.tsx` to:

```tsx
<a className="button button--primary" href={`/${lang}/login`}>
  {copy.hero.primaryAction}
  <span aria-hidden="true">↗</span>
</a>
```

Update the existing home-page test to assert the primary link has `href="/en-US/login"`.

- [ ] **Step 7: Add login-page styling**

Append to `frontend/src/app/globals.css`:

```css
.auth-page {
  min-height: 100vh;
  overflow: hidden;
  position: relative;
}

.auth-masthead {
  align-items: center;
  border-bottom: 1px solid var(--ink);
  display: flex;
  justify-content: space-between;
  margin: 0 3vw;
  min-height: 82px;
  position: relative;
  z-index: 2;
}

.auth-panel {
  display: grid;
  gap: clamp(3rem, 8vw, 9rem);
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.7fr);
  margin: 0 auto;
  max-width: 1320px;
  min-height: calc(100vh - 82px);
  padding: clamp(4rem, 10vw, 9rem) 5vw;
  position: relative;
  z-index: 1;
}

.auth-panel__copy h1 {
  font-family: var(--font-display), "Noto Serif SC", serif;
  font-size: clamp(4rem, 8vw, 8rem);
  font-weight: 420;
  letter-spacing: -0.065em;
  line-height: 0.88;
  margin: 2rem 0;
}

.auth-panel__copy > p:last-child {
  border-left: 2px solid var(--signal);
  font-size: 1.1rem;
  line-height: 1.7;
  max-width: 620px;
  padding-left: 1.25rem;
}

.auth-panel__action {
  align-self: center;
  background: var(--ink);
  box-shadow: 12px 12px 0 var(--signal);
  color: var(--paper);
  padding: 2.25rem;
}

.auth-panel__action p,
.auth-panel__action a {
  color: rgba(241, 239, 230, 0.7);
  font-size: 0.78rem;
  line-height: 1.6;
}

.google-login > div[aria-label] {
  min-height: 44px;
}

.auth-error {
  color: #ff9b7f !important;
}

@media (max-width: 800px) {
  .auth-panel { grid-template-columns: 1fr; }
  .auth-panel__copy h1 { font-size: clamp(3.6rem, 16vw, 6rem); }
}
```

- [ ] **Step 8: Run login UI tests and frontend regression**

Run:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false NEXT_PUBLIC_GOOGLE_CLIENT_ID=test-client corepack pnpm test
corepack pnpm exec tsc --noEmit
corepack pnpm lint
```

Expected: all frontend unit tests pass, TypeScript succeeds, and ESLint succeeds.

- [ ] **Step 9: Commit the login experience**

```bash
git add frontend/src/types frontend/src/components/google-sign-in-button.tsx frontend/src/components/google-sign-in-button.test.tsx frontend/src/app/\[lang\]/login frontend/src/dictionaries/index.ts frontend/src/app/\[lang\]/page.tsx frontend/src/app/\[lang\]/page.test.tsx frontend/src/app/globals.css
git commit -m "feat(auth): add localized Google login"
```

## Task 11: Add the protected application shell and locale preferences

**Files:**

- Create: `frontend/src/components/session-provider.tsx`
- Create: `frontend/src/components/session-provider.test.tsx`
- Create: `frontend/src/components/app-shell.tsx`
- Create: `frontend/src/components/app-shell.test.tsx`
- Create: `frontend/src/app/[lang]/(app)/layout.tsx`
- Create: `frontend/src/app/[lang]/(app)/dashboard/page.tsx`
- Create: `frontend/src/app/[lang]/(app)/dashboard/page.test.tsx`
- Create: `frontend/src/app/[lang]/(app)/settings/page.tsx`
- Modify: `frontend/src/components/language-switcher.tsx`
- Modify: `frontend/src/components/language-switcher.test.tsx`
- Modify: `frontend/src/dictionaries/index.ts`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Write failing session and app-shell tests**

Create `frontend/src/components/session-provider.test.tsx`:

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SessionProvider, useSession } from "./session-provider";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/en-US/dashboard",
  useRouter: () => ({ replace }),
}));

function Probe() {
  const { user } = useSession();
  return <span>{user?.email ?? "loading"}</span>;
}

describe("SessionProvider", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    replace.mockReset();
  });

  it("loads the authenticated user", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ id: 1, email: "investor@example.com", preferred_locale: "en-US" }),
    );
    render(<SessionProvider locale="en-US"><Probe /></SessionProvider>);
    expect(await screen.findByText("investor@example.com")).toBeInTheDocument();
  });

  it("redirects an expired session to localized login", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ code: "AUTH_REQUIRED" }, { status: 401 }),
    );
    render(<SessionProvider locale="en-US"><Probe /></SessionProvider>);
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith(
        "/en-US/login?returnTo=%2Fen-US%2Fdashboard",
      ),
    );
  });
});
```

Extend `frontend/src/components/language-switcher.test.tsx`:

```typescript
it("persists an authenticated locale preference", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({}));
  render(<LanguageSwitcher authenticated locale="en-US" label="Language" />);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "zh-CN" } });
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/auth/preferences",
    expect.objectContaining({ method: "PATCH" }),
  );
});
```

Create `frontend/src/components/app-shell.test.tsx`:

```typescript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/components/session-provider", () => ({
  useSession: () => ({
    loading: false,
    user: {
      email: "investor@example.com",
      full_name: "Investor",
      avatar_url: null,
    },
  }),
}));
vi.mock("@/components/language-switcher", () => ({
  LanguageSwitcher: () => <span>language</span>,
}));

describe("AppShell", () => {
  it("logs out and returns to the localized home page", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    render(
      <AppShell
        copy={{ dashboard: "Dashboard", settings: "Settings", signOut: "Sign out", loading: "Loading" }}
        languageLabel="Language"
        locale="en-US"
      >
        <p>content</p>
      </AppShell>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/en-US"));
  });
});
```

- [ ] **Step 2: Run protected-shell tests and verify the failure**

Run:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false corepack pnpm test -- src/components/session-provider.test.tsx src/components/language-switcher.test.tsx
```

Expected: FAIL because session context and authenticated preference synchronization are missing.

- [ ] **Step 3: Implement session context and route protection**

Create `frontend/src/components/session-provider.tsx`:

```typescript
"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import type { AuthUser } from "@/lib/auth/types";
import type { Locale } from "@/lib/i18n";

type SessionValue = { user: AuthUser | null; loading: boolean };
const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession requires SessionProvider");
  return value;
}

export function SessionProvider({
  children,
  locale,
}: {
  children: React.ReactNode;
  locale: Locale;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load(attempt = 0): Promise<void> {
      const response = await fetch("/api/auth/me", { cache: "no-store" });
      if (response.status === 409 && attempt === 0) {
        await new Promise((resolve) => window.setTimeout(resolve, 150));
        return load(1);
      }
      if (!response.ok) {
        router.replace(`/${locale}/login?returnTo=${encodeURIComponent(pathname)}`);
        return;
      }
      const current = (await response.json()) as AuthUser;
      if (active) {
        setUser(current);
        setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [locale, pathname, router]);

  const value = useMemo(() => ({ user, loading }), [loading, user]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
```

- [ ] **Step 4: Implement the authenticated app shell**

Create `frontend/src/components/app-shell.tsx`:

```typescript
"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";

import { LanguageSwitcher } from "@/components/language-switcher";
import { useSession } from "@/components/session-provider";
import type { Locale } from "@/lib/i18n";

type Copy = {
  dashboard: string;
  settings: string;
  signOut: string;
  loading: string;
};

export function AppShell({
  children,
  copy,
  languageLabel,
  locale,
}: {
  children: React.ReactNode;
  copy: Copy;
  languageLabel: string;
  locale: Locale;
}) {
  const router = useRouter();
  const { loading, user } = useSession();

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.replace(`/${locale}`);
  }

  if (loading || !user) return <main className="session-loading">{copy.loading}</main>;
  return (
    <div className="app-frame">
      <header className="app-header">
        <a className="wordmark" href={`/${locale}/dashboard`}>
          <span className="wordmark__seal">E</span><span>EquityLens</span>
        </a>
        <nav>
          <a href={`/${locale}/dashboard`}>{copy.dashboard}</a>
          <a href={`/${locale}/settings`}>{copy.settings}</a>
        </nav>
        <div className="app-header__account">
          {user.avatar_url ? (
            <Image
              alt=""
              className="app-header__avatar"
              height={32}
              src={user.avatar_url}
              unoptimized
              width={32}
            />
          ) : null}
          <span>{user.full_name ?? user.email}</span>
          <LanguageSwitcher authenticated locale={locale} label={languageLabel} />
          <button type="button" onClick={signOut}>{copy.signOut}</button>
        </div>
      </header>
      <main className="app-content">{children}</main>
    </div>
  );
}
```

Update `LanguageSwitcherProps` in `frontend/src/components/language-switcher.tsx`:

```typescript
type LanguageSwitcherProps = {
  authenticated?: boolean;
  locale: Locale;
  label: string;
};
```

Replace the component signature with:

```typescript
export function LanguageSwitcher({
  authenticated = false,
  locale,
  label,
}: LanguageSwitcherProps) {
```

Before `router.replace` in `changeLocale`, add:

```typescript
if (authenticated) {
  void fetch("/api/auth/preferences", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ preferred_locale: nextLocale }),
  });
}
```

- [ ] **Step 5: Add bilingual protected-page copy**

Add to the English dictionary:

```typescript
app: {
  nav: { dashboard: "Dashboard", settings: "Settings", signOut: "Sign out" },
  loading: "Resolving your research workspace…",
  dashboard: {
    eyebrow: "Research workspace / Phase 1",
    title: "Your research starts here.",
    description: "Company search, watchlists, filings, and valuation views arrive in the next delivery phase.",
  },
  settings: {
    eyebrow: "Workspace preferences",
    title: "Language and account",
    language: "Interface language",
  },
},
```

Add to the Chinese dictionary:

```typescript
app: {
  nav: { dashboard: "研究台", settings: "设置", signOut: "退出登录" },
  loading: "正在载入你的研究工作台…",
  dashboard: {
    eyebrow: "研究工作台 / 第一阶段",
    title: "从这里开始你的公司研究。",
    description: "公司搜索、自选股、财报与估值视图将在下一阶段加入。",
  },
  settings: {
    eyebrow: "工作台偏好",
    title: "语言与账户",
    language: "界面语言",
  },
},
```

- [ ] **Step 6: Create protected routes**

Create `frontend/src/app/[lang]/(app)/layout.tsx`:

```typescript
import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { SessionProvider } from "@/components/session-provider";
import { getDictionary } from "@/dictionaries";
import { isLocale } from "@/lib/i18n";

export default async function ProtectedLayout({ children, params }: {
  children: React.ReactNode;
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const copy = getDictionary(lang);
  return (
    <SessionProvider locale={lang}>
      <AppShell
        copy={{ ...copy.app.nav, loading: copy.app.loading }}
        languageLabel={copy.language}
        locale={lang}
      >
        {children}
      </AppShell>
    </SessionProvider>
  );
}
```

Create `frontend/src/app/[lang]/(app)/dashboard/page.tsx`:

```typescript
import { notFound } from "next/navigation";
import { getDictionary } from "@/dictionaries";
import { isLocale } from "@/lib/i18n";

export default async function Dashboard({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const copy = getDictionary(lang).app.dashboard;
  return (
    <section className="workspace-empty">
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1>{copy.title}</h1>
      <p>{copy.description}</p>
    </section>
  );
}
```

Create `frontend/src/app/[lang]/(app)/settings/page.tsx`:

```typescript
import { notFound } from "next/navigation";
import { LanguageSwitcher } from "@/components/language-switcher";
import { getDictionary } from "@/dictionaries";
import { isLocale } from "@/lib/i18n";

export default async function Settings({ params }: { params: Promise<{ lang: string }> }) {
  const { lang } = await params;
  if (!isLocale(lang)) notFound();
  const copy = getDictionary(lang);
  return (
    <section className="settings-card">
      <p className="eyebrow">{copy.app.settings.eyebrow}</p>
      <h1>{copy.app.settings.title}</h1>
      <LanguageSwitcher authenticated locale={lang} label={copy.app.settings.language} />
    </section>
  );
}
```

Create `frontend/src/app/[lang]/(app)/dashboard/page.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Dashboard from "./page";

vi.mock("next/navigation", () => ({ notFound: () => undefined }));

describe("localized dashboard shell", () => {
  it("renders the English onboarding state", async () => {
    render(await Dashboard({ params: Promise.resolve({ lang: "en-US" }) }));
    expect(
      screen.getByRole("heading", { name: "Your research starts here." }),
    ).toBeInTheDocument();
  });

  it("renders the Chinese onboarding state", async () => {
    render(await Dashboard({ params: Promise.resolve({ lang: "zh-CN" }) }));
    expect(
      screen.getByRole("heading", { name: "从这里开始你的公司研究。" }),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Add protected-shell styling**

Append to `frontend/src/app/globals.css`:

```css
.app-frame { min-height: 100vh; }
.app-header {
  align-items: center;
  border-bottom: 1px solid var(--ink);
  display: grid;
  gap: 2rem;
  grid-template-columns: auto 1fr auto;
  min-height: 82px;
  padding: 0 3vw;
}
.app-header nav { display: flex; gap: 1.5rem; justify-self: center; }
.app-header nav,
.app-header__account,
.app-header button { font: 500 0.72rem var(--font-mono), monospace; }
.app-header__account { align-items: center; display: flex; gap: 1rem; }
.app-header__avatar { border-radius: 50%; object-fit: cover; }
.app-header button { background: var(--signal); border: 1px solid var(--ink); padding: 0.7rem 0.9rem; }
.app-content { margin: 0 auto; max-width: 1440px; padding: clamp(4rem, 8vw, 8rem) 5vw; }
.workspace-empty { max-width: 900px; }
.workspace-empty h1,
.settings-card h1 {
  font-family: var(--font-display), serif;
  font-size: clamp(3.5rem, 7vw, 7rem);
  font-weight: 420;
  letter-spacing: -0.06em;
  line-height: 0.9;
}
.workspace-empty > p:last-child { font-size: 1.1rem; line-height: 1.7; max-width: 680px; }
.settings-card { border: 1px solid var(--ink); box-shadow: 10px 10px 0 var(--signal); padding: 2rem; }
.session-loading { display: grid; min-height: 100vh; place-items: center; }
@media (max-width: 900px) {
  .app-header { grid-template-columns: 1fr auto; }
  .app-header nav { display: none; }
  .app-header__account > span:first-child { display: none; }
}
```

- [ ] **Step 8: Run protected UI tests and build**

Run:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false NEXT_PUBLIC_GOOGLE_CLIENT_ID=test-client corepack pnpm test
corepack pnpm exec tsc --noEmit
corepack pnpm lint
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false NEXT_PUBLIC_GOOGLE_CLIENT_ID=test-client corepack pnpm build
```

Expected: unit tests, TypeScript, lint, and production build all pass.

- [ ] **Step 9: Commit the protected application shell**

```bash
git add frontend/src/components frontend/src/app/\[lang\]/\(app\) frontend/src/dictionaries/index.ts frontend/src/app/globals.css
git commit -m "feat(auth): protect the research workspace"
```

## Task 12: Add browser-level authentication coverage

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`
- Create: `frontend/playwright.config.ts`
- Create: `backend/tests/e2e_app.py`
- Create: `frontend/e2e/auth.spec.ts`

- [ ] **Step 1: Add the Playwright dependency and script**

Run:

```bash
cd frontend
corepack pnpm add --save-dev @playwright/test
corepack pnpm exec playwright install chromium
```

Add this script to `frontend/package.json`:

```json
"test:e2e": "playwright test"
```

Expected: `package.json` and `pnpm-lock.yaml` contain Playwright, and Chromium installs successfully.

- [ ] **Step 2: Create a test-only FastAPI application**

Create `backend/tests/e2e_app.py`:

```python
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
```

The file stays under `backend/tests`, which the Vercel function bundle already excludes.

- [ ] **Step 3: Configure Playwright to run both applications**

Create `frontend/playwright.config.ts`:

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "cd ../backend && uv run uvicorn tests.e2e_app:app --host 127.0.0.1 --port 8001",
      url: "http://127.0.0.1:8001/api/v1/health/live",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command:
        "BACKEND_URL=http://127.0.0.1:8001 FRONTEND_URL=http://127.0.0.1:3000 NEXT_PUBLIC_GOOGLE_CLIENT_ID=e2e-client COOKIE_SECURE=false corepack pnpm dev --hostname 127.0.0.1",
      url: "http://127.0.0.1:3000/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
```

- [ ] **Step 4: Write the full browser authentication scenario**

Create `frontend/e2e/auth.spec.ts`:

```typescript
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("https://accounts.google.com/gsi/client", (route) =>
    route.fulfill({ body: "", contentType: "application/javascript", status: 200 }),
  );
  await page.addInitScript(() => {
    let callback: (response: { credential: string }) => void = () => undefined;
    Object.assign(window, {
      google: {
        accounts: {
          id: {
            initialize: (config: { callback: typeof callback }) => {
              callback = config.callback;
            },
            renderButton: (parent: HTMLElement) => {
              const button = document.createElement("button");
              button.textContent = "Continue with Google";
              button.addEventListener("click", () =>
                callback({ credential: "e2e-google-token" }),
              );
              parent.replaceChildren(button);
            },
          },
        },
      },
    });
  });
});

test("signs in, refreshes, changes locale, and signs out", async ({ page }) => {
  await page.goto("/en-US/login");
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await expect(page).toHaveURL(/\/en-US\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "Your research starts here." }),
  ).toBeVisible();

  const refreshStatus = await page.evaluate(async () =>
    fetch("/api/auth/refresh", { method: "POST" }).then((response) => response.status),
  );
  expect(refreshStatus).toBe(200);

  await page.goto("/en-US/settings");
  await page.getByRole("combobox").last().selectOption("zh-CN");
  await expect(page).toHaveURL(/\/zh-CN\/settings$/);
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/zh-CN$/);
});

test("redirects a signed-out user from a protected route", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("/en-US/dashboard");
  await expect(page).toHaveURL(
    /\/en-US\/login\?returnTo=%2Fen-US%2Fdashboard$/,
  );
  await context.close();
});
```

- [ ] **Step 5: Run the end-to-end suite**

Run:

```bash
cd frontend
corepack pnpm test:e2e
```

Expected: two Chromium tests pass. The first covers Google credential exchange, current-user resolution, explicit refresh, locale persistence, and logout. The second covers protected-route redirection.

- [ ] **Step 6: Commit browser-level coverage**

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/playwright.config.ts frontend/e2e backend/tests/e2e_app.py
git commit -m "test(auth): add browser session coverage"
```

## Task 13: Document setup and complete delivery verification

**Files:**

- Modify: `README.md`
- Modify: `frontend/README.md`
- Modify: `deploy/vercel/README.md`
- Modify: `deploy/docker/README.md`

- [ ] **Step 1: Add exact Google Cloud setup documentation**

Add this section to the root `README.md` after local environment setup:

```markdown
### Google authentication

Create an OAuth 2.0 Web application in Google Cloud Console and configure these Authorized JavaScript origins:

- `http://localhost:3000`
- the Vercel Preview origin used for verification
- the Vercel Production origin
- the public Docker deployment origin

Set the same client ID as `GOOGLE_CLIENT_ID` for FastAPI and `NEXT_PUBLIC_GOOGLE_CLIENT_ID` for Next.js. FastAPI validates the Google ID token; Next.js stores the resulting EquityLens session in HttpOnly cookies.
```

Add these local commands to `frontend/README.md`:

````markdown
Copy `.env.example` to `.env.local`, set `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, and keep `BACKEND_URL=http://localhost:8000` for native development.

```bash
corepack pnpm test
corepack pnpm test:e2e
corepack pnpm lint
corepack pnpm build
```
````

Add the Vercel environment-variable table to `deploy/vercel/README.md`:

```text
Frontend project: BACKEND_URL, FRONTEND_URL, NEXT_PUBLIC_GOOGLE_CLIENT_ID, COOKIE_SECURE=true
Backend project: GOOGLE_CLIENT_ID, FRONTEND_URL, SECRET_KEY_ACCESS_API, DATABASE_URL
```

Add the Docker variables to `deploy/docker/README.md`:

```text
GOOGLE_CLIENT_ID
NEXT_PUBLIC_GOOGLE_CLIENT_ID
FRONTEND_URL
BACKEND_URL=http://api:8000
COOKIE_SECURE=true for HTTPS deployments
```

- [ ] **Step 2: Run the complete backend verification gate**

Run:

```bash
cd backend
uv lock --check
uv run ruff check app tests
uv run pytest
uv run pytest tests/auth tests/api/test_auth.py --cov=app.auth --cov=app.core.security --cov-report=term-missing --cov-fail-under=80
```

Expected: lock and lint checks succeed, the full backend suite passes, and authentication modules reach at least 80% statement and branch coverage.

- [ ] **Step 3: Verify the migration against PostgreSQL**

Run from the repository root with the Docker database available:

```bash
docker compose up -d db
cd backend
DATABASE_URL=postgresql://app:app@localhost:5432/equitylens uv run alembic upgrade head
DATABASE_URL=postgresql://app:app@localhost:5432/equitylens uv run alembic current
DATABASE_URL=postgresql://app:app@localhost:5432/equitylens uv run alembic downgrade 20260713_0001
DATABASE_URL=postgresql://app:app@localhost:5432/equitylens uv run alembic upgrade head
```

Expected: current revision is `20260713_0002`; downgrade to `0001` and re-upgrade both succeed.

- [ ] **Step 4: Run the complete frontend verification gate**

Run:

```bash
cd frontend
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false NEXT_PUBLIC_GOOGLE_CLIENT_ID=test-client corepack pnpm test
corepack pnpm exec tsc --noEmit
corepack pnpm lint
BACKEND_URL=http://localhost:8000 COOKIE_SECURE=false NEXT_PUBLIC_GOOGLE_CLIENT_ID=test-client corepack pnpm build
corepack pnpm test:e2e
```

Expected: unit tests, type checking, lint, production build, and two browser authentication scenarios pass.

- [ ] **Step 5: Verify Docker and Vercel build profiles**

Run from the repository root after setting the documented environment values:

```bash
docker compose build api web
docker compose up --wait db migrate api web
curl --fail http://localhost:8000/api/v1/health/live
curl --fail http://localhost:3000/api/health
```

Expected: both images build, migrations complete, API and web services become healthy, and both health checks return HTTP 200.

For linked Vercel projects, run:

```bash
cd backend && vercel build
cd ../frontend && vercel build
```

Expected: both Vercel builds succeed with the documented environment variables.

- [ ] **Step 6: Review secrets and API surface**

Run:

```bash
git diff --check
git grep -nE "(BEGIN PRIVATE KEY|AIza[0-9A-Za-z_-]{20,})" -- ':!backend/tests/**' ':!frontend/e2e/**' || true
curl --silent http://localhost:8000/api/v1/openapi.json | python -m json.tool | grep -E 'auth/(google|refresh|logout|me)'
```

Expected: whitespace checks pass, no committed runtime secrets appear, the five Phase 1 auth operations appear in OpenAPI, and `/api/v1/login/access-token` is absent.

- [ ] **Step 7: Commit documentation and final verification state**

```bash
git add README.md frontend/README.md deploy/vercel/README.md deploy/docker/README.md
git commit -m "docs(auth): document Google sign-in setup"
```

## Completion checklist

- [ ] Google ID tokens are validated with the official server library and stable `sub` identity.
- [ ] Existing integer user IDs remain unchanged through migration.
- [ ] Access tokens expire after 15 minutes and include user and session-family claims.
- [ ] Refresh token rotation, concurrency grace, replay revocation, and logout pass tests.
- [ ] Browser session tokens use HttpOnly, SameSite, path, expiry, and production Secure flags.
- [ ] English and Chinese login, dashboard, settings, errors, and Google-button locale pass tests.
- [ ] Protected routes redirect through the localized login page and preserve the internal path.
- [ ] Authenticated locale selection persists to the backend user record.
- [ ] Backend unit, API, migration, and coverage gates pass.
- [ ] Frontend unit, type, lint, build, and Playwright gates pass.
- [ ] Docker and linked Vercel build checks pass with documented configuration.
