# Company Research Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an evidence-backed, company-scoped research chat that combines structured EquityLens data, hybrid 10-K retrieval, Agent-selected web research, citation validation, durable conversations, independent daily quota, and bilingual streaming UI.

**Architecture:** Add a `chat` domain to FastAPI with principal-scoped repositories, immutable evidence records, a separate quota ledger, a zero-quota filing-index job, PostgreSQL FTS plus pgvector retrieval, bounded controlled web collection, strict answer planning, and durable-before-stream SSE. Extend the Next.js same-origin BFF with streaming pass-through and build a 430 px desktop research workbench plus a mobile bottom sheet. Reuse company identity, signed guest principals, authentication, SEC filing storage, structured research snapshots, supply-chain graph publication, RQ, Vercel Workflow, and object-storage controls.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, SQLModel, Alembic, PostgreSQL 16 with pgvector, SQLite test doubles, OpenAI Responses API, LangChain OpenAI, HTTPX, S3-compatible object storage, Vercel Blob, Redis/RQ, Vercel Workflow, Next.js 16, React 19, TypeScript 5.9, Vitest, Testing Library, Playwright, pytest.

---

## Working rules

- Run every command from `/Users/yang/Documents/Projects/fastapi-langchain-rag/.worktrees/company-research-chat` unless a step names a subdirectory.
- Use `docs/superpowers/specs/2026-07-14-company-research-chat-design.md` as the product source of truth.
- Keep one task in progress at a time and mark each checkbox as evidence is produced.
- Write tests before production behavior in every task.
- Keep conversation ownership predicates inside repository queries and return the same 404 for absent and foreign resources.
- Treat client context as typed identifiers. Resolve every identifier on the server against the active company and published snapshot.
- Persist the validated answer plan and immutable citations before emitting the first `section` event.
- Keep chat quota independent from company-analysis and graph quota.
- Use deterministic providers in unit, integration, browser, and RAG evaluation suites. Live provider calls stay outside automated tests.
- Keep existing company-intelligence and supply-chain graph APIs backward compatible.
- Use English for code, schema names, tests, documentation, and commits, matching the repository history requested by the user.

## Delivery map

### New backend files

- `backend/app/models/chat_model.py`
- `backend/app/chat/__init__.py`
- `backend/app/chat/contracts.py`
- `backend/app/chat/schemas.py`
- `backend/app/chat/repository.py`
- `backend/app/chat/quota.py`
- `backend/app/chat/chunker.py`
- `backend/app/chat/indexing.py`
- `backend/app/chat/retrieval.py`
- `backend/app/chat/structured_context.py`
- `backend/app/chat/artifacts.py`
- `backend/app/chat/web_search.py`
- `backend/app/chat/prompts.py`
- `backend/app/chat/openai_agent.py`
- `backend/app/chat/validator.py`
- `backend/app/chat/sse.py`
- `backend/app/chat/service.py`
- `backend/app/jobs/_filing_index.py`
- `backend/app/api/routes/chat.py`
- `backend/app/migrations/versions/20260714_0005_company_research_chat.py`
- `backend/tests/chat/conftest.py`
- `backend/tests/chat/test_schemas.py`
- `backend/tests/chat/test_repository.py`
- `backend/tests/chat/test_quota.py`
- `backend/tests/chat/test_chunker.py`
- `backend/tests/chat/test_indexing.py`
- `backend/tests/chat/test_retrieval.py`
- `backend/tests/chat/test_structured_context.py`
- `backend/tests/chat/test_artifacts.py`
- `backend/tests/chat/test_web_search.py`
- `backend/tests/chat/test_openai_agent.py`
- `backend/tests/chat/test_validator.py`
- `backend/tests/chat/test_sse.py`
- `backend/tests/chat/test_service.py`
- `backend/tests/chat/test_rag_evaluation.py`
- `backend/tests/api/test_chat.py`
- `backend/tests/models/test_chat_models.py`
- `backend/tests/test_chat_migration.py`
- `backend/tests/fixtures/chat/aapl_evidence.json`
- `backend/tests/fixtures/chat/aapl_answers.json`
- `backend/tests/fixtures/chat/rag-evaluation.json`
- `backend/tests/integration/test_chat_postgres_retrieval.py`
- `backend/tests/integration/test_company_chat_journey.py`

### Modified backend files

- `backend/pyproject.toml`
- `backend/uv.lock`
- `.env.example`
- `backend/.env.example`
- `backend/app/core/config.py`
- `backend/app/models/__init__.py`
- `backend/app/models/job_model.py`
- `backend/app/jobs/state.py`
- `backend/app/jobs/pipeline.py`
- `backend/app/jobs/schemas.py`
- `backend/app/jobs/service.py`
- `backend/app/jobs/tasks.py`
- `backend/app/jobs/rq_backend.py`
- `backend/app/jobs/vercel_backend.py`
- `backend/app/api/deps.py`
- `backend/app/api/main.py`
- `backend/app/api/routes/internal_jobs.py`
- `backend/tests/core/test_config.py`
- `backend/tests/jobs/backend_contract.py`
- `backend/tests/jobs/test_state.py`
- `backend/tests/jobs/test_pipeline.py`
- `backend/tests/jobs/test_service.py`
- `backend/tests/jobs/test_tasks.py`
- `backend/tests/jobs/test_rq_backend.py`
- `backend/tests/jobs/test_vercel_backend.py`
- `backend/tests/api/test_internal_jobs.py`
- `backend/tests/e2e_app.py`

### New frontend files

- `frontend/src/lib/chat/types.ts`
- `frontend/src/lib/chat/sse.ts`
- `frontend/src/lib/chat/sse.test.ts`
- `frontend/src/features/company/chat/use-company-chat.ts`
- `frontend/src/features/company/chat/chat-workbench.tsx`
- `frontend/src/features/company/chat/chat-workbench.test.tsx`
- `frontend/src/features/company/chat/conversation-history.tsx`
- `frontend/src/features/company/chat/conversation-history.test.tsx`
- `frontend/src/features/company/chat/readiness-panel.tsx`
- `frontend/src/features/company/chat/answer-sections.tsx`
- `frontend/src/features/company/chat/context-chips.tsx`
- `frontend/src/features/company/chat/context-actions.test.tsx`

### Modified frontend and documentation files

- `frontend/src/lib/research/types.ts`
- `frontend/src/lib/research/backend.ts`
- `frontend/src/lib/research/backend.test.ts`
- `frontend/src/app/api/research/[...path]/route.ts`
- `frontend/src/app/api/research/[...path]/route.test.ts`
- `frontend/src/features/company/company-page.tsx`
- `frontend/src/features/company/company-page.test.tsx`
- `frontend/src/features/company/company-header.tsx`
- `frontend/src/features/company/market-context.tsx`
- `frontend/src/features/company/financial-table.tsx`
- `frontend/src/features/company/business-summary.tsx`
- `frontend/src/features/company/supply-chain-node.tsx`
- `frontend/src/features/company/supply-chain-edge.tsx`
- `frontend/src/features/company/supply-chain-inspector.tsx`
- `frontend/src/features/company/copy.ts`
- `frontend/src/features/company/test-fixtures.ts`
- `frontend/src/app/globals.css`
- `frontend/e2e/company-intelligence.spec.ts`
- `README.md`
- `docs/deployment.md`
- `docs/product-status.md`
- `vercel.json`

## Task 1: Lock chat configuration and direct dependencies

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/core/test_config.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `.env.example`
- Modify: `backend/.env.example`

- [x] **Step 1: Write failing settings tests**

Add these assertions to `backend/tests/core/test_config.py` using the existing valid Docker environment fixture:

```python
def test_chat_defaults_follow_approved_contract(monkeypatch):
    monkeypatch.setenv("RESEARCH_MODEL", "gpt-5-mini")
    value = Settings(_env_file=None)

    assert value.CHAT_MODEL == "gpt-5-mini"
    assert value.CHAT_GUEST_DAILY_LIMIT == 2
    assert value.CHAT_USER_DAILY_LIMIT == 10
    assert value.CHAT_GUEST_RETENTION_DAYS == 7
    assert value.CHAT_MAX_MESSAGE_CHARS == 2_000
    assert value.CHAT_CHUNK_TARGET_TOKENS == 700
    assert value.CHAT_CHUNK_OVERLAP_TOKENS == 100
    assert value.CHAT_RETRIEVAL_CANDIDATES == 20
    assert value.CHAT_RETRIEVAL_MAX_CHUNKS == 8
    assert value.CHAT_WEB_MAX_QUERIES == 3
    assert value.CHAT_WEB_MAX_PAGES == 8
    assert value.CHAT_EMBEDDING_DIMENSIONS == 1_536


def test_chat_rejects_invalid_chunk_and_retrieval_bounds(monkeypatch):
    monkeypatch.setenv("CHAT_CHUNK_TARGET_TOKENS", "100")
    monkeypatch.setenv("CHAT_CHUNK_OVERLAP_TOKENS", "100")
    with pytest.raises(ValueError, match="CHAT_CHUNK_OVERLAP_TOKENS"):
        Settings(_env_file=None)
```

- [x] **Step 2: Confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py -q
```

Expected: failure because the `CHAT_*` settings and `CHAT_MODEL` property are absent.

- [x] **Step 3: Add the exact settings contract**

Add to `Settings` in `backend/app/core/config.py`:

```python
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

@property
def CHAT_MODEL(self) -> str:
    return self.CHAT_MODEL_OVERRIDE or self.RESEARCH_MODEL
```

Validate positive limits, overlap below target, minimum final chunk at or below target, max chunks at or below candidates, max-per-section at or below max chunks, and embedding dimensions equal to 1,536 for `filing-chunk.v1`. Require `CHAT_INDEX_WORKFLOW_TRIGGER_URL` in the Vercel profile.

- [x] **Step 4: Promote transitive libraries to direct dependencies**

Run:

```bash
cd backend
uv add "openai>=1.109,<3" "tiktoken>=0.12,<1"
```

The code imports both packages directly. Keep `pgvector`, `langchain-openai`, and existing storage packages unchanged.

- [x] **Step 5: Document environment keys**

Add the complete configuration block from the approved design to `.env.example` and `backend/.env.example`, including `CHAT_INDEX_WORKFLOW_TRIGGER_URL=` and `CHAT_WEB_ARTIFACT_PREFIX=chat-web`. Keep credentials empty.

- [x] **Step 6: Run focused validation**

```bash
cd backend
uv run pytest tests/core/test_config.py -q
uv run python -c "import openai, tiktoken, pgvector"
```

Expected: all tests pass and the import command exits `0`.

- [x] **Step 7: Commit the configuration boundary**

```bash
git add .env.example backend/.env.example backend/app/core/config.py backend/tests/core/test_config.py backend/pyproject.toml backend/uv.lock
git commit -m "chore(chat): add research chat configuration"
```

## Task 2: Add durable chat models and migration

**Files:**

- Create: `backend/app/models/chat_model.py`
- Create: `backend/app/migrations/versions/20260714_0005_company_research_chat.py`
- Create: `backend/tests/models/test_chat_models.py`
- Create: `backend/tests/test_chat_migration.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/job_model.py`

- [x] **Step 1: Write model metadata and constraint tests**

In `backend/tests/models/test_chat_models.py`, assert the six model tables, conversation owner check, active-guest partial index, message request uniqueness, citation ordinal uniqueness, filing chunk version uniqueness, quota request uniqueness, and cascade foreign keys:

```python
def test_chat_models_expose_locked_constraints():
    conversation = CompanyConversation.__table__
    assert "ck_company_conversation_exactly_one_owner" in {
        item.name for item in conversation.constraints
    }
    assert "uq_company_conversation_active_guest" in {
        item.name for item in conversation.indexes
    }

    message = ConversationMessage.__table__
    assert "uq_conversation_message_request" in {
        item.name for item in message.constraints
    }
    assert "uq_message_citation_ordinal" in {
        item.name for item in MessageCitation.__table__.constraints
    }
