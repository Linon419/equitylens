# Agentic Supply Chain Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the linear upstream/downstream summary with an AI-generated, evidence-backed supply-chain knowledge graph for US-listed companies, with bilingual presentation, exact quota accounting, durable snapshots, and equivalent Docker and Vercel execution paths.

**Architecture:** Extend the existing FastAPI research domain with graph-specific SQLAlchemy models, immutable compressed source artifacts, an evidence-gated Agent pipeline, and a graph publication service. Reuse the current company identity, authentication, job polling, quota identity, RQ, and Vercel Workflow seams. Extend the React company page with a React Flow canvas, deterministic layered layout, a detail/evidence inspector, cached-snapshot refresh states, and browser-language-aware English/Chinese copy.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL/SQLite, OpenAI structured outputs, HTTPX, boto3-compatible object storage, Vercel Blob Python SDK, Redis/RQ, Vercel Workflow, Next.js 16, React 19, TypeScript, `@xyflow/react`, Vitest, Testing Library, Playwright, pytest.

---

## Working rules

- Run every command from `/Users/yang/Documents/Projects/fastapi-langchain-rag/.worktrees/agentic-supply-chain-graph` unless a step names a subdirectory.
- Keep the approved design in `docs/superpowers/specs/2026-07-14-agentic-supply-chain-graph-design.md` as the product source of truth.
- Preserve the existing company-intelligence API and `EvidenceFlow` until the graph endpoint and frontend integration pass regression tests.
- Use official sources only: SEC filings, company investor-relations pages, and official company press releases.
- Store exact source excerpts and content hashes; return public metadata through APIs and keep object-store credentials server-side.
- Keep graph layout deterministic and model-generated content independent from canvas coordinates.
- Treat a quota reservation as a ledger transaction. Consume it once after a newly generated snapshot is accepted; refund it once after a system failure; keep it consumed after an evidence-insufficient terminal result.
- Keep the previous accepted snapshot visible while refresh work is in progress.
- Use English for code, schema names, test names, docs, and commits.
- Use commit subjects in `<type>(scope): <English summary>` format for this feature, matching the user-approved repository history language.

## Delivery map

### New backend files

- `backend/app/models/supply_chain_model.py`
- `backend/app/supply_chain/__init__.py`
- `backend/app/supply_chain/contracts.py`
- `backend/app/supply_chain/schemas.py`
- `backend/app/supply_chain/artifacts.py`
- `backend/app/supply_chain/source_policy.py`
- `backend/app/supply_chain/collector.py`
- `backend/app/supply_chain/entity_resolver.py`
- `backend/app/supply_chain/prompts.py`
- `backend/app/supply_chain/openai_agent.py`
- `backend/app/supply_chain/validator.py`
- `backend/app/supply_chain/repository.py`
- `backend/app/supply_chain/service.py`
- `backend/app/supply_chain/pipeline.py`
- `backend/app/migrations/versions/20260714_0004_agentic_supply_chain_graph.py`
- `backend/tests/fixtures/supply_chain/aapl_sources.json`
- `backend/tests/fixtures/supply_chain/aapl_draft.json`
- `backend/tests/fixtures/supply_chain/aapl_verification.json`
- `backend/tests/supply_chain/test_schemas.py`
- `backend/tests/supply_chain/test_artifacts.py`
- `backend/tests/supply_chain/test_source_policy.py`
- `backend/tests/supply_chain/test_collector.py`
- `backend/tests/supply_chain/test_entity_resolver.py`
- `backend/tests/supply_chain/test_openai_agent.py`
- `backend/tests/supply_chain/test_validator.py`
- `backend/tests/supply_chain/test_repository.py`
- `backend/tests/supply_chain/test_service.py`
- `backend/tests/supply_chain/test_pipeline.py`
- `backend/tests/models/test_supply_chain_models.py`
- `backend/tests/test_supply_chain_migration.py`

### Modified backend files

- `backend/pyproject.toml`
- `backend/uv.lock`
- `backend/.env.example`
- `.env.example`
- `backend/app/core/config.py`
- `backend/app/models/__init__.py`
- `backend/app/models/job_model.py`
- `backend/app/providers/contracts.py`
- `backend/app/quota/repository.py`
- `backend/app/quota/service.py`
- `backend/app/jobs/schemas.py`
- `backend/app/jobs/state.py`
- `backend/app/jobs/service.py`
- `backend/app/jobs/tasks.py`
- `backend/app/jobs/rq_backend.py`
- `backend/app/jobs/vercel_backend.py`
- `backend/app/api/deps.py`
- `backend/app/api/main.py`
- `backend/app/api/routes/companies.py`
- `backend/app/api/routes/jobs.py`
- `backend/app/api/routes/internal_jobs.py`
- `backend/tests/core/test_config.py`
- `backend/tests/quota/test_service.py`
- `backend/tests/quota/test_sqlite_repository.py`
- `backend/tests/quota/test_postgres_repository.py`
- `backend/tests/jobs/backend_contract.py`
- `backend/tests/jobs/test_state.py`
- `backend/tests/jobs/test_service.py`
- `backend/tests/jobs/test_tasks.py`
- `backend/tests/jobs/test_rq_backend.py`
- `backend/tests/jobs/test_vercel_backend.py`
- `backend/tests/api/conftest.py`
- `backend/tests/api/test_companies.py`
- `backend/tests/api/test_jobs.py`
- `backend/tests/api/test_internal_jobs.py`
- `backend/tests/e2e_app.py`

### New frontend files

- `frontend/src/features/company/supply-chain-graph.tsx`
- `frontend/src/features/company/supply-chain-graph.test.tsx`
- `frontend/src/features/company/supply-chain-layout.ts`
- `frontend/src/features/company/supply-chain-layout.test.ts`
- `frontend/src/features/company/supply-chain-node.tsx`
- `frontend/src/features/company/supply-chain-edge.tsx`
- `frontend/src/features/company/supply-chain-inspector.tsx`
- `frontend/src/features/company/supply-chain-legend.tsx`
- `frontend/src/app/api/internal/workflows/supply-chain-graph/route.ts`
- `frontend/src/app/api/internal/workflows/supply-chain-graph/route.test.ts`
- `frontend/src/workflows/supply-chain-graph.ts`
- `frontend/src/workflows/supply-chain-graph.test.ts`

### Modified frontend and documentation files

- `frontend/package.json`
- `frontend/pnpm-lock.yaml`
- `frontend/src/lib/research/types.ts`
- `frontend/src/app/api/research/[...path]/route.ts`
- `frontend/src/app/api/research/[...path]/route.test.ts`
- `frontend/src/features/company/company-page.tsx`
- `frontend/src/features/company/company-page.test.tsx`
- `frontend/src/features/company/copy.ts`
- `frontend/src/features/company/test-fixtures.ts`
- `frontend/src/app/globals.css`
- `frontend/e2e/company-intelligence.spec.ts`
- `README.md`
- `docs/deployment.md`
- `docs/product-status.md`

## Task 1: Lock graph configuration and runtime dependencies

**Files:**

- Modify: `backend/app/core/config.py`
- Modify: `backend/tests/core/test_config.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Modify: `backend/.env.example`
- Modify: `.env.example`
- Modify: `frontend/package.json`
- Modify: `frontend/pnpm-lock.yaml`

- [ ] **Step 1: Write failing configuration tests**

Add focused assertions to `backend/tests/core/test_config.py`:

```python
def test_supply_chain_graph_defaults_follow_research_model(monkeypatch):
    monkeypatch.setenv("RESEARCH_MODEL", "gpt-5-mini")
    settings = Settings(_env_file=None)

    assert settings.SUPPLY_CHAIN_GRAPH_MODEL == "gpt-5-mini"
    assert settings.SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION == "supply-chain-graph.v1"
    assert settings.SUPPLY_CHAIN_GRAPH_PROMPT_VERSION == "supply-chain-graph.2026-07-14"
    assert settings.SUPPLY_CHAIN_GRAPH_MAX_NODES == 40
    assert settings.SUPPLY_CHAIN_GRAPH_MIN_NODES == 25
    assert settings.SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD == 0.75
```

Extend the existing Vercel profile test to require `SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL` alongside the company-intelligence workflow trigger.

- [ ] **Step 2: Run the focused test and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py -q
```

Expected: failure because graph settings and cross-field validation are absent.

- [ ] **Step 3: Add graph settings and validation**

Add these settings to `backend/app/core/config.py` and extend the existing model validator:

```python
SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE: str | None = None
SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION: str = "supply-chain-graph.v1"
SUPPLY_CHAIN_GRAPH_PROMPT_VERSION: str = "supply-chain-graph.2026-07-14"
SUPPLY_CHAIN_GRAPH_MIN_NODES: int = 25
SUPPLY_CHAIN_GRAPH_MAX_NODES: int = 40
SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD: float = 0.75
SUPPLY_CHAIN_GRAPH_CACHE_TTL_HOURS: int = 24
SUPPLY_CHAIN_GRAPH_SOURCE_LIMIT: int = 24
SUPPLY_CHAIN_GRAPH_SOURCE_BYTES: int = 8_000_000
GRAPH_ARTIFACT_PREFIX: str = "supply-chain"
SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL: str | None = None

@property
def SUPPLY_CHAIN_GRAPH_MODEL(self) -> str:
    return self.SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE or self.RESEARCH_MODEL
```

Validate `MIN_NODES >= 1`, `MAX_NODES >= MIN_NODES`, and the threshold within `[0, 1]`. Reuse the existing `OBJECT_STORAGE_PROVIDER`, S3 credentials, Vercel Blob token, and deployment-profile validation.

- [ ] **Step 4: Add pinned runtime dependencies**

Use the package managers so lockfiles remain authoritative:

```bash
cd backend
uv remove --group worker boto3
uv add "boto3>=1.39,<2" "tldextract>=5.3,<6" "vercel>=0.3,<1"
cd ../frontend
corepack pnpm add @xyflow/react@12.11.2
```

Confirm that `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, and `frontend/pnpm-lock.yaml` changed together.

- [ ] **Step 5: Document environment keys**

Add the graph settings to both backend-facing env examples. Use `memory` for local unit tests, `s3` for Docker/MinIO, and `vercel_blob` for Vercel. Keep all credential values empty.

```dotenv
SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE=
SUPPLY_CHAIN_GRAPH_MAX_NODES=40
SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD=0.75
GRAPH_ARTIFACT_PREFIX=supply-chain
SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL=
```

- [ ] **Step 6: Run configuration and install validation**

Run:

```bash
cd backend
uv run pytest tests/core/test_config.py -q
uv run python -c "import boto3, tldextract; from vercel.blob import AsyncBlobClient"
cd ../frontend
corepack pnpm exec node -e "require.resolve('@xyflow/react')"
```

Expected: configuration tests pass and both dependency checks exit `0`.

- [ ] **Step 7: Commit the dependency boundary**

```bash
git add .env.example backend/.env.example backend/app/core/config.py backend/tests/core/test_config.py backend/pyproject.toml backend/uv.lock frontend/package.json frontend/pnpm-lock.yaml
git commit -m "chore(graph): add graph runtime dependencies"
```

## Task 2: Add graph persistence models and migration

**Files:**

- Create: `backend/app/models/supply_chain_model.py`
- Create: `backend/app/migrations/versions/20260714_0004_agentic_supply_chain_graph.py`
- Create: `backend/tests/models/test_supply_chain_models.py`
- Create: `backend/tests/test_supply_chain_migration.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/job_model.py`

- [ ] **Step 1: Write failing model tests**

Cover model metadata, uniqueness, lifecycle fields, and relationships:

```python
def test_graph_snapshot_has_versioned_publication_metadata():
    snapshot = SupplyChainGraphSnapshot(
        company_id=1,
        status="drafted",
        schema_version="supply-chain-graph.v1",
        prompt_version="supply-chain-graph.2026-07-14",
        model_id="gpt-5-mini",
        source_fingerprint="a" * 64,
    )

    assert snapshot.status == "drafted"
    assert snapshot.node_count == 0
    assert snapshot.edge_count == 0
    assert snapshot.evidence_coverage == "insufficient_evidence"