```

Add construction tests for locale, state, role, evidence coverage, source kind, tier, verification, positive token count, and excerpt limits.

- [x] **Step 2: Confirm the red state**

```bash
cd backend
uv run pytest tests/models/test_chat_models.py -q
```

Expected: import failure because `app.models.chat_model` is absent.

- [x] **Step 3: Define the persistence models**

Create `backend/app/models/chat_model.py` with:

```python
class CompanyConversation(SQLModel, table=True):
    __tablename__ = "company_conversation"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(foreign_key="company.id", ondelete="CASCADE", index=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", ondelete="CASCADE", index=True)
    guest_principal_hash: str | None = Field(default=None, max_length=64, index=True)
    title: str = Field(min_length=1, max_length=120)
    locale: str = Field(max_length=5)
    summary: str | None = Field(default=None, sa_column=Column(Text()))
    summary_through_message_id: UUID | None = Field(default=None)
    expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    archived_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
```

Add `ConversationMessage`, `MessageCitation`, `FilingChunk`, `WebSearchTrace`, and `ChatQuotaLedger` with every field and check from design section 6. Use `Vector(1536)` for `FilingChunk.embedding`. Use JSON only for validated context selection and sanitized search-result metadata. Add `chat_index_snapshot_id` to `IngestionJob` only when a separate snapshot record is created; otherwise leave the job linked through `company_id` and `FilingChunk.filing_id`.

Store user message text directly in `ConversationMessage.content`. Store an assistant answer as the canonical JSON serialization of the validated `ResearchAnswerPlan` in the same text field; API serializers parse it back into the closed response schema. This keeps the approved table contract intact and makes the durable-before-stream boundary explicit.

Create the active guest index with PostgreSQL and SQLite predicates:

```python
Index(
    "uq_company_conversation_active_guest",
    "company_id",
    "guest_principal_hash",
    unique=True,
    postgresql_where=text("archived_at IS NULL AND guest_principal_hash IS NOT NULL"),
    sqlite_where=text("archived_at IS NULL AND guest_principal_hash IS NOT NULL"),
)
```

Add an FK from `summary_through_message_id` to `conversation_message.id` in the migration after both tables exist. Name every check, unique constraint, FK, and index.

- [x] **Step 4: Write the migration test before the migration**

Create `backend/tests/test_chat_migration.py`. Follow the existing migration harness and assert upgrade from `20260714_0004`, the six new tables, vector/FTS indexes on PostgreSQL metadata, all named constraints, and downgrade back to `20260714_0004`:

```python
CHAT_TABLES = {
    "company_conversation",
    "conversation_message",
    "message_citation",
    "filing_chunk",
    "web_search_trace",
    "chat_quota_ledger",
}

assert CHAT_TABLES <= set(inspector.get_table_names())
assert "uq_company_conversation_active_guest" in named(
    inspector.get_indexes("company_conversation")
)
```

- [x] **Step 5: Implement reversible migration `0005`**

Create the tables in FK-safe order. Run `CREATE EXTENSION IF NOT EXISTS vector` through the migration. Add:

```sql
CREATE INDEX ix_filing_chunk_embedding_hnsw
ON filing_chunk USING hnsw (embedding vector_cosine_ops)
```

and:

```sql
CREATE INDEX ix_filing_chunk_fts
ON filing_chunk USING gin (to_tsvector('english', text))
```

Guard PostgreSQL-only DDL by dialect. The downgrade drops child tables first and retains the shared `vector` extension.

- [ ] **Step 6: Validate models and migration**

Deterministic SQLite migration round-trip, model regressions, and Ruff passed on
2026-07-15. Live PostgreSQL upgrade/downgrade remains part of Task 16 because the
local workspace has no database environment configured.

```bash
cd backend
uv run pytest tests/models/test_chat_models.py tests/test_chat_migration.py tests/test_migrations.py -q
uv run alembic upgrade head
uv run alembic downgrade 20260714_0004
uv run alembic upgrade head
```

Expected: tests pass and both migration directions exit `0` against the configured development database.

- [x] **Step 7: Commit persistence**

```bash
git add backend/app/models/chat_model.py backend/app/models/__init__.py backend/app/models/job_model.py backend/app/migrations/versions/20260714_0005_company_research_chat.py backend/tests/models/test_chat_models.py backend/tests/test_chat_migration.py
git commit -m "feat(chat): add conversation persistence"
```

## Task 3: Enforce conversation ownership, lifecycle, and pagination

**Files:**

- Create: `backend/app/chat/__init__.py`
- Create: `backend/app/chat/contracts.py`
- Create: `backend/app/chat/schemas.py`
- Create: `backend/app/chat/repository.py`
- Create: `backend/tests/chat/conftest.py`
- Create: `backend/tests/chat/test_schemas.py`
- Create: `backend/tests/chat/test_repository.py`

- [x] **Step 1: Write failing schema tests**

Cover locale, title, 2,000-character message limit, Unicode normalization, closed context kinds, UUID requirements, and cursor shape:

```python
def test_message_request_normalizes_text_and_rejects_unknown_context():
    request = MessageCreate(
        client_request_id=uuid4(),
        content="  Why\u00a0did margins rise?  ",
        locale="en-US",
        context=[],
    )
    assert request.content == "Why did margins rise?"

    with pytest.raises(ValidationError):
        MessageCreate(
            client_request_id=uuid4(),
            content="Question",
            locale="en-US",
            context=[{"kind": "client_text", "id": str(uuid4())}],
        )
```

The context union contains `market_metric`, `financial_metric`, `business_claim`, `supply_chain_node`, and `supply_chain_edge`.

- [x] **Step 2: Write failing repository isolation tests**

In `backend/tests/chat/test_repository.py`, cover:

- guest singleton reuse by company;
- expired guest archive and replacement;
- authenticated multiple conversations;
- principal and company isolation returning `None`;
- rename allowed for user ownership;
- ownership-safe row locking for later rename policy enforcement;
- archive exclusion;
- ascending message cursor pagination;
- idempotent lookup by `(conversation_id, client_request_id)`;
- seven-day cleanup returning private artifact keys for deletion.

Use this ownership call shape:

```python
conversation = repository.get_owned(
    conversation_id,
    company_id=company.id,
    principal=principal,
    now=now,
)
assert conversation is None
```

- [x] **Step 3: Confirm the red state**

```bash
cd backend
uv run pytest tests/chat/test_schemas.py tests/chat/test_repository.py -q
```

Expected: imports fail because chat schemas and repository are absent.

- [x] **Step 4: Add closed API schemas and provider protocols**

Define `Locale = Literal["en-US", "zh-CN"]`, context discriminated unions, `ConversationCreate`, `ConversationPatch`, `ConversationPublic`, `MessageCreate`, `MessagePublic`, `CitationPublic`, `MessagePage`, `ChatReadiness`, and the SSE payload schemas in `backend/app/chat/schemas.py`. Set `extra="forbid"` on write models.

Define protocols in `backend/app/chat/contracts.py`:

```python
class EmbeddingProvider(Protocol):
    model_id: str
    dimensions: int
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...

class StructuredContextProvider(Protocol):
    async def build(self, request: StructuredContextRequest) -> EvidencePack: ...

class WebSearchProvider(Protocol):
    async def search(self, request: WebSearchRequest) -> WebSearchResult: ...

class AnswerPlanningModel(Protocol):
    model_id: str
    async def plan(self, request: AnswerPlanningRequest) -> ResearchAnswerPlan: ...
```

- [x] **Step 5: Implement repository predicates and lifecycle**

Build SQLModel statements through one `_owner_predicate(principal)` helper. User ownership compares `user_id`; guest ownership compares the signed principal's `principal_hash`. Every single-resource lookup includes the owner predicate, active state, expiry rule, and company where applicable.

Use cursor `(created_at, id)` and `limit + 1` pagination. Archive with a row lock and update `updated_at`. Guest creation archives an expired active row before inserting the successor. Return artifact keys from cleanup and let the service delete objects after the database transaction commits.

- [x] **Step 6: Validate repository behavior**

```bash
cd backend
uv run pytest tests/chat/test_schemas.py tests/chat/test_repository.py -q
```

Expected: all schema and ownership tests pass.

- [x] **Step 7: Commit the conversation domain**

```bash
git add backend/app/chat/__init__.py backend/app/chat/contracts.py backend/app/chat/schemas.py backend/app/chat/repository.py backend/tests/chat
git commit -m "feat(chat): enforce conversation ownership"
```

## Task 4: Implement independent idempotent chat quota

**Files:**

- Create: `backend/app/chat/quota.py`
- Create: `backend/tests/chat/test_quota.py`
- Modify: `backend/app/chat/contracts.py`
- Modify: `backend/app/chat/repository.py`

- [x] **Step 1: Write quota lifecycle tests**

Cover guest limit 2, user limit 10, UTC reset, independence from `AgentDailyUsage`, request replay, consume, refund exactly once, consumed reservation permanence, retry after refund, and concurrent reservation cap:

```python
def test_replay_and_refund_are_idempotent(chat_quota, guest_principal, now):
    request_id = uuid4()
    first = chat_quota.reserve(request_id, guest_principal, conversation_id, now)
    replay = chat_quota.reserve(request_id, guest_principal, conversation_id, now)
    assert replay.ledger_id == first.ledger_id
    assert replay.used == 1

    assert chat_quota.refund(first.ledger_id, "CHAT_RETRIEVAL_FAILED", now)
    assert chat_quota.refund(first.ledger_id, "CHAT_RETRIEVAL_FAILED", now) is False
    assert chat_quota.status(guest_principal, now).remaining == 2
```

- [x] **Step 2: Confirm the red state**

```bash
cd backend
uv run pytest tests/chat/test_quota.py -q
```

Expected: import failure because the chat quota service is absent.

- [x] **Step 3: Implement ledger transactions**

Create `ChatQuotaRepository` in `contracts.py` and SQL/in-memory implementations in `quota.py`. Use a unique `request_id`, `SELECT ... FOR UPDATE` for state transitions, and a conditional PostgreSQL insert/count query scoped to `principal_type`, `principal_key`, and `usage_date`. Store `user:<id>` for users and the existing keyed HMAC digest for guests.

Expose:

```python
class ChatQuotaService:
    def status(self, principal, now) -> ChatQuotaStatus: ...
    def reserve(self, request_id, principal, conversation_id, now) -> ChatQuotaLease: ...
    def attach_messages(self, ledger_id, user_message_id, assistant_message_id) -> None: ...
    def consume(self, ledger_id, coverage, now) -> bool: ...
    def refund(self, ledger_id, reason, now) -> bool: ...
```

Allow `complete`, `partial`, and `insufficient` coverage to consume. Keep a refunded attempt replayable without charging. A retry uses its fresh request UUID and increments the attempt number.

- [ ] **Step 4: Validate unit and PostgreSQL concurrency behavior**

SQLite lifecycle and regression suites passed on 2026-07-15. The isolated-schema
PostgreSQL concurrency test is present and skips until `TEST_POSTGRES_URL` is
configured; Task 16 owns that live integration gate.

Add a `@pytest.mark.postgres` concurrent test beside the unit suite, then run:

```bash
cd backend
uv run pytest tests/chat/test_quota.py -q
TEST_POSTGRES_URL="$DATABASE_URL" uv run pytest tests/chat/test_quota.py -m postgres -q
```

Expected: unit tests pass; PostgreSQL test passes when the integration database is configured. Record a skipped PostgreSQL test as an incomplete integration gate.

- [x] **Step 5: Commit quota accounting**

```bash
git add backend/app/chat/contracts.py backend/app/chat/quota.py backend/app/chat/repository.py backend/tests/chat/test_quota.py
git commit -m "feat(chat): add independent message quota"
```

## Task 5: Index latest 10-K sections through zero-quota jobs

**Files:**

- Create: `backend/app/chat/chunker.py`
- Create: `backend/app/chat/indexing.py`
- Create: `backend/app/jobs/_filing_index.py`
- Create: `backend/tests/chat/test_chunker.py`
- Create: `backend/tests/chat/test_indexing.py`
- Modify: `backend/app/jobs/state.py`
- Modify: `backend/app/jobs/schemas.py`
- Modify: `backend/app/jobs/pipeline.py`
- Modify: `backend/app/jobs/service.py`
- Modify: `backend/app/jobs/tasks.py`
- Modify: `backend/app/jobs/rq_backend.py`
- Modify: `backend/app/jobs/vercel_backend.py`
- Modify: `backend/tests/jobs/backend_contract.py`
- Modify: `backend/tests/jobs/test_state.py`
- Modify: `backend/tests/jobs/test_pipeline.py`
- Modify: `backend/tests/jobs/test_service.py`
- Modify: `backend/tests/jobs/test_tasks.py`
- Modify: `backend/tests/jobs/test_rq_backend.py`
- Modify: `backend/tests/jobs/test_vercel_backend.py`

- [x] **Step 1: Write deterministic chunk tests**

Inject a token codec and assert target 700, overlap 100, final minimum 120, stable ordinals, metadata separation, content hashes, and deterministic re-runs:

```python
def test_chunker_merges_short_tail_and_preserves_overlap(token_codec):
    chunks = chunk_section(section, token_codec=token_codec, target=700, overlap=100, minimum_final=120)
    assert all(chunk.token_count <= 700 for chunk in chunks)
    assert chunks[-1].token_count >= 120
    assert token_codec.decode(chunks[0].token_ids[-100:]) == token_codec.decode(
        chunks[1].token_ids[:100]
    )
```

- [x] **Step 2: Write indexing and job-contract tests**

Cover latest 10-K selection, batched embeddings, dimension mismatch, idempotent reuse, changed-section replacement in one transaction, empty filing error, `filing_index` state order, RQ task routing, Vercel trigger routing, and zero chat/Agent quota mutations.

Use the state order:

```python
JOB_STATE_ORDER["filing_index"] == (
    "queued",
    "chunking",
    "embedding",
    "indexing",
    "completed",
)
```

- [x] **Step 3: Confirm the red state**

```bash
cd backend
uv run pytest tests/chat/test_chunker.py tests/chat/test_indexing.py tests/jobs/test_state.py tests/jobs/test_rq_backend.py tests/jobs/test_vercel_backend.py -q
```

Expected: failures for missing chunker, indexer, and job route.

- [x] **Step 4: Implement chunking and idempotent indexing**

Use `tiktoken.encoding_for_model` with a deterministic fallback to `cl100k_base`. Prepend heading and source anchor only to embedding input. Store source text separately. Compare `(content_hash, chunk_schema_version, embedding_model)` and reuse a matching section set. Delete and replace changed section chunks inside a transaction after all embeddings validate as 1,536-dimensional finite floats.

- [x] **Step 5: Add shared job execution**

Add `synchronize_filing_index` that creates/deduplicates a `filing_index` `IngestionJob` from company, latest filing accession, schema, and embedding model. Skip every Agent quota call. Add `run_filing_index`, RQ routing, Vercel trigger routing, retry state, and internal Workflow step endpoint. The company-intelligence pipeline calls the same indexer after parsing and before analyzing; an indexing failure keeps company analysis retryable at `indexing`.

- [x] **Step 6: Validate indexing and backend parity**

```bash
cd backend
uv run pytest tests/chat/test_chunker.py tests/chat/test_indexing.py tests/jobs/test_state.py tests/jobs/test_service.py tests/jobs/test_tasks.py tests/jobs/test_rq_backend.py tests/jobs/test_vercel_backend.py -q
```

Expected: all focused tests pass and existing job types retain their state sequences.

- [x] **Step 7: Commit filing indexing**

```bash
git add backend/app/chat/chunker.py backend/app/chat/indexing.py backend/app/jobs/_filing_index.py backend/app/jobs/state.py backend/app/jobs/schemas.py backend/app/jobs/pipeline.py backend/app/jobs/service.py backend/app/jobs/tasks.py backend/app/jobs/rq_backend.py backend/app/jobs/vercel_backend.py backend/tests/chat/test_chunker.py backend/tests/chat/test_indexing.py backend/tests/jobs/backend_contract.py backend/tests/jobs/test_state.py backend/tests/jobs/test_pipeline.py backend/tests/jobs/test_service.py backend/tests/jobs/test_tasks.py backend/tests/jobs/test_rq_backend.py backend/tests/jobs/test_vercel_backend.py
git commit -m "feat(chat): index latest filing evidence"
```

## Task 6: Build query rewriting and hybrid retrieval

**Files:**

- Create: `backend/app/chat/retrieval.py`
- Create: `backend/tests/chat/test_retrieval.py`
- Create: `backend/tests/integration/test_chat_postgres_retrieval.py`
- Modify: `backend/app/chat/contracts.py`
- Modify: `backend/app/chat/schemas.py`
- Modify: `backend/app/chat/repository.py`

- [x] **Step 1: Write rewrite and ranker tests**

Fixtures must preserve company identity, ticker, fiscal periods, metrics, and selected graph entities for English and Chinese questions. Add RRF tests for top-20 inputs, `k=60`, stable ties, three-per-section diversity, eight-chunk cap, and 6,000-token budget:

```python
def test_rrf_is_stable_and_enforces_section_diversity():
    ranked = reciprocal_rank_fusion(fts_hits, vector_hits, k=60)
    selected = select_chunks(ranked, max_chunks=8, max_per_section=3, token_budget=6000)
    assert [item.id for item in selected] == EXPECTED_IDS
    assert max(Counter(item.section_id for item in selected).values()) <= 3
    assert sum(item.token_count for item in selected) <= 6000
```

- [x] **Step 2: Write PostgreSQL retrieval tests**

Seed two companies and two filings. Assert FTS and cosine searches filter by company and latest filing, return at most 20 each, and use the expected indexes through `EXPLAIN`. Mark with `@pytest.mark.postgres`.

- [x] **Step 3: Confirm the red state**

```bash
cd backend
uv run pytest tests/chat/test_retrieval.py -q
```

Expected: import failure because retrieval code is absent.

- [x] **Step 4: Implement standalone query rewriting**

Define `QueryRewrite` with `filing_query_en`, `display_query`, `current_intent`, and preserved typed entities. Build the input from current question, resolved context labels, previous eight messages, summary, company name, ticker, and locale. Use a strict structured model call and validate explicit dates, fiscal periods, ticker, metric names, and context entities remain present.

- [x] **Step 5: Implement PostgreSQL and in-memory retrieval**

Use parameterized SQLAlchemy expressions for `plainto_tsquery('english', :query)` and pgvector cosine distance. Fetch 20 candidates from each channel, fuse with `score += 1 / (60 + rank)`, break ties by best individual rank then UUID, and apply diversity/token bounds. Return evidence objects with exact section, filing, URL, anchor, excerpt, and retrieval scores. Keep SQL construction inside the repository.

- [x] **Step 6: Validate both ranking paths**

```bash
cd backend
uv run pytest tests/chat/test_retrieval.py -q
TEST_POSTGRES_URL="$DATABASE_URL" uv run pytest tests/integration/test_chat_postgres_retrieval.py -m postgres -q
```

Expected: deterministic tests pass; PostgreSQL retrieval passes when configured.

- [x] **Step 7: Commit hybrid retrieval**

```bash
git add backend/app/chat/contracts.py backend/app/chat/schemas.py backend/app/chat/repository.py backend/app/chat/retrieval.py backend/tests/chat/test_retrieval.py backend/tests/integration/test_chat_postgres_retrieval.py
git commit -m "feat(chat): add hybrid filing retrieval"
```

## Task 7: Resolve trusted structured company context

**Files:**

- Create: `backend/app/chat/structured_context.py`
- Create: `backend/tests/chat/test_structured_context.py`
- Modify: `backend/app/chat/contracts.py`
- Modify: `backend/app/chat/schemas.py`

- [x] **Step 1: Write context-resolution tests**

Cover latest market observation, four annual periods plus TTM, published intelligence claims, published graph nodes/edges, exact excerpts, stale snapshots, missing resources, and cross-company IDs. Every client label must be ignored:

```python
async def test_graph_edge_context_is_resolved_from_published_snapshot(services):
    pack = await services.resolve(
        company=aapl,
        selections=[SupplyChainEdgeContext(id=edge.id, snapshot_id=snapshot.id)],
        locale="en-US",
    )
    assert pack.items[0].label == persisted_edge.explanation_en
    assert pack.items[0].citation.excerpt == persisted_citation.excerpt


async def test_cross_company_context_has_stable_error(services):
    with pytest.raises(DomainError, match="CHAT_CONTEXT_INVALID"):
        await services.resolve(company=aapl, selections=[msft_metric], locale="en-US")
```

- [x] **Step 2: Confirm the red state**

```bash
cd backend
uv run pytest tests/chat/test_structured_context.py -q
```

Expected: import failure because structured context is absent.

- [x] **Step 3: Implement typed server resolution**

Create adapters around existing market, financial, intelligence, and supply-chain repositories. Resolve `market_metric` and `financial_metric` from allowlisted metric keys; resolve claim/node/edge IDs through company-scoped snapshot queries. Build immutable evidence candidates with `source_kind`, stable internal ID, title, HTTPS URL, anchor, excerpt, publication/observation time, source tier, and verification.

Return readiness independently for company intelligence, filing text, filing index, graph, and web recency. Missing optional resources add readiness actions and evidence-gap records.

- [x] **Step 4: Validate context and regress existing domains**

```bash
cd backend
uv run pytest tests/chat/test_structured_context.py tests/market_data tests/financials tests/research tests/supply_chain/test_service.py -q
```

Expected: all focused suites pass.

- [x] **Step 5: Commit structured evidence**

```bash
git add backend/app/chat/contracts.py backend/app/chat/schemas.py backend/app/chat/structured_context.py backend/tests/chat/test_structured_context.py
git commit -m "feat(chat): resolve structured company evidence"
```

## Task 8: Add bounded Agent-selected web evidence

**Files:**

- Create: `backend/app/chat/artifacts.py`
- Create: `backend/app/chat/web_discovery.py`
- Create: `backend/app/chat/web_fetcher.py`
- Create: `backend/app/chat/web_search.py`
- Create: `backend/app/chat/web_trace.py`
- Create: `backend/tests/chat/test_artifacts.py`
- Create: `backend/tests/chat/test_web_search.py`
- Modify: `backend/app/chat/contracts.py`
- Modify: `backend/app/chat/schemas.py`

- [x] **Step 1: Write source-policy and budget tests**

Cover deterministic current-intent triggers, low internal evidence, Agent-requested search, three-query cap, eight-page cap, official priority, trusted-secondary classification, rejected domain classification, deduplicated canonical URLs, and normalized query storage.

```python
async def test_current_question_forces_bounded_web_collection(harness):
    result = await harness.search(
        question="What is Apple's latest antitrust development?",
        internal_coverage="partial",
    )
    assert result.decision == "required_current"
    assert len(result.queries) <= 3
    assert len(result.selected_pages) <= 8
    assert result.selected_pages[0].source_tier == "primary"
```

Add safety tests that selected URLs pass the existing `PinnedDnsTransport` and controlled collector before they become citable. Verify prompt-injection text stays delimited as untrusted evidence and never changes tool budgets.

- [x] **Step 2: Write immutable artifact tests**

Reuse graph artifact-store patterns. Assert gzip round-trip, SHA-256 verification, `chat-web/<principal-scope>/<conversation>/<message>/<ordinal>-<hash>.json.gz` keys, private access, collision handling, and cleanup by exact returned key.

- [x] **Step 3: Confirm the red state**

```bash
cd backend
uv run pytest tests/chat/test_artifacts.py tests/chat/test_web_search.py -q
```

Expected: imports fail because web and artifact adapters are absent.

- [x] **Step 4: Implement OpenAI Responses search adapter**

Use `AsyncOpenAI.responses.create` with a web-search tool and `tool_choice="auto"`. Expose only the bounded `WebSearchProvider` contract. Record provider request ID, tool ordinal, normalized query, search reason, candidate metadata, selected IDs, and duration. Exclude model reasoning and raw page bodies from the database.

Classify sources through an explicit allowlist/configuration object. Prefer SEC, US government/regulators, official company IR/newsrooms, and exchange notices. Treat configured financial publications, industry associations, and research institutions as `trusted_secondary`.

- [x] **Step 5: Re-fetch and verify selected pages**

Pass each selected HTTPS URL through the existing DNS-pinned collector controls. Store the compressed immutable page record in S3/Vercel Blob, save its key/hash on `WebSearchTrace`, and allow exact citations only from stored fetched text. Optional web failure with strong internal evidence yields a partial-evidence note; required-current web failure raises `CHAT_WEB_SEARCH_FAILED`.

- [x] **Step 6: Validate provider isolation and safety**

```bash
cd backend
uv run pytest tests/chat/test_artifacts.py tests/chat/test_web_search.py tests/supply_chain/test_source_policy.py tests/supply_chain/test_collector.py -q
```

Expected: all tests pass with deterministic fake Responses and HTTP transports.

- [x] **Step 7: Commit web evidence**

```bash
git add backend/app/chat/contracts.py backend/app/chat/schemas.py backend/app/chat/artifacts.py backend/app/chat/web_search.py backend/tests/chat/test_artifacts.py backend/tests/chat/test_web_search.py
git commit -m "feat(chat): add bounded web evidence"
```

## Task 9: Generate and validate citation-bound answer plans

**Files:**

- Create: `backend/app/chat/prompts.py`
- Create: `backend/app/chat/answer_schemas.py`
- Create: `backend/app/chat/openai_agent.py`
- Create: `backend/app/chat/validator.py`
- Create: `backend/tests/chat/test_openai_agent.py`
- Create: `backend/tests/chat/test_validator.py`
- Create: `backend/tests/fixtures/chat/aapl_evidence.json`
- Create: `backend/tests/fixtures/chat/aapl_answers.json`
- Modify: `backend/app/chat/schemas.py`

- [x] **Step 1: Write strict schema and Agent retry tests**

Define fixtures for English, Chinese, partial, insufficient, invalid citation, invalid locale, altered filing excerpt, altered web excerpt, unsupported number, unlabeled inference, and cross-company evidence. Test one repair call and terminal second failure.

```python
async def test_agent_repairs_invalid_citations_once(fake_model, evidence_pack):
    fake_model.outputs = [INVALID_PLAN, VALID_PLAN]
    plan = await agent.create_plan(question, evidence_pack, locale="en-US")
    assert plan == ResearchAnswerPlan.model_validate(VALID_PLAN)
    assert fake_model.calls == 2
    assert "unknown citation" in fake_model.requests[1].repair_feedback
```

- [x] **Step 2: Confirm the red state**

```bash
cd backend
uv run pytest tests/chat/test_openai_agent.py tests/chat/test_validator.py -q
```

Expected: imports fail because answer planning and validation are absent.

- [x] **Step 3: Define `ResearchAnswerPlan`**

Use strict Pydantic models:

```python
class AnswerPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4_000)
    citation_ids: list[str] = Field(max_length=8)
    inference: bool = False

class ResearchAnswerPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    direct_conclusion: AnswerPoint
    key_evidence: list[AnswerPoint] = Field(min_length=1, max_length=8)
    risks_and_uncertainties: list[AnswerPoint] = Field(max_length=6)
    sources: list[str] = Field(max_length=24)
    evidence_coverage: Literal["complete", "partial", "insufficient"]
    web_search_used: bool
```

- [x] **Step 4: Implement prompt boundaries and model adapter**

Separate system policy, typed internal context, untrusted filing/web evidence, conversation history, and user question into distinct message blocks. Instruct the model to output the four approved sections, preserve locale, label inference, cite every material number/current fact/supply-chain claim, and state missing evidence for insufficient answers. Use structured outputs and compact validation feedback for one repair attempt.

- [x] **Step 5: Implement deterministic validation**

Validate citation existence, source ownership, source ordering, number support, excerpt equivalence after whitespace normalization, exact controlled-artifact excerpts, locale, inference premises, coverage semantics, and `web_search_used`. Convert validated evidence to immutable `MessageCitation` snapshots capped at 1,000 characters for filings and 600 for web.

- [x] **Step 6: Run Agent and validation suites**

```bash
cd backend
uv run pytest tests/chat/test_openai_agent.py tests/chat/test_validator.py -q
```

Expected: all deterministic fixtures pass and the fake model receives at most two planning calls.

- [x] **Step 7: Commit answer planning**

```bash
git add backend/app/chat/prompts.py backend/app/chat/openai_agent.py backend/app/chat/validator.py backend/app/chat/schemas.py backend/tests/chat/test_openai_agent.py backend/tests/chat/test_validator.py backend/tests/fixtures/chat/aapl_evidence.json backend/tests/fixtures/chat/aapl_answers.json
git commit -m "feat(chat): validate citation bound answers"
```

## Task 10: Orchestrate durable messages and SSE lifecycle

**Files:**

- Create: `backend/app/chat/sse.py`
- Create: `backend/app/chat/service.py`
- Create: `backend/tests/chat/test_sse.py`
- Create: `backend/tests/chat/test_service.py`
- Modify: `backend/app/chat/repository.py`
- Modify: `backend/app/chat/schemas.py`

- [x] **Step 1: Write SSE encoding tests**

Test monotonic event IDs, JSON encoding, accepted/stage/section/citation/complete/error closed union, 15-second heartbeat comments, cache headers, and newline-safe data:

```python
def test_sse_encoder_emits_monotonic_closed_events():
    stream = SseEncoder()
    assert stream.event("accepted", accepted).startswith("id: 1\nevent: accepted\n")
    assert stream.event("stage", stage).startswith("id: 2\nevent: stage\n")
    assert stream.heartbeat() == ": heartbeat\n\n"