def test_graph_edge_identity_is_stable():
    edge = SupplyChainGraphEdge(
        snapshot_id=uuid4(),
        edge_key="company:0001046179|supplies|company:0000320193",
        source_node_id=uuid4(),
        target_node_id=uuid4(),
        relationship_type="supplies",
        evidence_status="verified",
        confidence="High",
    )

    assert "|supplies|" in edge.edge_key
```

Also assert that `IngestionJob` exposes `graph_snapshot_id` and that each quota reservation has one unique `job_id`.

- [ ] **Step 2: Run the model test and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/models/test_supply_chain_models.py -q
```

Expected: import failure for `app.models.supply_chain_model`.

- [ ] **Step 3: Implement the normalized graph model**

Create six SQLModel models, following the current model style:

```python
class SupplyChainGraphSnapshot(SQLModel, table=True):
    __tablename__ = "supply_chain_graph_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "source_fingerprint",
            "schema_version",
            "prompt_version",
            "model_id",
            name="uq_supply_chain_graph_snapshot_version",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    status: str = Field(max_length=32, index=True)
    schema_version: str = Field(max_length=64)
    prompt_version: str = Field(max_length=64)
    model_id: str = Field(max_length=128)
    source_fingerprint: str = Field(max_length=64, index=True)
    content_en: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    content_zh: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    evidence_coverage: str = Field(
        default="insufficient_evidence",
        max_length=32,
    )
    overall_confidence: str | None = Field(default=None, max_length=16)
    node_count: int = 0
    edge_count: int = 0
    generated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    verified_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class SupplyChainGraphNode(SQLModel, table=True):
    __tablename__ = "supply_chain_graph_node"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "node_key",
            name="uq_supply_chain_graph_node_key",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    snapshot_id: UUID = Field(
        foreign_key="supply_chain_graph_snapshot.id",
        ondelete="CASCADE",
        index=True,
    )
    node_key: str = Field(max_length=160)
    kind: str = Field(max_length=24)
    layer: str = Field(max_length=24)
    company_id: int | None = Field(default=None, foreign_key="company.id")
    symbol: str | None = Field(default=None, max_length=16)
    cik: str | None = Field(default=None, max_length=16)
    label_en: str = Field(max_length=255)
    label_zh: str = Field(max_length=255)
    description_en: str = Field(sa_column=Column(Text(), nullable=False))
    description_zh: str = Field(sa_column=Column(Text(), nullable=False))
    importance: Decimal = Field(sa_column=Column(Numeric(5, 4), nullable=False))
    confidence: str = Field(max_length=16)
    rank: int = 0
```

Add matching models for:

- `SupplyChainGraphEdge`: stable `edge_key`, node foreign-key endpoints, relationship type, evidence status, confidence label, bilingual explanations, first/last evidence dates.
- `GraphOfficialSource`: publisher, canonical URL, source type, title, published/fetched timestamps, content hash, immutable `artifact_key`.
- `GraphEdgeCitation`: edge/source foreign keys, exact excerpt, source anchor, and support role.
- `AgentQuotaReservation`: unique job ID, principal type/hash, optional IP hash, usage date, principal/IP daily limits, state (`reserved`, `consumed`, `refunded`), and created/updated/consumed/refunded timestamps.

Add `graph_snapshot_id` to `IngestionJob`. Keep the current `snapshot_id` foreign key for company-intelligence compatibility.

- [ ] **Step 4: Register the models**

Export all graph models from `backend/app/models/__init__.py` so Alembic metadata and tests import them.

- [ ] **Step 5: Write the migration test**

`backend/tests/test_supply_chain_migration.py` must migrate an empty SQLite database to head, inspect all graph tables and key indexes, downgrade one revision, and upgrade again. Assert:

```python
assert {
    "supply_chain_graph_snapshot",
    "supply_chain_graph_node",
    "supply_chain_graph_edge",
    "graph_official_source",
    "graph_edge_citation",
    "agent_quota_reservation",
}.issubset(table_names)
```

- [ ] **Step 6: Generate and edit the Alembic migration**

Run:

```bash
cd backend
uv run alembic revision --autogenerate -m "add agentic supply chain graph"
```

Rename the file to `20260714_0004_agentic_supply_chain_graph.py`, set `revision = "20260714_0004"`, `down_revision = "20260713_0003"`, and review every foreign key, unique constraint, check constraint, and index. Add explicit checks for importance within `[0, 1]`, nonnegative counts/ranks, supported snapshot statuses, evidence-coverage labels, confidence labels, node kinds/layers, edge relationship/evidence statuses, source/support-role types, and reservation states.

- [ ] **Step 7: Run model and migration tests**

Run:

```bash
cd backend
uv run pytest tests/models/test_supply_chain_models.py tests/test_supply_chain_migration.py tests/test_migrations.py -q
```

Expected: all selected tests pass; Alembic reports one head.

- [ ] **Step 8: Commit persistence**

```bash
git add backend/app/models backend/app/migrations/versions/20260714_0004_agentic_supply_chain_graph.py backend/tests/models/test_supply_chain_models.py backend/tests/test_supply_chain_migration.py
git commit -m "feat(graph): add graph persistence model"
```

## Task 3: Define structured Agent contracts and deterministic fixtures

**Files:**

- Create: `backend/app/supply_chain/__init__.py`
- Create: `backend/app/supply_chain/contracts.py`
- Create: `backend/app/supply_chain/schemas.py`
- Create: `backend/tests/supply_chain/test_schemas.py`
- Create: `backend/tests/fixtures/supply_chain/aapl_sources.json`
- Create: `backend/tests/fixtures/supply_chain/aapl_draft.json`
- Create: `backend/tests/fixtures/supply_chain/aapl_verification.json`

- [ ] **Step 1: Write the schema tests before implementation**

Cover valid parsing and every publication invariant:

```python
def test_graph_draft_parses_stable_entity_and_evidence_keys(aapl_draft):
    draft = GraphDraft.model_validate(aapl_draft)

    assert draft.focus_node_key == "company:0000320193"
    assert {node.layer for node in draft.nodes} == {"upstream", "core", "downstream"}
    assert all(edge.evidence_refs for edge in draft.edges)


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_stays_in_closed_unit_interval(confidence):
    with pytest.raises(ValidationError):
        EvidenceReference(
            source_key="sec:aapl:10-k:2025",
            excerpt="Apple relies on manufacturing partners.",
            locator="Item 1, p. 12",
            confidence=confidence,
        )
```

Also test duplicate node keys, orphan endpoints, unsupported source types, unsupported edge types, missing English labels, and a graph above 40 nodes.

- [ ] **Step 2: Run the schema test and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_schemas.py -q
```

Expected: import failure for graph schemas.

- [ ] **Step 3: Implement Pydantic graph contracts**

Use closed enums and frozen evidence records:

```python
NodeKind = Literal["company", "business", "product", "category"]
NodeLayer = Literal["upstream", "core", "downstream"]
EdgeType = Literal[
    "supplies",
    "manufactures_for",
    "distributes_for",
    "sells_to",
    "licenses_to",
    "platform_for",
    "component_of",
    "serves_market",
]
EvidenceStatus = Literal["verified", "potential", "internal"]
VerificationVerdict = Literal["verified", "potential", "rejected", "conflicted"]
SourceType = Literal[
    "sec_filing",
    "annual_report",
    "ir_page",
    "official_press_release",
]


class EvidenceReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_key: str
    excerpt: str = Field(min_length=20, max_length=2_000)
    locator: str = Field(min_length=1, max_length=240)
    support_role: Literal["primary", "corroborating"] = "primary"
    confidence: float = Field(ge=0, le=1)


class GraphDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    focus_node_key: str
    thesis_en: str
    nodes: list[GraphNodeDraft] = Field(min_length=1, max_length=40)
    edges: list[GraphEdgeDraft]
```

Define `OfficialSourceDocument`, `GraphNodeDraft`, `GraphEdgeDraft`, `GraphDraft`, `EdgeVerification`, `GraphVerification`, `AcceptedGraph`, `PublicGraphNode`, `PublicGraphEdge`, `PublicGraphSource`, `PublicGraphCitation`, `PublicSupplyChainGraph`, `GraphRefreshRequest`, and `GraphRefreshResponse`.

Use a model-level validator to enforce unique keys, one focus node, valid endpoints, and at least one evidence reference for every `verified` or `potential` edge.

- [ ] **Step 4: Define dependency protocols**

Add narrow async protocols to `contracts.py`:

```python
class GraphArtifactStore(Protocol):
    async def put(
        self,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> str: ...

    async def get(self, *, artifact_key: str) -> bytes: ...


class OfficialSourceTools(Protocol):
    async def list_official_sources(
        self,
        *,
        company: CompanyIdentity,
        query: str,
        source_types: tuple[SourceType, ...],
    ) -> list[OfficialSourceMetadata]: ...

    async def fetch_official_source(self, *, source_id: str) -> OfficialSourceDocument: ...

    def selected_documents(self, source_ids: Sequence[str]) -> list[OfficialSourceDocument]: ...


class OfficialSourceCollector(Protocol):
    async def prepare_catalog(self, *, company: CompanyIdentity) -> OfficialSourceTools: ...


class SupplyChainAgent(Protocol):
    async def plan_sources(
        self,
        *,
        company: CompanyIdentity,
        tools: OfficialSourceTools,
    ) -> SourcePlan: ...
    async def extract_graph(self, *, company: CompanyIdentity, sources: list[OfficialSourceDocument]) -> GraphDraft: ...
    async def verify_graph(self, *, draft: GraphDraft, sources: list[OfficialSourceDocument]) -> GraphVerification: ...
    async def localize_graph(self, *, graph: AcceptedGraph, locale: Literal["zh"] = "zh") -> GraphLocalization: ...
```

Add `EntityResolver`, `SupplyChainGraphRepository`, and `GraphQuotaLedger` protocols with only the methods used by the pipeline.

- [ ] **Step 5: Add deterministic AAPL fixtures**

Create a compact set of 25 nodes and evidence-backed edges spanning:

- upstream semiconductor manufacturing, display components, memory, and contract manufacturing;
- Apple as the focus company plus core businesses/products;
- downstream carriers, distributors, enterprise channels, and end markets;
- at least two `potential` edges and one adversarial verification rejection;
- exact excerpts referencing a source key and locator.

Fixtures must contain synthetic test text clearly marked as fixture data and stable IDs. They must never fetch the network.

- [ ] **Step 6: Run schema tests**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_schemas.py -q
```

Expected: all schema and fixture validation tests pass.

- [ ] **Step 7: Commit contracts**

```bash
git add backend/app/supply_chain backend/tests/supply_chain/test_schemas.py backend/tests/fixtures/supply_chain
git commit -m "feat(graph): define agent graph contracts"
```

## Task 4: Implement immutable artifact stores

**Files:**

- Create: `backend/app/supply_chain/artifacts.py`
- Create: `backend/tests/supply_chain/test_artifacts.py`
- Modify: `backend/app/api/deps.py`

- [ ] **Step 1: Write storage contract tests**

Use one parametrized contract for memory, S3, and Vercel adapters. Stub SDK clients for external stores:

```python
@pytest.mark.anyio
async def test_memory_store_round_trips_immutable_bytes():
    store = InMemoryGraphArtifactStore()
    body = gzip.compress(b"official source body")
    key = await store.put(
        object_key="supply-chain/sha256/abc.html.gz",
        body=body,
        content_type="application/gzip",
        sha256=sha256(body).hexdigest(),
    )

    assert await store.get(artifact_key=key) == body


@pytest.mark.anyio
async def test_s3_store_writes_private_content_with_hash_metadata(recording_s3):
    store = S3GraphArtifactStore(client=recording_s3, bucket="research", prefix="supply-chain")
    await store.put(object_key="abc.gz", body=b"payload", content_type="application/gzip", sha256="abc")

    assert recording_s3.put_calls[0]["Metadata"] == {"sha256": "abc"}
```

For Vercel, assert `access="private"`, `add_random_suffix=False`, `overwrite=False`, and exact buffered-byte reads from `GetBlobResult.content`.

- [ ] **Step 2: Run the storage test and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_artifacts.py -q
```

Expected: import failure for artifact adapters.

- [ ] **Step 3: Implement memory and S3 adapters**

Use content-addressed keys. Keep boto3 blocking calls away from the event loop:

```python
class S3GraphArtifactStore:
    async def put(self, *, object_key: str, body: bytes, content_type: str, sha256: str) -> str:
        key = f"{self._prefix}/{object_key}".lstrip("/")
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            Metadata={"sha256": sha256},
            IfNoneMatch="*",
        )
        return key

    async def get(self, *, artifact_key: str) -> bytes:
        response = await asyncio.to_thread(
            self._client.get_object,
            Bucket=self._bucket,
            Key=artifact_key,
        )
        return await asyncio.to_thread(response["Body"].read)
```

The in-memory implementation must reject overwrite attempts with different bytes for the same key.
For an S3 precondition failure, read object metadata: return the existing key when its hash matches and raise `GraphArtifactConflict` when it differs.

- [ ] **Step 4: Implement the Vercel Blob adapter**

Use the official Python SDK:

```python
class VercelBlobGraphArtifactStore:
    async def put(self, *, object_key: str, body: bytes, content_type: str, sha256: str) -> str:
        result = await self._client.put(
            object_key,
            body,
            access="private",
            add_random_suffix=False,
            overwrite=False,
            content_type=content_type,
        )
        return result.url

    async def get(self, *, artifact_key: str) -> bytes:
        result = await self._client.get(artifact_key, access="private", use_cache=True)
        if result is None or result.status_code != 200:
            raise GraphArtifactNotFound(artifact_key)
        return result.content
```

Wrap provider exceptions in graph-domain errors and avoid returning tokens, request headers, or SDK payloads in error details.

- [ ] **Step 5: Wire artifact-store dependency selection**

Add `get_graph_artifact_store()` to `backend/app/api/deps.py`. Select `S3GraphArtifactStore` when `OBJECT_STORAGE_PROVIDER=s3` and `VercelBlobGraphArtifactStore` when it equals `vercel_blob`. Override this dependency with `InMemoryGraphArtifactStore` in tests. Cache SDK clients at process scope and keep storage methods request-safe.

- [ ] **Step 6: Run storage tests and type checks**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_artifacts.py -q
uv run ruff check app/supply_chain/artifacts.py app/api/deps.py tests/supply_chain/test_artifacts.py
```

Expected: all selected tests pass and Ruff exits `0`.

- [ ] **Step 7: Commit storage adapters**

```bash
git add backend/app/supply_chain/artifacts.py backend/app/api/deps.py backend/tests/supply_chain/test_artifacts.py
git commit -m "feat(graph): add immutable artifact stores"
```

## Task 5: Enforce official-source security and collect immutable evidence

**Files:**

- Create: `backend/app/supply_chain/source_policy.py`
- Create: `backend/app/supply_chain/collector.py`
- Create: `backend/tests/supply_chain/test_source_policy.py`
- Create: `backend/tests/supply_chain/test_collector.py`
- Modify: `backend/app/providers/contracts.py`
- Modify: `backend/app/api/deps.py`

- [ ] **Step 1: Write failing source-policy tests**

Test canonical URLs, SEC hosts, registered company hosts, redirects, DNS results, and bounded responses:

```python
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "https://user:secret@investor.apple.com/report",
        "https://investor.apple.com:444/report",
        "file:///etc/passwd",
    ],
)
def test_source_policy_rejects_unsafe_urls(url):
    with pytest.raises(SourcePolicyError):
        validate_official_source_url(url, trusted_hosts={"investor.apple.com"})


def test_source_policy_accepts_sec_and_registered_ir_hosts():
    assert validate_official_source_url(
        "https://www.sec.gov/Archives/edgar/data/320193/report.htm",
        trusted_hosts={"investor.apple.com"},
    ).host == "www.sec.gov"
```

Add a resolver stub that returns loopback/private/link-local IPs and assert the fetch is blocked before the HTTP request. Add a redirect test where the first host is trusted and the target host is unsafe.

- [ ] **Step 2: Run source-policy tests and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_source_policy.py -q
```

Expected: import failure for `source_policy`.

- [ ] **Step 3: Implement the allowlist and SSRF gate**

Create a `ValidatedSourceUrl` value object and pure validation functions. Accept HTTPS on:

- `sec.gov`, `www.sec.gov`, `data.sec.gov`, and `archives.sec.gov`;
- issuer website and investor-relations hosts obtained from the saved SEC submissions payload or issuer links in a saved SEC filing;
- explicit IR and newsroom subdomains whose registrable domain matches one of those SEC-anchored issuer hosts.

Use `tldextract.TLDExtract(suffix_list_urls=())` for offline registrable-domain checks. Use `ipaddress.ip_address` after DNS resolution and reject loopback, private, link-local, multicast, reserved, and unspecified results. Normalize IDNA hostnames, strip fragments, reject embedded credentials, cap redirects at three, and re-run the full gate for each redirect target.

- [ ] **Step 4: Write collector tests**

Use `httpx.MockTransport`, the current SEC provider fake, and the in-memory artifact store:

```python
@pytest.mark.anyio
async def test_collector_hashes_compresses_and_stores_official_sources(
    collector,
    artifact_store,
):
    tools = await collector.prepare_catalog(company=AAPL_IDENTITY)
    metadata = await tools.list_official_sources(
        company=AAPL_IDENTITY,
        query="manufacturing suppliers and distribution channels",
        source_types=("sec_filing", "annual_report", "ir_page"),
    )
    sources = [await tools.fetch_official_source(source_id=item.source_id) for item in metadata[:3]]

    assert len(sources[0].content_hash) == 64
    compressed = await artifact_store.get(artifact_key=sources[0].artifact_key)
    assert gzip.decompress(compressed).startswith(b"<html")
    assert sources[0].body_text


@pytest.mark.anyio
async def test_collector_stops_at_global_source_byte_limit(collector):
    tools = await collector.prepare_catalog(company=AAPL_IDENTITY)
    with pytest.raises(SourceCollectionError, match="SOURCE_BUDGET_EXCEEDED"):
        await tools.fetch_official_source(source_id=OVERSIZED_SOURCE_ID)
```

Also test unsupported content types, decompression bombs, a source limit above 24, duplicate canonical URLs, timeouts, robots exclusion for issuer pages, per-host pacing, and request headers that include the configured SEC user agent.

- [ ] **Step 5: Run collector tests and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_collector.py -q
```

Expected: import failure for the collector.

- [ ] **Step 6: Implement collection and text extraction**

Reuse `SecClient` for filing discovery/downloads. Use a dedicated bounded `httpx.AsyncClient` for IR and press pages. Cache issuer `robots.txt` rules for the run, respect disallowed paths, and pace requests per host through an injected monotonic clock/rate limiter. Stream every response while enforcing per-source and total byte budgets. Accept HTML, plain text, and PDF content already supported by the configured parser boundary.

```python
async def _persist_source(
    self,
    *,
    source_key: str,
    canonical_url: str,
    body: bytes,
    content_type: str,
) -> OfficialSourceDocument:
    digest = hashlib.sha256(body).hexdigest()
    compressed = gzip.compress(body, compresslevel=6, mtime=0)
    artifact_key = await self._artifacts.put(
        object_key=f"sha256/{digest}.gz",
        body=compressed,
        content_type="application/gzip",
        sha256=hashlib.sha256(compressed).hexdigest(),
    )
    return OfficialSourceDocument(
        source_key=source_key,
        canonical_url=canonical_url,
        content_hash=digest,
        artifact_key=artifact_key,
        body_text=extract_official_text(body, content_type=content_type),
    )
```

`prepare_catalog()` discovers metadata from the latest SEC filing set plus bounded issuer-owned IR/newsroom index pages. `list_official_sources()` searches only that catalog. `fetch_official_source()` passes the security gate, saves the immutable artifact, and returns bounded text. `selected_documents()` returns previously fetched documents only.

Canonicalize visible text with Beautiful Soup, preserve headings and table row boundaries, cap model-facing text per source, and retain the full compressed artifact for audit.

- [ ] **Step 7: Extend provider contracts and dependency wiring**

Add only graph-required methods to the official-source provider boundary. Keep the existing market-data and filing contracts stable. Wire `OfficialSourceCollectorImpl` in `backend/app/api/deps.py` using the existing SEC client, HTTP client, parser, settings, and graph artifact store.

- [ ] **Step 8: Run source security and collector validation**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_source_policy.py tests/supply_chain/test_collector.py tests/filings/test_service.py -q
uv run ruff check app/supply_chain/source_policy.py app/supply_chain/collector.py tests/supply_chain
```

Expected: selected tests pass and Ruff exits `0`.

- [ ] **Step 9: Commit collection**

```bash
git add backend/app/supply_chain/source_policy.py backend/app/supply_chain/collector.py backend/app/providers/contracts.py backend/app/api/deps.py backend/tests/supply_chain/test_source_policy.py backend/tests/supply_chain/test_collector.py
git commit -m "feat(graph): collect official source evidence"
```

## Task 6: Resolve graph entities deterministically

**Files:**

- Create: `backend/app/supply_chain/entity_resolver.py`
- Create: `backend/tests/supply_chain/test_entity_resolver.py`

- [ ] **Step 1: Write failing entity-resolution tests**

Cover CIK, ticker, normalized company name, product/category keys, aliases, and ambiguity:

```python
@pytest.mark.anyio
async def test_cik_is_the_primary_company_identity(resolver):
    resolved = await resolver.resolve(
        EntityCandidate(
            name="Apple Inc.",
            symbol="AAPL",
            cik="0000320193",
            kind="company",
        )
    )

    assert resolved.node_key == "company:0000320193"
    assert resolved.resolution_basis == "cik"


@pytest.mark.anyio
async def test_ambiguous_name_stays_unresolved(resolver):
    resolved = await resolver.resolve(
        EntityCandidate(name="Global Foundry", kind="company")
    )

    assert resolved.company_id is None
    assert resolved.confidence < 0.8
```

Add tests showing that `TSMC`, `Taiwan Semiconductor Manufacturing Company`, and CIK `0001046179` converge to one stable key when the SEC directory supplies the match.

- [ ] **Step 2: Run the resolver test and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_entity_resolver.py -q
```

Expected: import failure for the resolver.

- [ ] **Step 3: Implement the resolution ladder**

Resolve in this order:

1. exact normalized CIK;
2. exact US ticker from the existing company directory;
3. normalized legal name with one exact company-directory result;
4. deterministic non-company key based on kind and normalized label;
5. unresolved company key based on a content hash plus low confidence.

```python
def non_company_node_key(kind: NodeKind, label: str) -> str:
    normalized = unicodedata.normalize("NFKC", label).casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:10]
    return f"{kind}:{slug[:48]}:{digest}"
```

Keep resolution evidence in the validated snapshot audit content. Require a higher verification threshold for unresolved companies before publication.

- [ ] **Step 4: Add merge and deduplication behavior**

Implement `resolve_draft()` to:

- merge duplicate nodes into the most authoritative identity;
- redirect edge endpoints to canonical keys;
- merge identical evidence references;
- preserve the highest importance and confidence values;
- record discarded aliases for traceability;
- keep product and business nodes distinct when their kinds differ.