```

- [x] **Step 2: Write service transaction tests**

Cover authorization before quota, idempotency before quota, accepted event IDs, retrieval stages, web stages, durable answer before first section, citation order, consume for complete/partial/insufficient, refund for every pre-persistence error, cancellation, reconnect through history, retry eligibility, retry request replay, and one net consumed unit after a refunded attempt.

Capture the durability boundary explicitly:

```python
async for event in service.stream_message(command):
    if event.kind == "section":
        with Session(engine) as session:
            stored = repository.get_message(session, event.assistant_message_id)
            assert stored.state == "completed"
            assert repository.list_citations(stored.id)
        break
```

- [x] **Step 3: Confirm the red state**

```bash
cd backend
uv run pytest tests/chat/test_sse.py tests/chat/test_service.py -q
```

Expected: imports fail because streaming orchestration is absent.

- [x] **Step 4: Implement the message state machine**

Execute in this order:

1. Load owned active conversation.
2. Validate and resolve client context.
3. Return existing request attempt when `client_request_id` exists.
4. Reserve chat quota.
5. Persist user and pending assistant messages; attach ledger IDs.
6. Emit `accepted`.
7. Rewrite and retrieve internal evidence.
8. Decide and collect bounded web evidence.
9. Generate and validate one answer plan with one repair attempt.
10. In one transaction, persist completed assistant content, answer-plan JSON, immutable citations, coverage, and completion time.
11. Consume quota.
12. Emit sections, citations, and `complete` from durable records.

Map public failures to the design error table. Catch `asyncio.CancelledError`; before durable completion mark failed and refund with `CHAT_STREAM_CANCELLED`, then re-raise. After durability, leave the completed record reloadable.

- [x] **Step 5: Implement retry and summary checkpoints**

Retry requires a failed retryable assistant, a fresh request UUID, and the same owned conversation. Atomically increment `attempt_count`, reserve from the refunded prior attempt, and reuse the original user message. After more than eight unsummarized messages, create/update `conversation.summary` and `summary_through_message_id` through a deterministic summarizer contract; tests inject a fake summarizer.

- [x] **Step 6: Validate service semantics**

```bash
cd backend
uv run pytest tests/chat/test_sse.py tests/chat/test_service.py tests/chat/test_quota.py tests/chat/test_repository.py -q
```

Expected: all lifecycle, retry, idempotency, and durability assertions pass.

- [x] **Step 7: Commit orchestration**

```bash
git add backend/app/chat/sse.py backend/app/chat/service.py backend/app/chat/repository.py backend/app/chat/schemas.py backend/tests/chat/test_sse.py backend/tests/chat/test_service.py
git commit -m "feat(chat): stream durable research answers"
```

## Task 11: Expose company chat APIs and production dependencies

**Files:**

- Create: `backend/app/api/routes/chat.py`
- Create: `backend/tests/api/test_chat.py`
- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/api/main.py`
- Modify: `backend/app/api/routes/internal_jobs.py`
- Modify: `backend/tests/api/test_internal_jobs.py`