- [ ] **Step 5: Run resolver validation**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_entity_resolver.py -q
uv run ruff check app/supply_chain/entity_resolver.py tests/supply_chain/test_entity_resolver.py
```

Expected: all resolver tests pass and Ruff exits `0`.

- [ ] **Step 6: Commit entity resolution**

```bash
git add backend/app/supply_chain/entity_resolver.py backend/tests/supply_chain/test_entity_resolver.py
git commit -m "feat(graph): resolve graph entities"
```

## Task 7: Implement the structured-output supply-chain Agent

**Files:**

- Create: `backend/app/supply_chain/prompts.py`
- Create: `backend/app/supply_chain/openai_agent.py`
- Create: `backend/tests/supply_chain/test_openai_agent.py`
- Modify: `backend/app/api/deps.py`

- [ ] **Step 1: Write failing Agent adapter tests**

Use a recording structured-output model fake and assert four bounded stages:

```python
@pytest.mark.anyio
async def test_agent_uses_official_source_tools_and_four_structured_stages(
    recording_model,
    official_source_tools,
    sources,
):
    agent = OpenAISupplyChainAgent(
        model=recording_model,
        prompt_version="supply-chain-graph.2026-07-14",
    )

    plan = await agent.plan_sources(
        company=AAPL_IDENTITY,
        tools=official_source_tools,
    )
    draft = await agent.extract_graph(company=AAPL_IDENTITY, sources=sources)
    verification = await agent.verify_graph(draft=draft, sources=sources)
    localization = await agent.localize_graph(graph=ACCEPTED_GRAPH)

    assert [call.schema for call in recording_model.calls] == [
        SourcePlan,
        GraphDraft,
        GraphVerification,
        GraphLocalization,
    ]
    assert all(call.prompt_version == "supply-chain-graph.2026-07-14" for call in recording_model.calls)
    assert official_source_tools.calls == [
        "list_official_sources",
        "fetch_official_source",
        "fetch_official_source",
    ]
    assert set(plan.source_ids).issubset(official_source_tools.fetched_ids)
```

Add tests for invalid structured output, retry exhaustion, token-budget truncation, prompt-injection text in a filing, unknown citations, unknown tool names, invalid tool arguments, more than eight tool calls, and provider errors mapped to retryable graph-domain errors.

- [ ] **Step 2: Run the Agent test and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_openai_agent.py -q
```

Expected: import failure for the graph Agent.

- [ ] **Step 3: Write versioned prompts as constants**

Create separate system/task prompt builders for:

- `plan_sources`: search the prepared official catalog, inspect selected sources, and return source IDs plus relevant sections;
- `extract_graph`: identify focus business, products/categories, companies, and supported relations;
- `verify_graph`: challenge every edge, mark contradictions, and assign `verified`, `potential`, or `rejected`;
- `localize_graph`: translate accepted labels, descriptions, explanations, and thesis into Simplified Chinese while preserving IDs, symbols, CIKs, URLs, dates, numeric values, and excerpts.

For `plan_sources`, instruct the model to select only source IDs returned by `list_official_sources` and inspected through `fetch_official_source`. Every prompt must state that source text is untrusted data and that instructions embedded in documents carry zero authority. Include the schema version and prompt version in every request.

- [ ] **Step 4: Implement the bounded official-source tool loop**

Bind two strict Pydantic tool schemas with `ChatOpenAI.bind_tools`: `ListOfficialSources` and `FetchOfficialSource`. Run at most eight tool calls and append one `ToolMessage` per validated result.

```python
async def plan_sources(
    self,
    *,
    company: CompanyIdentity,
    tools: OfficialSourceTools,
) -> SourcePlan:
    model_with_tools = self._model.bind_tools(
        [ListOfficialSources, FetchOfficialSource],
        strict=True,
    )
    messages: list[BaseMessage] = build_source_planning_messages(company)
    tool_call_count = 0
    while tool_call_count < 8:
        response = await model_with_tools.ainvoke(messages)
        messages.append(response)
        if not response.tool_calls:
            return await self._finalize_source_plan(company=company, messages=messages)
        for call in response.tool_calls:
            tool_call_count += 1
            result = await execute_official_source_tool(call, company=company, tools=tools)
            messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=call["id"],
                )
            )
    raise SupplyChainAgentError("SOURCE_TOOL_LIMIT_REACHED", retryable=False)
```

Validate source IDs against the prepared catalog on every fetch. Return bounded metadata/text only. Exclude open web search and arbitrary URL fetching from the Agent tool set.

- [ ] **Step 5: Implement the OpenAI structured-output adapter**

Reuse the current project pattern from `backend/app/research/openai_generator.py`. Keep one adapter method per stage:

```python
async def _invoke_structured[T: BaseModel](
    self,
    *,
    schema: type[T],
    system_prompt: str,
    user_payload: dict[str, object],
) -> T:
    runnable = self._model.with_structured_output(schema, strict=True)
    try:
        result = await runnable.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=json.dumps(user_payload, ensure_ascii=False)),
            ]
        )
    except Exception as error:
        raise SupplyChainAgentError.from_provider(error) from error
    return schema.model_validate(result)
```

Use `_invoke_structured()` for the final `SourcePlan`, graph draft, adversarial verification, and localization. Apply per-stage timeouts and one structured-output repair attempt. Log request IDs, model ID, stage, duration, tool counts, and token counts. Exclude source bodies, excerpts, and credentials from logs.

- [ ] **Step 6: Wire the Agent dependency**

Add `get_supply_chain_agent()` to `backend/app/api/deps.py`. Construct the model with `SUPPLY_CHAIN_GRAPH_MODEL`, temperature `0`, and provider timeout settings. Keep tests able to override the protocol dependency.

- [ ] **Step 7: Run Agent validation**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_openai_agent.py tests/research/test_service.py -q
uv run ruff check app/supply_chain/prompts.py app/supply_chain/openai_agent.py tests/supply_chain/test_openai_agent.py
```

Expected: selected tests pass and Ruff exits `0`.

- [ ] **Step 8: Commit Agent generation**

```bash
git add backend/app/supply_chain/prompts.py backend/app/supply_chain/openai_agent.py backend/app/api/deps.py backend/tests/supply_chain/test_openai_agent.py
git commit -m "feat(graph): generate graph with structured agent"
```

## Task 8: Gate publication with evidence and localization invariants

**Files:**

- Create: `backend/app/supply_chain/validator.py`
- Create: `backend/tests/supply_chain/test_validator.py`

- [ ] **Step 1: Write failing validation tests**

Cover evidence fidelity, graph topology, node budget, verification decisions, and localization:

```python
def test_verified_edge_requires_exact_excerpt_in_immutable_source(sources):
    result = validate_for_publication(
        draft=graph_with_fabricated_excerpt(),
        verification=verification_accepting_all_edges(),
        sources=sources,
        min_nodes=25,
        max_nodes=40,
        evidence_threshold=0.75,
    )

    assert result.status == "insufficient_evidence"
    assert result.rejections[0].code == "EXCERPT_NOT_FOUND"


def test_potential_edges_stay_separate_from_verified_edges(valid_graph):
    result = validate_for_publication(**valid_graph)

    assert all(edge.status == "verified" for edge in result.public_edges)
    assert all(edge.status == "potential" for edge in result.potential_edges)
```

Also test: disconnected focus node, cycles, self-edges, duplicate semantic edges, a missing upstream/downstream layer, unknown source keys, rejected edges, confidence thresholds, orphan nodes after pruning, 40-node ranking, translation IDs changed by the model, and excerpts changed by translation.

- [ ] **Step 2: Run validator tests and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_validator.py -q
```

Expected: import failure for the validator.

- [ ] **Step 3: Implement deterministic publication gates**

Validate in this order:

1. schema and unique-key integrity;
2. source-key existence and exact normalized excerpt containment;
3. entity resolution confidence;
4. adversarial verification verdicts;
5. semantic edge deduplication;
6. focus connectivity and upstream/downstream reachability;
7. evidence coverage;
8. 40-node deterministic ranking;
9. bilingual invariant checks.

```python
def evidence_coverage(edges: Sequence[AcceptedEdge]) -> float:
    weighted_total = sum(max(edge.importance, 0.1) for edge in edges)
    weighted_supported = sum(
        max(edge.importance, 0.1)
        for edge in edges
        if edge.status == "verified" and edge.valid_citations
    )
    return weighted_supported / weighted_total if weighted_total else 0.0
```

Rank nodes by focus status, verified-edge degree, evidence quality, business importance, and stable node key. Preserve the focus node, at least one upstream path, and at least one downstream path. Keep accepted graph size between 25 and 40 when the evidence pool supports that range. Return `insufficient_evidence` with reason codes when the surviving graph falls below the minimum.

- [ ] **Step 4: Validate localization without translating evidence**

Implement a structural comparison between accepted English content and Chinese localization:

- identical node and edge key sets;
- identical endpoint keys, status, type, dates, confidence, source references, URLs, symbols, CIKs, and exact excerpts;
- translated thesis, labels, descriptions, and relationship explanations;
- localized text length bounds and valid UTF-8.

Discard invalid localization and retain the accepted English snapshot for a retryable localization stage. Keep publication blocked until both locales satisfy the approved product contract.

- [ ] **Step 5: Run validation tests and full schema regression**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_validator.py tests/supply_chain/test_schemas.py -q
uv run ruff check app/supply_chain/validator.py tests/supply_chain/test_validator.py
```

Expected: all selected tests pass and Ruff exits `0`.

- [ ] **Step 6: Commit evidence gates**

```bash
git add backend/app/supply_chain/validator.py backend/tests/supply_chain/test_validator.py
git commit -m "feat(graph): verify graph publication evidence"
```

## Task 9: Persist accepted graphs and serve stable cached snapshots

**Files:**

- Create: `backend/app/supply_chain/repository.py`
- Create: `backend/app/supply_chain/service.py`
- Create: `backend/tests/supply_chain/test_repository.py`
- Create: `backend/tests/supply_chain/test_service.py`

- [ ] **Step 1: Write failing repository transaction tests**

Use an isolated database and assert normalized rows, immutable snapshots, and rollback behavior:

```python
def test_publish_graph_writes_snapshot_and_children_in_one_transaction(
    session,
    repository,
    accepted_graph,
):
    snapshot = repository.publish(
        company_id=AAPL_COMPANY_ID,
        graph=accepted_graph,
        source_fingerprint="a" * 64,
        schema_version="supply-chain-graph.v1",
        prompt_version="supply-chain-graph.2026-07-14",
        model_id="gpt-5-mini",
        now=NOW,
    )

    assert snapshot.status == "completed"
    assert snapshot.node_count == len(accepted_graph.nodes)
    assert snapshot.edge_count == len(accepted_graph.public_edges)
    assert session.exec(select(GraphEdgeCitation)).all()


def test_failed_publication_leaves_previous_snapshot_readable(
    session,
    repository,
    previous_snapshot,
    invalid_graph,
):
    with pytest.raises(GraphPublicationError):
        repository.publish(company_id=AAPL_COMPANY_ID, graph=invalid_graph, **VERSIONS)

    assert repository.latest_public(AAPL_COMPANY_ID).id == previous_snapshot.id


def test_working_snapshot_persists_resumable_stage_payloads(repository, collected_sources):
    working = repository.create_working_snapshot(
        job_id=JOB_ID,
        company_id=AAPL_COMPANY_ID,
        sources=collected_sources,
        source_fingerprint="a" * 64,
        **VERSIONS,
    )
    repository.save_stage(working.id, stage="extracted", payload=AAPL_DRAFT)

    assert repository.load_stage(working.id, stage="extracted") == AAPL_DRAFT
    assert repository.latest_public(AAPL_COMPANY_ID).id == PREVIOUS_SNAPSHOT_ID
```

Also test unique version keys, citation/source deduplication, node foreign-key endpoint mapping, insufficient-evidence publication, and snapshot row immutability.

- [ ] **Step 2: Run repository tests and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_repository.py -q
```

Expected: import failure for the graph repository.

- [ ] **Step 3: Implement atomic publication**

Create `SqlSupplyChainGraphRepository` with methods:

```python
class SqlSupplyChainGraphRepository:
    def latest_public(self, company_id: int) -> SupplyChainGraphSnapshot | None: ...
    def find_by_version_key(self, key: GraphVersionKey) -> SupplyChainGraphSnapshot | None: ...
    def create_working_snapshot(self, command: CreateWorkingSnapshotCommand) -> SupplyChainGraphSnapshot: ...
    def save_stage(self, snapshot_id: UUID, *, stage: str, payload: BaseModel) -> None: ...
    def load_stage(self, snapshot_id: UUID, *, stage: str) -> dict[str, object]: ...
    def publish(self, command: PublishGraphCommand) -> SupplyChainGraphSnapshot: ...
    def load_public(self, snapshot_id: UUID) -> PersistedGraph: ...
```

At the end of collection, compute the source fingerprint and create one private `drafted` working snapshot with its `graph_official_source` rows. Store resumable `extracted`, `resolved`, `verified`, and `localized` stage envelopes in the snapshot audit JSON. Keep `latest_public()` restricted to `completed` and `insufficient_evidence`, so the previous terminal snapshot stays visible.