- [x] **Step 1: Write API contract tests**

Cover all approved routes and exact behaviors:

```text
GET    /companies/{symbol}/chat-readiness
POST   /companies/{symbol}/chat-index/sync
GET    /companies/{symbol}/conversations
POST   /companies/{symbol}/conversations
GET    /conversations/{conversation_id}
PATCH  /conversations/{conversation_id}
DELETE /conversations/{conversation_id}
GET    /conversations/{conversation_id}/messages
POST   /conversations/{conversation_id}/messages
POST   /conversations/{conversation_id}/messages/{assistant_message_id}/retry
GET    /chat-quota
```

Assert guest singleton response, user create/rename/archive, guest rename policy, ownership 404, invalid context 422, quota 429 before SSE, `text/event-stream`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, cursor pagination, and locale preservation.

- [x] **Step 2: Confirm the red state**

```bash
cd backend
uv run pytest tests/api/test_chat.py -q
```

Expected: 404 responses because the router is absent.

- [x] **Step 3: Wire production dependencies**

In `backend/app/api/deps.py`, provide request-scoped chat repository/quota/service, `OpenAIEmbeddings` with 1,536 dimensions, structured context adapter, OpenAI Responses web provider, answer-planning Agent, controlled collector, and S3/Vercel Blob artifact store selected through existing deployment settings. Reuse `AgentPrincipal` and the current database session.

Keep route handlers thin. Convert `DomainError` through the existing public error shape. Stream with `StreamingResponse(generator, media_type="text/event-stream", headers=...)`.

- [x] **Step 4: Add readiness index endpoint and Workflow step**

`chat-readiness` reads resource state without quota. `chat-index/sync` calls zero-quota `synchronize_filing_index`. Extend `internal_jobs.py` with authenticated `filing_index` Workflow steps that invoke the same indexer as RQ.

- [x] **Step 5: Validate APIs and regress auth/security**

```bash
cd backend
uv run pytest tests/api/test_chat.py tests/api/test_internal_jobs.py tests/api/test_auth.py tests/quota/test_identity.py -q
```

Expected: routes pass for guest and user principals; ownership leaks remain covered by 404 assertions.

- [x] **Step 6: Commit the FastAPI surface**

```bash
git add backend/app/api/routes/chat.py backend/app/api/deps.py backend/app/api/main.py backend/app/api/routes/internal_jobs.py backend/tests/api/test_chat.py backend/tests/api/test_internal_jobs.py
git commit -m "feat(chat): expose company research APIs"
```

## Task 12: Stream chat through the Next.js BFF

**Files:**

- Create: `frontend/src/lib/chat/types.ts`
- Create: `frontend/src/lib/chat/sse.ts`
- Create: `frontend/src/lib/chat/sse.test.ts`
- Modify: `frontend/src/lib/research/types.ts`
- Modify: `frontend/src/lib/research/backend.ts`
- Modify: `frontend/src/lib/research/backend.test.ts`
- Modify: `frontend/src/app/api/research/[...path]/route.ts`
- Modify: `frontend/src/app/api/research/[...path]/route.test.ts`

- [ ] **Step 1: Write BFF allowlist and stream tests**

Add exact regex entries for every chat route and `PATCH`. Keep method/path pairing closed. Test origin enforcement, 64 KiB body cap, guest assertion, token refresh, upstream 404/422/429 forwarding, and a delayed two-chunk SSE response where the first chunk reaches the caller before the second resolves.

```typescript
it("forwards SSE incrementally", async () => {
  const response = await POST(messageRequest, context);
  const reader = response.body!.getReader();
  const first = await reader.read();
  expect(new TextDecoder().decode(first.value)).toContain("event: accepted");
  expect(secondChunkReleased).toBe(false);
});
```

- [ ] **Step 2: Write closed SSE parser tests**

Test chunk splits across UTF-8 boundaries, multiple events per chunk, comments, multiline data, monotonic IDs, invalid JSON, unknown events, cancellation, and final incomplete frames. Define a discriminated `ChatStreamEvent` union for the six event kinds.

- [ ] **Step 3: Confirm the red state**

```bash
cd frontend
corepack pnpm test -- src/app/api/research/'[...path]'/route.test.ts src/lib/chat/sse.test.ts
```

Expected: route allowlist and parser tests fail.

- [ ] **Step 4: Forward streaming bodies directly**

Extend `ResearchHttpMethod` with `PATCH`. In `copyUpstreamResponse`, branch on `content-type: text/event-stream` and return `upstream.body` directly. Forward `content-type`, `cache-control`, `x-accel-buffering`, and `retry-after`; avoid `arrayBuffer()` for SSE. Preserve cookie rotation and guest-cookie attachment on the streaming response.

Propagate caller abort to the backend request by passing `request.signal` through `researchBackendRequest` and `fetch`.

- [ ] **Step 5: Implement incremental parser**

Expose:

```typescript
export async function* parseChatEventStream(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal,
): AsyncGenerator<ChatStreamEvent>;
```

Use `TextDecoder(..., { stream: true })`, buffer until blank-line boundaries, ignore comments, parse closed event names, validate monotonic numeric IDs, and validate payload fields with explicit type guards.

- [ ] **Step 6: Validate BFF and parser**

```bash
cd frontend
corepack pnpm test -- src/app/api/research/'[...path]'/route.test.ts src/lib/research/backend.test.ts src/lib/chat/sse.test.ts
```

Expected: all focused tests pass and incremental delivery assertion observes the first delayed chunk.

- [ ] **Step 7: Commit the streaming boundary**

```bash
git add frontend/src/lib/chat frontend/src/lib/research/types.ts frontend/src/lib/research/backend.ts frontend/src/lib/research/backend.test.ts frontend/src/app/api/research/'[...path]'/route.ts frontend/src/app/api/research/'[...path]'/route.test.ts
git commit -m "feat(chat): stream events through research BFF"
```

## Task 13: Build the conversation workbench and history

**Files:**

- Create: `frontend/src/features/company/chat/use-company-chat.ts`
- Create: `frontend/src/features/company/chat/chat-workbench.tsx`
- Create: `frontend/src/features/company/chat/chat-workbench.test.tsx`
- Create: `frontend/src/features/company/chat/conversation-history.tsx`
- Create: `frontend/src/features/company/chat/conversation-history.test.tsx`
- Create: `frontend/src/features/company/chat/answer-sections.tsx`
- Create: `frontend/src/features/company/chat/context-chips.tsx`
- Modify: `frontend/src/features/company/company-page.tsx`
- Modify: `frontend/src/features/company/company-page.test.tsx`
- Modify: `frontend/src/features/company/company-header.tsx`
- Modify: `frontend/src/features/company/copy.ts`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Write reducer and workbench behavior tests**

Test open/close, initial guest conversation, authenticated history, new/rename/archive, message pagination, sending, accepted/stage/section/citation/complete transitions, errors, retry, request replay, quota updates, composer disable rules, and title generation display.

```typescript
it("renders validated sections as events arrive", async () => {
  render(<ChatWorkbench {...props} />);
  await user.type(screen.getByRole("textbox", { name: copy.question }), "Why did margins rise?");
  await user.click(screen.getByRole("button", { name: copy.send }));
  expect(await screen.findByText(copy.stages.retrieval)).toBeVisible();
  expect(await screen.findByRole("heading", { name: copy.directConclusion })).toBeVisible();
  expect(await screen.findByText("1 message remaining")).toBeVisible();
});
```

- [ ] **Step 2: Confirm the red state**

```bash
cd frontend
corepack pnpm test -- src/features/company/chat src/features/company/company-page.test.tsx
```

Expected: imports fail because workbench components are absent.

- [ ] **Step 3: Implement the chat state hook**

`useCompanyChat` owns the conversation list, selected conversation, paginated messages, context selection, stream `AbortController`, reducer, quota, and readiness. Generate a fresh `crypto.randomUUID()` for initial sends and retries. Preserve it during transport replay. Abort active streams on close/unmount and reload the assistant record when the stream ends after durable completion.

- [ ] **Step 4: Build structured answer presentation**

Render direct conclusion, key evidence, risks and uncertainties, and sources as distinct semantic sections. Citation chips open HTTPS links and expose title, source tier, publication/retrieval date, anchor, and excerpt. Render server text as plain paragraphs and narrow inline emphasis; keep HTML disabled.

- [ ] **Step 5: Build desktop history and workbench shell**

At 768 px and above, change the company page to a flexible dossier column plus a 430 px workbench. Add symbol, title, history, new conversation, close, message list, selected-context chips, composer, automatic-web status, quota, and research disclaimer. Authenticated users receive create/rename/archive; guests receive the active singleton plus archive-and-start-fresh.

- [ ] **Step 6: Add bilingual copy**

Add complete `en` and `zh` keys for all controls, stage status, section headings, quota, readiness, context labels, errors, retry, citations, history, disclaimer, and suggested questions. Keep server-created historical message text in its stored locale.

- [ ] **Step 7: Validate workbench and company regressions**

```bash
cd frontend
corepack pnpm test -- src/features/company/chat src/features/company/company-page.test.tsx src/lib/i18n.test.ts
```

Expected: workbench, history, stream transitions, and both dictionaries pass.

- [ ] **Step 8: Commit the research workbench**

```bash
git add frontend/src/features/company/chat frontend/src/features/company/company-page.tsx frontend/src/features/company/company-page.test.tsx frontend/src/features/company/company-header.tsx frontend/src/features/company/copy.ts frontend/src/app/globals.css
git commit -m "feat(chat): add company research workbench"
```

## Task 14: Connect readiness, page context, mobile, and accessibility

**Files:**

- Create: `frontend/src/features/company/chat/readiness-panel.tsx`
- Create: `frontend/src/features/company/chat/context-actions.test.tsx`
- Modify: `frontend/src/features/company/chat/chat-workbench.tsx`
- Modify: `frontend/src/features/company/chat/chat-workbench.test.tsx`
- Modify: `frontend/src/features/company/market-context.tsx`
- Modify: `frontend/src/features/company/financial-table.tsx`
- Modify: `frontend/src/features/company/business-summary.tsx`
- Modify: `frontend/src/features/company/supply-chain-node.tsx`
- Modify: `frontend/src/features/company/supply-chain-edge.tsx`
- Modify: `frontend/src/features/company/supply-chain-inspector.tsx`
- Modify: `frontend/src/features/company/test-fixtures.ts`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Write typed context-action tests**

Click price, P/E, a financial cell, business claim, graph node, and graph edge. Assert each action opens chat and sends only approved identifiers plus snapshot/period fields. Assert visible labels stay outside the request payload.

```typescript
expect(onAsk).toHaveBeenCalledWith({
  kind: "supply_chain_edge",
  id: edge.id,
  snapshot_id: graph.snapshot.id,
});
```

- [ ] **Step 2: Write readiness and accessibility tests**

Cover independent ready/missing rows, zero-quota index action, existing analysis/graph actions, suggested questions from available categories, mobile bottom sheet, 92dvh cap, focus trap, Escape close, focus restoration, `aria-live="polite"`, heading order, keyboard citation access, and reduced-motion classes.

- [ ] **Step 3: Confirm the red state**

```bash
cd frontend
corepack pnpm test -- src/features/company/chat/context-actions.test.tsx src/features/company/chat/chat-workbench.test.tsx src/app/graph-accessibility.test.ts
```

Expected: context and mobile/accessibility assertions fail.

- [ ] **Step 4: Add context entry points**

Introduce one `onAskContext(selection)` callback from `CompanyPage` and pass it into the existing market, financial, business, node, edge, and inspector components. Add compact `Ask EquityLens` buttons with specific accessible names. The workbench resolves selected chips only from server-returned labels after conversation/message validation.

- [ ] **Step 5: Add readiness controls**

Show structured intelligence, filing text, filing index, graph, and web recency. Wire `Prepare 10-K for chat` to `/chat-index/sync`; show its job state without decrementing either quota. Reuse existing analysis and graph hooks for quota-consuming readiness actions and display their current quota separately from chat quota.