Within `publish()`:

1. lock the working snapshot;
2. flush nodes and build `node_key -> node_id`;
3. load saved official sources and build `source_key -> source_id`;
4. insert public verified and potential edges;
5. insert citations with exact excerpts;
6. replace stage envelopes with final bilingual audit content;
7. set counts, terminal status, and terminal timestamps;
8. commit once at the repository boundary;
9. rollback and raise `GraphPublicationError` on any write failure.

Keep rejected and internal edges in `content_en`/`content_zh` audit JSON. Store normalized edge rows only for verified and potential public candidates.

- [ ] **Step 4: Write service and serialization tests**

Cover locale, evidence filters, rank limits, active refresh metadata, and cached lookup:

```python
def test_public_graph_defaults_to_verified_edges(service, principal):
    graph = service.get_current(
        company=AAPL,
        principal=principal,
        locale="en",
        evidence={"verified"},
        limit=40,
    )

    assert graph.snapshot.symbol == "AAPL"
    assert all(edge.evidence_status == "verified" for edge in graph.edges)
    assert graph.refresh_job is None


def test_refresh_job_is_returned_with_previous_snapshot(service, active_graph_job):
    graph = service.get_current(company=AAPL, principal=GUEST, locale="zh")

    assert graph.snapshot.id == PREVIOUS_SNAPSHOT_ID
    assert graph.refresh_job.id == active_graph_job.id
```

Test the 10–40 limit clamp, unknown locale, `potential` toggle, source/citation filtering after edge pruning, bilingual fields, and `GRAPH_NOT_FOUND`.

- [ ] **Step 5: Implement cache reads and public serialization**

Create `SupplyChainGraphService` that:

- returns the newest `completed` or `insufficient_evidence` snapshot;
- returns the current graph refresh job alongside a previous public snapshot;
- selects one locale without mutating IDs or evidence;
- includes only nodes reachable from selected edges plus the focal node;
- applies the deterministic rank limit;
- returns cited source metadata and exact excerpts;
- includes current principal quota status;
- maps stored confidence/evidence labels to the public schema.

Use the completed job deduplication key to determine reusable snapshot freshness against the latest SEC accession, schema version, prompt version, and model ID.

- [ ] **Step 6: Run repository and service validation**

Run:

```bash
cd backend
uv run pytest tests/supply_chain/test_repository.py tests/supply_chain/test_service.py -q
uv run ruff check app/supply_chain/repository.py app/supply_chain/service.py tests/supply_chain
```

Expected: selected tests pass and Ruff exits `0`.

- [ ] **Step 7: Commit publication and cache reads**

```bash
git add backend/app/supply_chain/repository.py backend/app/supply_chain/service.py backend/tests/supply_chain/test_repository.py backend/tests/supply_chain/test_service.py
git commit -m "feat(graph): publish and cache graph snapshots"
```

## Task 10: Add idempotent quota reservation, consumption, and refund

**Files:**

- Modify: `backend/app/quota/repository.py`
- Modify: `backend/app/quota/service.py`
- Modify: `backend/tests/quota/test_service.py`
- Modify: `backend/tests/quota/test_sqlite_repository.py`
- Modify: `backend/tests/quota/test_postgres_repository.py`

- [ ] **Step 1: Write failing quota-ledger service tests**

Preserve all current quota tests and add graph lifecycle cases:

```python
def test_refund_is_idempotent(repository, guest_principal):
    lease = reserve_job_analysis(
        repository,
        principal=guest_principal,
        job_id=JOB_ID,
        usage_date=TODAY,
        guest_limit=2,
        ip_limit=10,
    )

    assert refund_job_analysis(repository, lease.job_id, now=NOW) is True
    assert refund_job_analysis(repository, lease.job_id, now=NOW) is False
    assert get_quota(repository, guest_principal, TODAY).used == 0


def test_insufficient_evidence_consumes_reservation(repository, guest_principal):
    lease = reserve_job_analysis(repository, guest_principal, JOB_ID, TODAY)

    assert consume_job_analysis(repository, lease.job_id, now=NOW) is True
    assert refund_job_analysis(repository, lease.job_id, now=NOW) is False
    assert get_quota(repository, guest_principal, TODAY).used == 1


def test_explicit_retry_reserves_a_refunded_job_again(repository, guest_principal):
    reserve_job_analysis(repository, guest_principal, JOB_ID, TODAY)
    refund_job_analysis(repository, JOB_ID, now=NOW)

    assert rereserve_job_analysis(repository, JOB_ID, now=LATER) is True
    assert get_quota(repository, guest_principal, TODAY).used == 1
```

Add user, guest-IP, already-consumed, unknown-job, cross-day, and dispatch-failure cases.

- [ ] **Step 2: Run quota tests and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/quota/test_service.py tests/quota/test_sqlite_repository.py -q
```

Expected: failures because the repository protocol lacks ledger transitions.

- [ ] **Step 3: Extend the repository protocol around job leases**

Add these operations while retaining `reserve_many()` for existing company-intelligence behavior during staged migration:

```python
class QuotaRepository(Protocol):
    def reserve_for_job(self, reservation: JobQuotaReservation) -> JobQuotaLease: ...
    def rereserve_for_job(
        self,
        job_id: UUID,
        *,
        usage_date: date,
        principal_limit: int,
        ip_limit: int,
        now: datetime,
    ) -> bool: ...
    def consume_for_job(self, job_id: UUID, *, now: datetime) -> bool: ...
    def refund_for_job(self, job_id: UUID, *, now: datetime) -> bool: ...
    def reserve_many(self, reservations: list[QuotaReservation]) -> dict[QuotaKey, int]: ...
    def get_count(self, principal_type: str, principal_hash: str, usage_date: date) -> int: ...
```

`JobQuotaReservation` includes the job ID, principal identity, optional guest IP hash, usage date, principal daily limit, and IP daily limit.

- [ ] **Step 4: Implement transactional SQLite and PostgreSQL transitions**

Reservation must insert `agent_quota_reservation` and increment principal/IP aggregates in the caller's transaction. Repository methods flush and raise domain errors; the synchronization service owns commit/rollback with job creation. Consumption updates `reserved -> consumed`. Refund acquires/locks the ledger row, updates `reserved -> refunded`, decrements the principal aggregate and optional IP aggregate with a floor of zero, and sets `refunded_at`. Explicit retry conditionally updates `refunded -> reserved`, enforces the current daily principal/IP limits, increments the aggregates once, clears `refunded_at`, and records a new reservation timestamp.

For PostgreSQL, use a conditional update or `SELECT ... FOR UPDATE` so exactly one caller observes a successful state transition. For SQLite, perform the conditional state update and aggregate decrement in one session transaction. For the in-memory repository, protect transitions with a lock to keep concurrency tests deterministic.

- [ ] **Step 5: Add service-level lifecycle functions**

```python
def reserve_job_analysis(
    repository: QuotaRepository,
    principal: RequestPrincipal,
    job_id: UUID,
    usage_date: date,
    *,
    guest_limit: int = GUEST_DAILY_LIMIT,
    user_limit: int = USER_DAILY_LIMIT,
    ip_limit: int = IP_DAILY_LIMIT,
) -> tuple[JobQuotaLease, QuotaStatus]: ...


def consume_job_analysis(repository: QuotaRepository, job_id: UUID, *, now: datetime) -> bool: ...


def refund_job_analysis(repository: QuotaRepository, job_id: UUID, *, now: datetime) -> bool: ...


def rereserve_job_analysis(
    repository: QuotaRepository,
    job_id: UUID,
    *,
    now: datetime,
    guest_limit: int = GUEST_DAILY_LIMIT,
    user_limit: int = USER_DAILY_LIMIT,
    ip_limit: int = IP_DAILY_LIMIT,
) -> bool: ...
```

Map principal and IP limits to the existing public error codes. Keep cached reads and active-job reuse on `get_quota()` only.

- [ ] **Step 6: Add PostgreSQL idempotency coverage**

Mark the real-database test with `@pytest.mark.postgres`. Start two sessions against the same reserved job and call refund concurrently. Assert one `True`, one `False`, one `refunded` ledger row, and one aggregate decrement.

- [ ] **Step 7: Run quota regression tests**

Run:

```bash
cd backend
uv run pytest tests/quota -q
uv run pytest -m postgres tests/quota/test_postgres_repository.py -q
```

Expected: the first command passes. The PostgreSQL command passes when `TEST_POSTGRES_URL` is configured; otherwise report it as skipped by the existing test fixture.

- [ ] **Step 8: Commit quota lifecycle**

```bash
git add backend/app/quota/repository.py backend/app/quota/service.py backend/tests/quota
git commit -m "feat(quota): add idempotent graph refunds"
```

## Task 11: Build graph synchronization and the Agent pipeline

**Files:**

- Create: `backend/app/supply_chain/pipeline.py`
- Create: `backend/tests/supply_chain/test_pipeline.py`
- Modify: `backend/app/jobs/schemas.py`
- Modify: `backend/app/jobs/state.py`
- Modify: `backend/app/jobs/service.py`
- Modify: `backend/tests/jobs/test_state.py`
- Modify: `backend/tests/jobs/test_service.py`

- [ ] **Step 1: Write failing per-job state-machine tests**

Add the graph sequence while preserving current company-intelligence transitions:

```python
def test_supply_chain_graph_state_order():
    assert states_for("supply_chain_graph") == (
        "queued",
        "collecting",
        "extracting",
        "resolving",
        "verifying",
        "localizing",
        "completed",
    )


def test_company_intelligence_state_order_is_unchanged():
    assert states_for("company_intelligence") == (
        "queued",
        "downloading",
        "parsing",
        "analyzing",
        "verifying",
        "localizing",
        "completed",
    )
```

Test allowed forward transitions, retry from the current graph step, failure from every active step, and rejection of cross-job-type transitions.

- [ ] **Step 2: Run state tests and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/jobs/test_state.py -q
```

Expected: failures because state order is global.

- [ ] **Step 3: Implement the per-job-type state machine**

Replace the global tuple with a mapping and helpers:

```python
JOB_STATES = {
    "company_intelligence": COMPANY_INTELLIGENCE_STATES,
    "supply_chain_graph": SUPPLY_CHAIN_GRAPH_STATES,
}


def states_for(job_type: str) -> tuple[str, ...]:
    try:
        return JOB_STATES[job_type]
    except KeyError as error:
        raise InvalidJobType(job_type) from error
```

Update transition helpers to accept `job.job_type` and keep stable failure semantics.

- [ ] **Step 4: Write failing graph synchronization tests**

Add graph sync cases to `backend/tests/jobs/test_service.py`:

```python
@pytest.mark.anyio
async def test_graph_sync_reuses_completed_job_snapshot_without_quota(
    session,
    completed_graph_job,
    services,
):
    response = await synchronize_supply_chain_graph(
        session,
        company=AAPL,
        principal=GUEST,
        latest_accession="0000320193-25-000079",
        force_refresh=False,
        services=services,
    )

    assert response.status == "reused_snapshot"
    assert response.graph_snapshot_id == completed_graph_job.graph_snapshot_id
    assert response.quota.used == 0
```

Add active job, force refresh, newer filing, duplicate request race, quota exceeded, queue dispatch failure, one ledger reservation per accepted job, and explicit retry re-reservation after a refunded system failure.

- [ ] **Step 5: Implement graph deduplication and synchronization**

Add `GraphSynchronizationServices` and `synchronize_supply_chain_graph()` in `backend/app/jobs/service.py`. Build a key from:

```python
def graph_deduplication_key(
    company_id: int,
    latest_accession: str,
    schema_version: str,
    prompt_version: str,
    model_id: str,
) -> str:
    raw = "|".join(
        ("supply_chain_graph", str(company_id), latest_accession, schema_version, prompt_version, model_id)
    )
    return f"supply-chain-graph:{hashlib.sha256(raw.encode()).hexdigest()}"
```

Decision order:

1. find an active graph job for the same company and return `active_job`;
2. for `force_refresh=False`, find a completed job/snapshot with the exact deduplication key and return `reused_snapshot`;
3. preassign a job UUID;
4. reserve quota for that job and add the job in one database transaction;
5. commit once;
6. enqueue through the selected backend;
7. on dispatch failure, mark the graph job failed, preserve retry eligibility/error code, and refund the reservation once.

Expose `result_kind` and `graph_snapshot_id` from `JobPublic` while retaining `snapshot_id` for existing clients.
Update `retry_job()` so a retryable graph job re-reserves its refunded ledger before it moves back to `queued`; a quota error leaves the failed job unchanged. Repeated retry requests observe the queued state and add zero extra reservations.

- [ ] **Step 6: Write failing pipeline tests**

Use protocol fakes to assert stage ordering, state persistence, publication, and quota outcomes:

```python
@pytest.mark.anyio
async def test_pipeline_runs_agent_stages_and_consumes_quota(services, job):
    result = await SupplyChainGraphPipeline(services).run(job.id)

    assert services.calls == [
        "prepare_catalog",
        "plan_sources",
        "selected_documents",
        "extract_graph",
        "resolve_draft",
        "verify_graph",
        "validate_for_publication",
        "localize_graph",
        "publish",
        "consume_quota",
    ]
    assert result.status == "completed"


@pytest.mark.anyio
async def test_retryable_failure_refunds_once_and_keeps_previous_snapshot(services, job):
    services.collector.error = SourceCollectionError("SEC_UNAVAILABLE", retryable=True)

    with pytest.raises(SourceCollectionError):
        await SupplyChainGraphPipeline(services).run(job.id)

    assert services.quota.refund_calls == [job.id]
    assert services.repository.latest_public(job.company_id).id == PREVIOUS_SNAPSHOT_ID
```

Add tests for insufficient evidence consumption, unchanged-source force refresh linking the existing version, localization retry, duplicate worker delivery, a completed job replay, and failed publication refund.

- [ ] **Step 7: Implement the orchestration pipeline**

Implement public `collect()`, `extract()`, `resolve()`, `verify()`, `localize()`, and `publish()` stage methods plus `run(job_id)`, which invokes them in order for RQ. Each stage loads its prerequisite payload from the working snapshot, persists its output, and returns immediately when its stored target state already exists. This gives Vercel Workflow durable handoff without transferring source bodies through workflow payloads.

`SupplyChainGraphPipeline.run(job_id)` must:

1. load and lock the job;
2. return the existing result when the job is terminal;
3. prepare the official catalog, let the Agent call its list/fetch tools and select source IDs, load the fetched documents, and compute the fingerprint;
4. when that exact version key already exists after a forced refresh, link the job to the existing snapshot, complete the accepted research job, and consume its reservation;
5. otherwise create the working snapshot and set `graph_snapshot_id`;
6. transition and persist each named stage;
7. call extraction, entity resolution, adversarial verification, deterministic validation, and localization;
8. publish the working snapshot in one transaction;
9. set the terminal job state; `JobPublic` derives `result_kind="supply_chain_graph"` from `job_type`;
10. consume quota for completed or insufficient-evidence results;
11. classify system failures as retryable, mark the working snapshot/job failed, and refund exactly once;
12. preserve a stable `error_code` and current step for explicit retries.

Generate the source fingerprint from the sorted unique official source hashes. Keep model inputs bounded and pass only stored source IDs, metadata, and relevant text sections.

- [ ] **Step 8: Run job and pipeline validation**

Run:

```bash
cd backend
uv run pytest tests/jobs/test_state.py tests/jobs/test_service.py tests/supply_chain/test_pipeline.py -q
uv run ruff check app/jobs app/supply_chain/pipeline.py tests/jobs tests/supply_chain/test_pipeline.py
```

Expected: selected tests pass and Ruff exits `0`.

- [ ] **Step 9: Commit synchronization and pipeline**

```bash
git add backend/app/jobs backend/app/supply_chain/pipeline.py backend/tests/jobs/test_state.py backend/tests/jobs/test_service.py backend/tests/supply_chain/test_pipeline.py
git commit -m "feat(graph): orchestrate graph agent jobs"
```

## Task 12: Support RQ and Vercel Workflow execution

**Files:**

- Modify: `backend/app/jobs/tasks.py`
- Modify: `backend/app/jobs/rq_backend.py`
- Modify: `backend/app/jobs/vercel_backend.py`
- Modify: `backend/app/api/routes/internal_jobs.py`
- Modify: `backend/tests/jobs/backend_contract.py`
- Modify: `backend/tests/jobs/test_tasks.py`
- Modify: `backend/tests/jobs/test_rq_backend.py`
- Modify: `backend/tests/jobs/test_vercel_backend.py`
- Modify: `backend/tests/api/test_internal_jobs.py`
- Create: `frontend/src/app/api/internal/workflows/supply-chain-graph/route.ts`
- Create: `frontend/src/app/api/internal/workflows/supply-chain-graph/route.test.ts`
- Create: `frontend/src/workflows/supply-chain-graph.ts`
- Create: `frontend/src/workflows/supply-chain-graph.test.ts`

- [ ] **Step 1: Extend the shared backend contract test**

Parametrize both job types across both backends:

```python
@pytest.mark.parametrize(
    ("job_type", "expected_target"),
    [
        ("company_intelligence", "app.jobs.tasks.run_company_intelligence"),
        ("supply_chain_graph", "app.jobs.tasks.run_supply_chain_graph"),
    ],
)
@pytest.mark.anyio
async def test_backend_routes_supported_job_type(backend, job_type, expected_target):
    submission = await backend.enqueue(job_type=job_type, payload={"job_id": str(JOB_ID)})

    assert backend.recorded_target == expected_target
    assert submission.job_id
```

Add rejection tests for unsupported job types and malformed payloads.

- [ ] **Step 2: Run backend contract tests and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/jobs/test_rq_backend.py tests/jobs/test_vercel_backend.py tests/jobs/test_tasks.py -q
```

Expected: graph job routing failures.

- [ ] **Step 3: Route RQ tasks by job type**

Add `run_supply_chain_graph(job_id: str)` next to the existing task. Each task creates its sync database/session dependencies, invokes the async pipeline through the current worker bridge, and closes resources in `finally`.

Use an explicit mapping in `RQJobBackend`:

```python
RQ_TASKS = {
    "company_intelligence": "app.jobs.tasks.run_company_intelligence",
    "supply_chain_graph": "app.jobs.tasks.run_supply_chain_graph",
}
```

Use the graph job ID as the RQ job ID/deduplication identity and retain existing retry configuration.

- [ ] **Step 4: Route Vercel Workflow triggers by job type**

Map graph jobs to the configured `SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL` and company-intelligence jobs to the existing `WORKFLOW_TRIGGER_URL`. Include only `job_id` plus the current bearer and idempotency headers expected by the trigger route. Keep provider run IDs in the public job record.

- [ ] **Step 5: Add an internal graph-step API**

Extend `backend/app/api/routes/internal_jobs.py` with a signed, idempotent endpoint used by Vercel Workflow:

```http
POST /api/v1/internal/jobs/{job_id}/supply-chain-graph/{step}
```

Supported `step` values are `collect`, `extract`, `resolve`, `verify`, `localize`, and `publish`. Each call validates the existing internal secret/signature, confirms the job type, runs exactly one resumable stage, and returns the stored step result/status. Replayed completed steps return the stored result.

- [ ] **Step 6: Implement the Vercel Workflow route**

Create a workflow route mirroring the existing company-intelligence route. Add `frontend/src/workflows/supply-chain-graph.ts` with durable steps in order:

```typescript
const STEPS = ["collect", "extract", "resolve", "verify", "localize", "publish"] as const;

export async function supplyChainGraphWorkflow(jobId: string) {
  "use workflow";

  for (const step of STEPS) {
    await runSupplyChainGraphStep(jobId, step);
  }
}

export async function runSupplyChainGraphStep(
  jobId: string,
  step: (typeof STEPS)[number],
) {
  "use step";

  const backendUrl = requiredEnv("BACKEND_URL").replace(/\/$/, "");
  const response = await fetch(
    `${backendUrl}/api/v1/internal/jobs/${encodeURIComponent(jobId)}/supply-chain-graph/${step}`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${requiredEnv("INTERNAL_JOB_SECRET")}`,
        "x-idempotency-key": `${jobId}:supply-chain-graph:${step}:v1`,
      },
    },
  );
  if (!response.ok) {
    throw new Error(`Backend graph step ${step} failed: ${response.status}`);
  }
}
```

Use the project's existing workflow package and signature helpers. Keep stage response bodies bounded and store large artifacts through the backend stores.

- [ ] **Step 7: Test step replay and backend parity**

Add tests for:

- RQ execution of the complete pipeline;
- Workflow stage order;
- a replayed completed stage;
- an invalid signature;
- an unsupported step;
- a retryable internal failure;
- job type mismatch;
- identical terminal graph snapshot semantics for RQ and Workflow fixtures.

- [ ] **Step 8: Run backend and frontend workflow tests**

Run:

```bash
cd backend
uv run pytest tests/jobs/test_tasks.py tests/jobs/test_rq_backend.py tests/jobs/test_vercel_backend.py tests/api/test_internal_jobs.py -q
cd ../frontend
corepack pnpm test -- --run src/app/api/internal/workflows/supply-chain-graph/route.test.ts src/workflows/supply-chain-graph.test.ts
```

Expected: selected backend and frontend tests pass.

- [ ] **Step 9: Commit dual execution support**

```bash
git add backend/app/jobs backend/app/api/routes/internal_jobs.py backend/tests/jobs backend/tests/api/test_internal_jobs.py frontend/src/app/api/internal/workflows/supply-chain-graph frontend/src/workflows/supply-chain-graph.ts frontend/src/workflows/supply-chain-graph.test.ts
git commit -m "feat(graph): run graph jobs on rq and vercel"
```

## Task 13: Expose graph APIs and the secured Next.js BFF paths

**Files:**

- Modify: `backend/app/api/deps.py`
- Modify: `backend/app/api/routes/companies.py`
- Modify: `backend/app/api/routes/jobs.py`
- Modify: `backend/tests/api/conftest.py`
- Modify: `backend/tests/api/test_companies.py`
- Modify: `backend/tests/api/test_jobs.py`
- Modify: `frontend/src/app/api/research/[...path]/route.ts`
- Modify: `frontend/src/app/api/research/[...path]/route.test.ts`

- [ ] **Step 1: Write failing public API tests**

Add endpoint tests using dependency fakes and the existing signed guest/authenticated request helpers:

```python
def test_get_supply_chain_graph_defaults_to_verified_english(client, graph_snapshot):
    response = client.get("/api/v1/companies/AAPL/supply-chain-graph")

    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["symbol"] == "AAPL"
    assert {edge["evidence_status"] for edge in body["edges"]} == {"verified"}
    assert body["quota"]["limit"] == 2


def test_graph_sync_accepts_force_refresh_and_returns_graph_job(client):
    response = client.post(
        "/api/v1/companies/AAPL/supply-chain-graph/sync",
        json={"force_refresh": True},
        headers=GUEST_MUTATION_HEADERS,
    )

    assert response.status_code == 202
    assert response.json()["job"]["result_kind"] == "supply_chain_graph"
```

Cover `locale=zh`, `evidence=verified,potential`, `limit=10/40/99`, missing graph 404, unknown company, invalid filters, current refresh job, same-principal and cross-principal active reuse, cached reuse, quota errors, and authenticated user ownership.

- [ ] **Step 2: Run API tests and confirm the red state**

Run:

```bash
cd backend
uv run pytest tests/api/test_companies.py tests/api/test_jobs.py -q
```

Expected: graph routes return 404 and job payload assertions fail.

- [ ] **Step 3: Add typed graph dependencies**

Expose `SupplyChainGraphServiceDep`, `SupplyChainGraphPipelineDep`, and `GraphSynchronizationServicesDep` in `backend/app/api/deps.py`. Reuse the request principal, database session, SEC provider, job backend, quota repository, and versioned settings.

- [ ] **Step 4: Implement the public FastAPI routes**

Add to `companies.py`:

```python
@router.get("/{symbol}/supply-chain-graph", response_model=PublicSupplyChainGraph)
async def get_supply_chain_graph(
    symbol: str,
    session: SessionDep,
    principal: RequestPrincipalDep,
    service: SupplyChainGraphServiceDep,
    locale: Literal["en", "zh"] = "en",
    evidence: Annotated[str, Query(pattern="^(verified|verified,potential)$")] = "verified",
    limit: Annotated[int, Query(ge=10, le=40)] = 40,
) -> PublicSupplyChainGraph: ...


@router.post(
    "/{symbol}/supply-chain-graph/sync",
    response_model=GraphRefreshResponse,
    status_code=202,
)
async def sync_supply_chain_graph(
    symbol: str,
    command: GraphRefreshRequest,
    session: SessionDep,
    principal: RequestPrincipalDep,
    services: GraphSynchronizationServicesDep,
) -> GraphRefreshResponse: ...
```

Resolve the company and latest SEC accession through existing services. Preserve 202 for `accepted` and `active_job`; return 200 for `reused_snapshot` through an explicit `Response` status override. Keep domain error bodies in the current `{code, request_id}` contract.
Parse the comma-separated evidence string into a closed set before calling the service.

- [ ] **Step 5: Extend public job payloads**

Return:

```json
{
  "result_kind": "supply_chain_graph",
  "snapshot_id": null,
  "graph_snapshot_id": "uuid"
}
```

For company-intelligence jobs, return `result_kind="company_intelligence"`, the current `snapshot_id`, and `graph_snapshot_id=null`. Keep retry authorization and ownership unchanged.

- [ ] **Step 6: Write failing BFF allowlist tests**

Add exact path tests:

```typescript
expect(
  isAllowedResearchRequest("GET", "companies/AAPL/supply-chain-graph"),
).toBe(true);
expect(
  isAllowedResearchRequest("POST", "companies/AAPL/supply-chain-graph/sync"),
).toBe(true);
expect(
  isAllowedResearchRequest("DELETE", "companies/AAPL/supply-chain-graph"),
).toBe(false);
```

Also assert encoded slash, traversal, oversized body, cross-origin POST, and arbitrary suffix rejection.

- [ ] **Step 7: Extend the strict BFF allowlist**

Add only these patterns:

```typescript
["GET", new RegExp(`^companies/${SYMBOL}/supply-chain-graph$`)],
["POST", new RegExp(`^companies/${SYMBOL}/supply-chain-graph/sync$`)],
```

Query strings continue through `request.nextUrl.search`. Retain same-origin mutation enforcement, bounded request bodies, signed guest assertions, token rotation, and approved response headers.

- [ ] **Step 8: Run API and BFF validation**

Run:

```bash
cd backend
uv run pytest tests/api/test_companies.py tests/api/test_jobs.py -q
cd ../frontend
corepack pnpm test -- --run 'src/app/api/research/[...path]/route.test.ts'
```

Expected: selected backend and frontend tests pass.

- [ ] **Step 9: Commit public contracts**

```bash
git add backend/app/api backend/tests/api frontend/src/app/api/research
git commit -m "feat(graph): expose graph research api"
```

## Task 14: Define frontend graph types and deterministic layout

**Files:**

- Modify: `frontend/src/lib/research/types.ts`
- Create: `frontend/src/features/company/supply-chain-layout.ts`
- Create: `frontend/src/features/company/supply-chain-layout.test.ts`
- Modify: `frontend/src/features/company/test-fixtures.ts`

- [ ] **Step 1: Write failing response-parser tests**

Extend the existing research type tests or company fixture tests:

```typescript
it("parses the supply chain graph contract", () => {
  const graph = parseResearchResponse("supplyChainGraph", supplyChainGraphFixture);

  expect(graph.snapshot.symbol).toBe("AAPL");
  expect(graph.nodes).toHaveLength(25);
  expect(graph.edges[0].citations[0].excerpt).toContain("fixture evidence");
});

it("rejects a graph without nodes", () => {
  expect(() =>
    parseResearchResponse("supplyChainGraph", {
      ...supplyChainGraphFixture,
      nodes: undefined,
    }),
  ).toThrow("missing nodes");
});
```

- [ ] **Step 2: Add frontend graph types**

Extend `JobStatus` with `collecting`, `extracting`, and `resolving`. Extend `IngestionJob` with `result_kind` and `graph_snapshot_id`. Add:

```typescript
export type SupplyChainNodeKind = "company" | "business" | "product" | "category";
export type SupplyChainLayer = "upstream" | "core" | "downstream";
export type SupplyChainEvidenceStatus = "verified" | "potential";

export interface SupplyChainGraphNode {
  id: string;
  node_key: string;
  kind: SupplyChainNodeKind;
  layer: SupplyChainLayer;
  label: string;
  description: string;
  symbol: string | null;
  cik: string | null;
  importance: number;
  confidence: Confidence;
  rank: number;
}

export interface SupplyChainGraphEdge {
  id: string;
  edge_key: string;
  source: string;
  target: string;
  relationship_type: string;
  evidence_status: SupplyChainEvidenceStatus;
  confidence: Confidence;
  explanation: string;
  citations: SupplyChainCitation[];
}

export interface SupplyChainGraphResponse {
  snapshot: SupplyChainSnapshotSummary;
  nodes: SupplyChainGraphNode[];
  edges: SupplyChainGraphEdge[];
  sources: SupplyChainSource[];
  refresh_job: IngestionJob | null;
  quota: QuotaStatus;
}
```

Add `supplyChainGraph` and `graphSync` parser kinds with required top-level fields. Keep runtime checks lightweight and trust the authenticated FastAPI schema for nested validation.

- [ ] **Step 3: Write failing deterministic-layout tests**

```typescript
it("places graph layers in stable left-to-right columns", () => {
  const first = layoutSupplyChainGraph(nodes, edges);
  const second = layoutSupplyChainGraph([...nodes].reverse(), [...edges].reverse());

  expect(first).toEqual(second);
  expect(xOf(first, "upstream")).toBeLessThan(xOf(first, "core"));
  expect(xOf(first, "core")).toBeLessThan(xOf(first, "downstream"));
});

it("keeps every node within a 40-node canvas budget", () => {
  const result = layoutSupplyChainGraph(fortyNodeFixture.nodes, fortyNodeFixture.edges);

  expect(new Set(result.nodes.map((node) => `${node.position.x}:${node.position.y}`)).size)
    .toBe(result.nodes.length);
});
```

Add stable ordering, focus centering, same-rank tie break, empty graph, one layer, filtered potential edges, and handle-direction tests.

- [ ] **Step 4: Implement the layered layout**

Keep canvas coordinates out of the API:

```typescript
const COLUMN_X: Record<SupplyChainLayer, number> = {
  upstream: 0,
  core: 440,
  downstream: 880,
};
const ROW_GAP = 132;

export function layoutSupplyChainGraph(
  inputNodes: SupplyChainGraphNode[],
  inputEdges: SupplyChainGraphEdge[],
): SupplyChainFlowModel {
  const ordered = [...inputNodes].sort(
    (left, right) =>
      layerOrder(left.layer) - layerOrder(right.layer) ||
      left.rank - right.rank ||
      left.node_key.localeCompare(right.node_key),
  );
  return {
    nodes: ordered.map((node, index, all) => ({
      id: node.id,
      type: "supplyChain",
      position: positionNode(node, all, COLUMN_X, ROW_GAP),
      data: node,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    })),
    edges: [...inputEdges]
      .sort((a, b) => a.edge_key.localeCompare(b.edge_key))
      .map(toFlowEdge),
  };
}
```

Use smooth-step edges, stable edge IDs, solid verified strokes, dashed potential strokes, and markers pointing downstream. Let React Flow handle viewport fit/zoom while the layout module owns only model coordinates.

- [ ] **Step 5: Add a full bilingual graph fixture**

Extend `test-fixtures.ts` with 25 nodes, verified and potential edges, multiple citations, an active refresh variation, and an insufficient-evidence variation. Keep fixture labels concise enough to exercise node overflow behavior.

- [ ] **Step 6: Run types and layout tests**

Run:

```bash
cd frontend
corepack pnpm test -- --run src/features/company/supply-chain-layout.test.ts
corepack pnpm exec tsc --noEmit
```

Expected: selected tests and TypeScript pass.

- [ ] **Step 7: Commit frontend graph contracts**

```bash
git add frontend/src/lib/research/types.ts frontend/src/features/company/supply-chain-layout.ts frontend/src/features/company/supply-chain-layout.test.ts frontend/src/features/company/test-fixtures.ts
git commit -m "feat(graph): add graph types and layout"
```

## Task 15: Build the interactive React Flow graph and evidence inspector

**Files:**

- Create: `frontend/src/features/company/supply-chain-graph.tsx`
- Create: `frontend/src/features/company/supply-chain-graph.test.tsx`
- Create: `frontend/src/features/company/supply-chain-node.tsx`
- Create: `frontend/src/features/company/supply-chain-edge.tsx`
- Create: `frontend/src/features/company/supply-chain-inspector.tsx`
- Create: `frontend/src/features/company/supply-chain-legend.tsx`
- Modify: `frontend/src/features/company/company-page.tsx`
- Modify: `frontend/src/features/company/company-page.test.tsx`
- Modify: `frontend/src/features/company/copy.ts`
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Write failing graph interaction tests**

Mock the React Flow viewport shell while rendering real custom node/inspector behavior:

```typescript
it("opens evidence when a relationship is selected", async () => {
  const user = userEvent.setup();
  render(<SupplyChainGraph graph={supplyChainGraphFixture} {...props} />);

  await user.click(screen.getByRole("button", { name: /TSMC supplies Apple/i }));

  expect(screen.getByRole("heading", { name: /Relationship evidence/i })).toBeVisible();
  expect(screen.getByText(/fixture evidence/i)).toBeVisible();
  expect(screen.getByRole("link", { name: /Open official source/i })).toHaveAttribute(
    "href",
    expect.stringContaining("sec.gov"),
  );
});

it("reveals potential edges only after the user enables them", async () => {
  const user = userEvent.setup();
  render(<SupplyChainGraph graph={supplyChainGraphFixture} {...props} />);

  expect(screen.queryByText("Potential relationship")).toBeNull();
  await user.click(screen.getByRole("switch", { name: /Potential relationships/i }));
  expect(screen.getByText("Potential relationship")).toBeVisible();
});
```

Add tests for node selection, selected styles, close inspector, fit view, locale labels, empty/insufficient state, stale snapshot during refresh, generation submit, polling completion, retryable error, quota exhaustion, and center-on-company.

- [ ] **Step 2: Run graph component tests and confirm the red state**

Run:

```bash
cd frontend
corepack pnpm test -- --run src/features/company/supply-chain-graph.test.tsx
```

Expected: component import failure.

- [ ] **Step 3: Implement custom nodes and edges**

`SupplyChainNode` must render:

- kind icon and layer accent;
- label plus ticker for resolved companies;
- business/product/category badge;
- confidence and verified-neighbor count;
- source/target handles;
- a visible selected/focus state;
- a semantic `<button>` surface with an accessible label.

`SupplyChainEdge` must render solid verified and dashed potential paths, an arrow marker, a selected halo, and an accessible interaction target exposed through the parallel relationship list for keyboard and screen-reader users.

- [ ] **Step 4: Implement the graph canvas**

Use `ReactFlowProvider`, custom `nodeTypes`, custom `edgeTypes`, `Background`, `Controls`, `MiniMap`, and `Panel`. Define type maps at module scope, add a `ResizeObserver` test shim, and keep viewport state inside the graph component. Use `fitView`, `minZoom`, `maxZoom`, attribution, and keyboard selection settings explicitly.

```tsx
<ReactFlow
  nodes={flow.nodes}
  edges={flow.edges}
  nodeTypes={nodeTypes}
  edgeTypes={edgeTypes}
  onNodeClick={(_, node) => setSelection({ type: "node", id: node.id })}
  onEdgeClick={(_, edge) => setSelection({ type: "edge", id: edge.id })}
  fitView
  minZoom={0.35}
  maxZoom={1.8}
  nodesDraggable={false}
  nodesConnectable={false}
  elementsSelectable
>
  <Background gap={24} size={1} />
  <MiniMap pannable zoomable />
  <Controls showInteractive={false} />
</ReactFlow>
```

Memoize layout by snapshot ID plus potential-edge toggle. Keep the focal company visually central and preserve selection when filters retain the selected item.

- [ ] **Step 5: Implement the 30% evidence inspector**

For a node, show kind, layer, description, confidence, ticker/CIK, direct verified relationships, and `Center on this company` for resolved neighboring companies.

For an edge, show relationship type, explanation, status, confidence, observed dates, all citations, exact excerpts, source title/publisher/date, and an external official-source link with `target="_blank" rel="noopener noreferrer"`.

Use a persistent desktop sidebar and a bottom sheet/dialog on narrow screens. Restore focus to the selected graph/list control when the mobile inspector closes.

- [ ] **Step 6: Add legend, filters, and an accessible list view**

The legend explains layer colors, node kinds, verified lines, and potential dashed lines. Add a switch for potential relationships and a view toggle between graph and relationship list. The list groups upstream/core/downstream relationships and exposes the same selection callbacks as the canvas.

- [ ] **Step 7: Integrate graph loading, generation, and polling**

In `company-page.tsx`, add graph loading to the current `Promise.allSettled` batch:

```typescript
loadResource<SupplyChainGraphResponse>(
  "supplyChainGraph",
  `/api/research/companies/${symbol}/supply-chain-graph?locale=${language}`,
  controller.signal,
)
```

Treat graph 404 as an empty Agent state, separate from secondary-resource failure. Render `SupplyChainGraphSection` after `BusinessSummary`, replacing the linear `EvidenceFlow` in the page composition. Preserve `EvidenceFlow` source/tests for rollback during staged delivery.

The graph section must:

1. render a cached snapshot immediately;
2. render an active refresh banner while keeping that snapshot visible;
3. POST `{"force_refresh": false}` for initial generation and `true` for refresh;
4. update the shared quota from the sync response;
5. poll the owned job endpoint with bounded backoff after `accepted`, and poll the graph read endpoint after global `active_job` reuse;
6. reload the graph when `graph_snapshot_id` becomes available;
7. show insufficient-evidence content as a terminal research result;
8. show retry only when the job says `retry_eligible`;
9. call graph sync for a selected neighboring company before routing to its company page.

- [ ] **Step 8: Add bilingual product copy**

Extend `companyPageCopy.en/zh` with:

- graph title and thesis labels;
- layer and kind labels;
- verified/potential legend text;
- evidence inspector labels;
- generate, refresh, retry, pending, stale, and insufficient states;
- quota remaining/reset labels;
- center-on-company action;
- graph/list view controls;
- all graph job stage labels.

Keep technical predicates user-readable, such as `manufactures_for -> Manufactures for / 为其制造`.

- [ ] **Step 9: Implement responsive production styling**

Add a scoped `.supply-chain-*` system in `globals.css`:

- import `@xyflow/react/dist/style.css` before project rules;
- desktop grid at 70% canvas / 30% inspector;
- 680–760px graph height on large screens;
- warm neutral canvas, restrained layer colors, high-contrast selected state;
- focus company as the strongest visual anchor;
- compact source cards and readable excerpts;
- visible focus rings and 44px interactive targets;
- mobile list default plus graph view option;
- bottom-sheet inspector under 760px;
- `prefers-reduced-motion` rules for transitions;
- print rules that prefer the relationship list and source references.

- [ ] **Step 10: Run component, page, accessibility, and type validation**

Run:

```bash
cd frontend
corepack pnpm test -- --run src/features/company/supply-chain-graph.test.tsx src/features/company/company-page.test.tsx src/features/company/supply-chain-layout.test.ts
corepack pnpm exec tsc --noEmit
corepack pnpm lint
```

Expected: selected tests, TypeScript, and ESLint pass.

- [ ] **Step 11: Commit the frontend graph experience**

```bash
git add frontend/src/features/company frontend/src/app/globals.css frontend/src/lib/research/types.ts
git commit -m "feat(graph): add interactive supply chain graph"
```

## Task 16: Complete integration, deployment documentation, and release gates

**Files:**

- Modify: `backend/tests/e2e_app.py`
- Modify: `frontend/e2e/company-intelligence.spec.ts`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `docs/deployment.md`
- Modify: `docs/product-status.md`
- Modify: `backend/tests/test_docker_profile.py`
- Modify: `backend/tests/test_vercel_config.py`
- Modify: `backend/tests/test_readme.py`

- [ ] **Step 1: Write the deterministic end-to-end graph backend**

Extend `backend/tests/e2e_app.py` with deterministic graph Agent, collector, resolver, artifact store, repository, and pipeline overrides. Route `supply_chain_graph` jobs to the graph pipeline and retain the existing company-intelligence path.

Use the approved 25-node fixture, fixed timestamps, official example URLs, and bounded delays so Playwright observes at least queued and collecting states before completion. Reset graph tables, artifacts, job counters, and quota ledgers in `/__e2e__/reset`.

- [ ] **Step 2: Add end-to-end user journeys**

Extend `frontend/e2e/company-intelligence.spec.ts` with:

```typescript
test("guest generates and explores an evidence-backed supply chain graph", async ({ page }) => {
  await page.goto("/en/companies/AAPL");
  await page.getByRole("button", { name: "Generate supply chain graph" }).click();
  await expect(page.getByText("Collecting official sources")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Supply chain graph" })).toBeVisible();

  await page.getByRole("button", { name: /TSMC supplies Apple/i }).click();
  await expect(page.getByRole("heading", { name: "Relationship evidence" })).toBeVisible();
  await expect(page.getByText(/fixture evidence/i)).toBeVisible();
});
```

Add journeys for:

- cached reload with unchanged quota;
- a second accepted graph consuming the second guest unit;
- a third new company generation returning the daily limit state;
- potential-edge toggle;
- Chinese locale labels and invariant ticker/source text;
- refresh failure keeping the previous graph visible;
- center-on-neighbor behavior;
- mobile list view and evidence bottom sheet.

- [ ] **Step 3: Run end-to-end tests and fix integration seams**

Run from a clean port state:

```bash
cd frontend
corepack pnpm exec playwright test e2e/company-intelligence.spec.ts
```

Expected: all company research and supply-chain graph journeys pass in Chromium.

- [ ] **Step 4: Make Docker object storage self-initializing**

Add a `minio-init` one-shot service using the official MinIO client image. It waits for MinIO, creates the configured bucket, and applies private access. Make `api` and `worker` depend on successful initialization. Extend `backend/tests/test_docker_profile.py` to assert:

- the init service exists;
- the configured bucket is created;
- API and worker use the S3 provider;
- Redis and database dependencies remain healthy;
- graph settings pass through the env file.

- [ ] **Step 5: Document Vercel and Docker graph configuration**

Update `docs/deployment.md` and README environment tables with:

- `SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE`;
- `SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL` pointing to `/api/internal/workflows/supply-chain-graph`;
- current company-intelligence `WORKFLOW_TRIGGER_URL`;
- `BLOB_READ_WRITE_TOKEN` and private Vercel Blob store setup;
- S3/MinIO bucket and endpoint setup;
- graph schema/prompt versioning;
- RQ worker command and Vercel Workflow route;
- SEC user-agent requirements;
- source size/rate limits;
- quota consume/refund behavior;
- local backend/frontend startup and deterministic test commands.

Update `docs/product-status.md` to mark the graph slice complete only after the full gates below pass. Keep the README architecture diagram and feature matrix concise.

- [ ] **Step 6: Add deployment contract tests**

Extend the existing tests to assert that:

- Vercel excludes tests and local ingestion assets while including graph runtime modules;
- both workflow trigger variables are documented;
- Vercel Blob remains private;
- Docker worker includes boto3 and the graph pipeline;
- README links to the approved design and implementation plan;
- guest graph generation documents two accepted analyses per UTC day.

- [ ] **Step 7: Run the complete backend release gate**

Run:

```bash
cd backend
uv sync --frozen
uv run ruff check .
uv run pytest -q
uv run pytest tests/test_supply_chain_migration.py tests/test_docker_profile.py tests/test_vercel_config.py tests/test_readme.py -q
```

Expected: all commands exit `0`; the full pytest count includes all new graph tests.

- [ ] **Step 8: Run the complete frontend release gate**

Run:

```bash
cd frontend
CI=1 corepack pnpm install --frozen-lockfile
corepack pnpm test -- --run
corepack pnpm exec tsc --noEmit
corepack pnpm lint
corepack pnpm build
corepack pnpm exec playwright test e2e/company-intelligence.spec.ts
```

Expected: unit tests, type checking, ESLint, production build, and Playwright pass.

- [ ] **Step 9: Validate deployment descriptors**

Run:

```bash
docker compose config --quiet
docker compose build api worker web
```

Expected: Compose validation and all three builds exit `0`. This validates packaging without starting the full Docker stack.

- [ ] **Step 10: Perform a local deterministic smoke test**

Start the deterministic backend and frontend in separate terminals:

```bash
cd backend
uv run uvicorn tests.e2e_app:app --host 127.0.0.1 --port 8001
```

```bash
cd frontend
BACKEND_URL=http://127.0.0.1:8001 FRONTEND_URL=http://127.0.0.1:3000 NEXT_PUBLIC_GOOGLE_CLIENT_ID=e2e-client COOKIE_SECURE=false GUEST_SIGNING_SECRET=gggggggggggggggggggggggggggggggg INTERNAL_JOB_SECRET=iiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii corepack pnpm dev --hostname 127.0.0.1 --port 3000
```

Verify `/en/companies/AAPL` and `/zh-CN/companies/AAPL` in a browser. Generate the graph, inspect one verified edge, enable potential edges, open one official source, and confirm that refresh keeps the cached snapshot visible.

- [ ] **Step 11: Review the implementation against all acceptance criteria**

Check each item explicitly:

1. 25–40 mixed company/business/product/category nodes;
2. focal company plus upstream and downstream paths;
3. verified edges by default and potential toggle;
4. exact official-source excerpts and links;
5. AI planning, extraction, entity interpretation, verification, and localization;
6. deterministic evidence/security/publication gates;
7. bilingual browser-locale behavior;
8. cached and active reuse at zero quota;
9. one quota unit per new accepted job;
10. idempotent system-failure refund;
11. insufficient-evidence consumption;
12. previous snapshot during refresh/failure;
13. RQ/Docker and Workflow/Vercel parity;
14. keyboard, mobile, reduced-motion, and list-view access.

Record any environment-bound skipped validation in the final delivery note with the exact reason.

- [ ] **Step 12: Commit release integration**

```bash
git add backend/tests/e2e_app.py frontend/e2e/company-intelligence.spec.ts docker-compose.yml README.md docs/deployment.md docs/product-status.md backend/tests/test_docker_profile.py backend/tests/test_vercel_config.py backend/tests/test_readme.py
git commit -m "docs(graph): complete graph deployment guide"
```

## Implementation references

- Approved design: `docs/superpowers/specs/2026-07-14-agentic-supply-chain-graph-design.md`
- Existing company-intelligence plan: `docs/superpowers/plans/2026-07-13-phase-2-company-intelligence.md`
- LangChain ChatOpenAI tool calling and structured output: <https://docs.langchain.com/oss/python/integrations/chat/openai>
- React Flow custom nodes: <https://reactflow.dev/learn/customization/custom-nodes>
- React Flow accessibility: <https://reactflow.dev/learn/advanced-use/accessibility>
- Vercel Blob Python SDK: <https://vercel.com/docs/vercel-blob/using-blob-sdk>
- Amazon S3 `put_object`: <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/put_object.html>
- Amazon S3 `get_object`: <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/get_object.html>
- SEC Webmaster FAQ: <https://www.sec.gov/about/webmaster-frequently-asked-questions>

## Final implementation handoff

After all tasks pass:

1. run `git status --short` and confirm only intentional files remain;
2. run `git log --oneline --decorate -15` and inspect the feature commit sequence;
3. inspect `git diff main...HEAD --stat` for the expected backend/frontend/docs surface;
4. keep the feature branch available for review;
5. merge into `main` only after the user requests integration.