- [ ] **Step 6: Implement mobile and accessibility behavior**

Below 768 px, render a near-full-height dialog sheet with drag handle, `max-height: 92dvh`, scrollable message body, composer using `position: sticky`, focus trap sentinels, Escape close, and origin focus restoration. Respect `prefers-reduced-motion: reduce`. Announce stage text politely and final errors assertively.

- [ ] **Step 7: Validate context, mobile, and accessibility**

```bash
cd frontend
corepack pnpm test -- src/features/company src/app/graph-accessibility.test.ts
corepack pnpm lint
```

Expected: all company feature tests and lint pass.

- [ ] **Step 8: Commit contextual chat UX**

```bash
git add frontend/src/features/company frontend/src/app/globals.css
git commit -m "feat(chat): connect research context actions"
```

## Task 15: Add deterministic journeys and RAG evaluation

**Files:**

- Create: `backend/tests/fixtures/chat/rag-evaluation.json`
- Create: `backend/tests/integration/test_company_chat_journey.py`
- Modify: `backend/tests/e2e_app.py`
- Modify: `frontend/e2e/company-intelligence.spec.ts`

- [ ] **Step 1: Build deterministic chat providers in the E2E app**

Seed AAPL filings, chunks, structured data, graph evidence, web candidates/artifacts, conversations, and users. Override embedding, query rewrite, web search, answer planning, and summarization providers. Add failure switches for model, required web, and cancellation. Keep every response fabricated and deterministic.

- [ ] **Step 2: Add 20-question RAG fixture**

Create at least 20 fixed questions spanning revenue, profitability, cash flow, valuation, segments, supply-chain position, competitors, risk factors, and recent events. Each entry contains:

```json
{
  "id": "aapl-gross-margin-01",
  "locale": "en-US",
  "question": "What supports Apple's gross margin?",
  "required_source_kinds": ["financial", "filing"],
  "required_facts": ["gross margin"],
  "expected_web_search": false,
  "expected_coverage": ["complete", "partial"]
}
```

The evaluator checks company/period, numerical consistency, citations, exact excerpt support, search decision, coverage, locale, and unsupported material claims.

- [ ] **Step 3: Add the ten approved browser journeys**

Extend Playwright with:

1. guest two-message completion and third-message 429;
2. repeated request ID without extra usage;
3. filing question with no web search;
4. current-event question with tier/date metadata;
5. graph edge context action;
6. failure refund and retry;
7. Chinese stages and answer;
8. authenticated create/rename/archive/reload;
9. cross-user conversation 404;
10. mobile keyboard citation and focus restoration.

- [ ] **Step 4: Add backend journey assertions**

In `test_company_chat_journey.py`, exercise the same service through FastAPI and inspect database rows after completion/refund/replay. Assert exact net quota and immutable citations.

- [ ] **Step 5: Run integration, RAG, and browser suites**

```bash
cd backend
uv run pytest tests/integration/test_company_chat_journey.py -q
uv run pytest tests/chat/test_rag_evaluation.py -q
cd ../frontend
corepack pnpm test:e2e -- company-intelligence.spec.ts
```

Expected: all ten browser journeys and all 20 RAG fixtures pass deterministically.

- [ ] **Step 6: Commit acceptance coverage**

```bash
git add backend/tests/fixtures/chat/rag-evaluation.json backend/tests/chat/test_rag_evaluation.py backend/tests/integration/test_company_chat_journey.py backend/tests/e2e_app.py frontend/e2e/company-intelligence.spec.ts
git commit -m "test(chat): cover research chat journeys"
```

## Task 16: Verify Docker, Vercel, documentation, and release gates

**Files:**

- Modify: `vercel.json`
- Modify: `README.md`
- Modify: `docs/deployment.md`
- Modify: `docs/product-status.md`
- Modify: `backend/tests/test_docker_profile.py`
- Modify: `backend/tests/test_vercel_config.py`
- Modify: `backend/tests/test_readme.py`

- [ ] **Step 1: Write deployment-contract tests**

Assert:

- Docker API exposes SSE through the existing port and worker accepts `filing_index`;
- PostgreSQL image/config enables pgvector;
- reverse-proxy guidance disables buffering for chat;
- Vercel Python `maxDuration` remains 300;
- `CHAT_INDEX_WORKFLOW_TRIGGER_URL` is documented and required;
- BFF keeps dynamic streaming and cache disabled;
- delayed FastAPI and BFF chunks arrive incrementally.

- [ ] **Step 2: Confirm the red state**

```bash
cd backend
uv run pytest tests/test_docker_profile.py tests/test_vercel_config.py tests/test_readme.py -q
```

Expected: failures for missing chat deployment and documentation contracts.

- [ ] **Step 3: Update deployment and product documentation**

Document local setup, migrations, pgvector, chat environment keys, RQ worker job, Vercel Workflow trigger, SSE buffering, guest/user limits, seven-day cleanup, private `chat-web/` artifacts, provider credentials, and deterministic tests. Update product status from planned to implemented only after all gates pass. Keep the approved design and this plan linked from `docs/product-status.md`.

- [ ] **Step 4: Run backend quality gates**

```bash
cd backend
uv run ruff check app tests
uv run pytest --cov=app --cov-report=term-missing
```

Expected: Ruff exits `0`, all backend tests pass, and configured coverage remains at or above 80%.

- [ ] **Step 5: Run frontend quality gates**

```bash
cd frontend
corepack pnpm lint
corepack pnpm test
corepack pnpm build
corepack pnpm test:e2e
```

Expected: lint, unit tests, production build, and Playwright exit `0`.

- [ ] **Step 6: Run migration and deployment gates**

```bash
cd backend
uv run alembic upgrade head
uv run alembic downgrade 20260714_0004
uv run alembic upgrade head
uv run pytest tests/test_docker_profile.py tests/test_vercel_config.py tests/test_readme.py -q
git diff --check
```

Expected: reversible migration, deployment tests, docs test, and whitespace check all pass.

- [ ] **Step 7: Inspect scope and secrets**

```bash
git status --short
git diff --stat main...HEAD
rg -n "(sk-[A-Za-z0-9_-]{20,}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|BLOB_READ_WRITE_TOKEN=.+|S3_SECRET_ACCESS_KEY=.+)" --glob '!*.lock' .
```

Expected: only planned files appear; secret scan returns no credential matches.

- [ ] **Step 8: Commit release documentation**

```bash
git add vercel.json README.md docs/deployment.md docs/product-status.md backend/tests/test_docker_profile.py backend/tests/test_vercel_config.py backend/tests/test_readme.py
git commit -m "docs(chat): document research chat deployment"
```

- [ ] **Step 9: Request code review and resolve findings**

Use `superpowers:requesting-code-review` against `main...HEAD`. Address every actionable finding, rerun its directly relevant tests, then repeat Steps 4–7. Record any unavailable external deployment check as an explicit release limitation.

## Spec coverage audit

Before marking the plan complete, verify each acceptance criterion maps to an implementation and test task:

| Acceptance criterion | Implementation tasks | Verification tasks |
|---|---|---|
| Guest/user quota and retention | 3, 4 | 4, 15 |
| Principal and company isolation | 3, 11 | 3, 11, 15 |
| Idempotent latest 10-K indexing | 5 | 5, 16 |
| FTS + pgvector hybrid retrieval | 6 | 6, 15 |
| Agent-selected bounded web search | 8 | 8, 15 |
| Citation-bound material claims | 9 | 9, 15 |
| Four-section bilingual answers | 9, 13 | 9, 13, 15 |
| Incremental FastAPI/BFF streaming | 10, 11, 12 | 10, 12, 16 |
| Refund and replay semantics | 4, 10 | 4, 10, 15 |
| Typed page context | 7, 14 | 7, 14, 15 |
| Desktop/mobile/a11y | 13, 14 | 13, 14, 15 |
| Full release gates | 16 | 16 |

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-14-company-research-chat.md`. Choose one execution mode:

1. **Subagent-Driven (recommended):** execute one task at a time with a fresh implementation worker and review gate, keeping integration in this task.
2. **Inline Execution:** execute the same tasks sequentially in this task with the checkbox file as the source of truth.
