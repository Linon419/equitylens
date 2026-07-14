# Agentic Supply-Chain Graph Design

**Status:** Approved design
**Date:** 2026-07-14
**Product:** EquityLens
**Audience:** Retail investors researching US-listed companies

## 1. Purpose

EquityLens will replace the current three-lane value-chain presentation with an
interactive, evidence-first supply-chain graph. The graph helps a retail
investor answer four questions quickly:

1. Where does this company sit in its industry value chain?
2. Which companies, products, and categories feed its core businesses?
3. Which customer groups, channels, and ecosystems depend on its output?
4. What official evidence supports each relationship?

The research Agent participates throughout the graph-generation workflow. It
plans source collection, discovers candidate entities and relationships,
resolves company identities, challenges every relationship, and produces
bilingual explanations. Deterministic services enforce evidence, security,
quota, identity, and persistence rules.

## 2. Approved Product Decisions

| Decision | Approved choice |
| --- | --- |
| Layout | Focus graph with a 70/30 evidence inspector |
| Node interaction | Open evidence details and offer “Center on this company” |
| Evidence sources | SEC filings, issuer investor-relations sites, and official press releases |
| Node taxonomy | Named companies plus product, category, and business nodes |
| Evidence visibility | Verified relationships by default; potential relationships behind a toggle |
| Refresh policy | Generate on first request, a newer SEC filing, or manual refresh; reuse snapshots otherwise |
| Default density | 25–40 nodes, capped at 40 |
| Quota policy | Charge only for a newly accepted graph-generation job |
| Rendering | React Flow with custom nodes and deterministic layered positions |
| Languages | English and Simplified Chinese |

Cached graph reads, viewport interactions, filters, citation viewing, and
opening an existing centered-company snapshot consume zero Agent quota.

## 3. Product Experience

### 3.1 Placement

The company research page retains the market, valuation, financial, and core
business sections. The current `EvidenceFlow` section becomes the
`SupplyChainGraphSection` and appears directly after the key-business section.

The graph occupies a large desktop canvas with an adjacent evidence inspector:

- upstream nodes occupy the left zone;
- the focal company and its business engines occupy the center zone;
- downstream nodes occupy the right zone;
- upstream company nodes use the warm red family;
- downstream company nodes use the teal family;
- business nodes use the ochre family;
- the focal company uses the existing dark ink color;
- product and category nodes use outlined rounded rectangles;
- solid edges represent verified relationships;
- dashed edges represent potential relationships.

The section header shows node count, relationship count, verified count,
potential count, generation time, model identifier, and source coverage.

### 3.2 Graph controls

The graph includes these controls:

- zoom in, zoom out, and fit view;
- verified-only and potential-relationship visibility;
- upstream, core, and downstream filters;
- company, product, category, and business filters;
- a structured-list view;
- a manual Agent refresh action;
- graph generation or polling status.

Drag operations affect only the current browser session. Stable deterministic
positions return on reload and remain suitable for screenshots and tests.

### 3.3 Selection and evidence inspector

Selecting a node highlights its direct relationships and dims unrelated graph
content. Selecting an edge opens the evidence inspector with:

- source node and target node;
- normalized relationship type;
- bilingual explanation;
- evidence status and confidence;
- observation date;
- primary and corroborating official sources;
- exact excerpts and source anchors;
- links to the saved official source URL.

A company node with a resolved `company_id` or US ticker exposes a
“Center on this company” action. The action calls the graph sync endpoint with
`force_refresh=false`. A cached snapshot opens immediately. A missing snapshot
creates a quota-charged Agent job, then the UI navigates to and polls the new
focal company.

Product, category, and business nodes explain the industry layer and omit the
re-centering action.

### 3.4 Responsive and accessible behavior

Desktop screens use the 70/30 canvas and inspector. Narrow screens place the
graph above a dismissible evidence panel. Touch targets have a minimum size of
44 CSS pixels.

React Flow nodes and edges remain keyboard focusable. `Enter` or `Space`
selects the focused item, `Escape` clears the selection, and localized ARIA
labels describe node kind, layer, and confidence. A structured relationship
list provides the same content in document order for screen readers and users
who prefer a table-like view.

React Flow provides the viewport, custom-node wrapper, controls, keyboard
selection, and focus management. EquityLens provides the visual system,
localized accessibility messages, graph semantics, and inspector.

References:

- [React Flow custom nodes](https://reactflow.dev/learn/customization/custom-nodes)
- [React Flow built-in components](https://reactflow.dev/learn/concepts/built-in-components)
- [React Flow accessibility](https://reactflow.dev/learn/advanced-use/accessibility)

## 4. Architecture

The feature follows the existing provider, pipeline, snapshot, API, BFF, and
React-component boundaries.

```text
Company page
  -> Next.js research BFF
    -> FastAPI supply-chain graph API
      -> graph snapshot cache
      -> quota reservation ledger
      -> RQ or Vercel Workflow job backend
        -> official-source collection tools
        -> AI planning and relationship extraction
        -> company/entity resolver
        -> AI adversarial verification
        -> deterministic evidence policy gate
        -> AI bilingual localization
        -> graph snapshot publisher
```

### 4.1 New backend modules

```text
backend/app/supply_chain/
  schemas.py          # AI draft, verified graph, and public response schemas
  contracts.py        # collector, generator, and resolver protocols
  sources.py          # official-source collection and artifact persistence
  resolver.py         # company/ticker/category identity resolution
  prompts.py          # plan, extract, verify, and localize prompts
  openai_generator.py # structured OpenAI implementation
  validator.py        # deterministic graph and citation validation
  service.py          # cache reads, sync decisions, and public serialization
  pipeline.py         # graph-specific job orchestration
  layout.py           # stable layer/rank metadata for the client
```

The public routes live in
`backend/app/api/routes/supply_chain_graph.py`. Dependency construction remains
in `backend/app/api/deps.py` and uses provider protocols for deterministic
integration tests.

### 4.2 New frontend modules

```text
frontend/src/features/supply-chain/
  supply-chain-section.tsx
  supply-chain-graph.tsx
  graph-node.tsx
  graph-edge.tsx
  graph-controls.tsx
  evidence-inspector.tsx
  relationship-list.tsx
  graph-status.tsx
  layout.ts
  copy.ts
```

`SupplyChainGraphSection` owns data loading and Agent status. The graph owns
viewport and selection. The inspector receives a selected node or edge and
renders evidence. The layout module maps server-provided layer and rank values
to deterministic coordinates.

## 5. Agent Workflow

The graph job type is `supply_chain_graph`. Its ordered states are:

```text
queued
  -> collecting
  -> extracting
  -> resolving
  -> verifying
  -> localizing
  -> completed
```

Any active step can transition to `failed`. The job records its current step,
retry eligibility, stable error code, attempt count, provider run identifier,
and graph snapshot identifier.

### 5.1 Collection

The collector starts with the focal company’s SEC identity and latest 10-K or
10-Q. It discovers the issuer’s official web domain from saved official
materials, then crawls a bounded set of same-organization investor-relations,
annual-report, and press-release pages.

The Agent receives two constrained tools:

- `list_official_sources(company, query, source_types)` returns metadata for
  SEC and verified issuer-owned documents;
- `fetch_official_source(source_id)` returns bounded text sections from a saved
  artifact.

The Agent decides which tools and documents support the research plan. The
collector enforces allowed domains, HTTPS, redirects, content type, response
size, timeout, robots policy, and request-rate rules. Search results act as
discovery hints. Saved official documents act as evidence.

SEC requests continue to use the configured `SEC_USER_AGENT` and the project’s
existing SEC access controls. The implementation follows the
[SEC Webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions).

Each collected source stores publisher, source type, title, URL, publication
date, retrieval time, content hash, and artifact location. Repeated content
hashes collapse to one source record within a snapshot.

### 5.2 Extraction

The AI generator receives the evidence bundle and returns a structured
`SupplyChainGraphDraft` containing candidate nodes, edges, citations, and
source references.

The extraction prompt requires:

- normalized upstream-to-downstream direction;
- one relationship predicate per edge;
- concise bilingual-ready explanations;
- explicit company aliases and ticker candidates;
- category nodes where official material names a class of suppliers or
  customers;
- one to five citations per public candidate edge;
- empty output for unsupported areas.

### 5.3 Entity resolution

The resolver matches company candidates against the local company table, SEC
CIK/ticker directory, known aliases, and issuer names. Resolution produces:

- `resolved_company` with `company_id`, symbol, and CIK;
- `private_company` with a normalized legal name;
- `ambiguous_company`, retained only in internal audit data;
- `category`, `product`, or `business` nodes.

The Agent contributes alias interpretation and context. Deterministic registry
matches establish the public re-centering identity.

### 5.4 Verification

The verifier evaluates every candidate edge against its cited excerpts and
actively seeks corroborating official material from a distinct publisher.

Publication levels are:

- `verified`: at least two independent official sources, distinct publishers,
  AI support verdicts, and a passing deterministic evidence gate;
- `potential`: one official source with direct semantic support and a passing
  deterministic evidence gate;
- `internal`: ambiguous, indirect, conflicting, or weakly supported candidates
  retained for audit and future research.

The public API includes `verified` and optionally `potential` edges. Internal
edges stay in the persisted audit result and outside the public response.

The deterministic gate validates:

1. every citation source belongs to the snapshot;
2. every excerpt exists verbatim after whitespace normalization in the saved
   source artifact;
3. source URLs use an approved official domain and scheme;
4. node keys are unique;
5. every edge endpoint exists;
6. self-edges and duplicate normalized edges are rejected;
7. edge direction and predicate belong to the supported vocabulary;
8. `verified` and `potential` edges meet their source-count policy;
9. all public edges contain a bilingual explanation after localization;
10. localized data preserves IDs, symbols, dates, confidence, and citations.

### 5.5 Localization and publication

AI localization produces English and Simplified Chinese node labels,
descriptions, relationship explanations, and evidence summaries. Entity names,
symbols, IDs, excerpts, URLs, confidence, dates, and numeric content remain
invariant.

Publication occurs in one database transaction after all validation passes.
The previous completed snapshot remains readable until that transaction
commits.

## 6. Data Model

### 6.1 `supply_chain_graph_snapshot`

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID PK | Snapshot identity |
| `company_id` | FK company | Focal company |
| `status` | varchar(32) | drafted, verified, completed, insufficient_evidence, failed |
| `schema_version` | varchar(64) | Public contract version |
| `prompt_version` | varchar(64) | Agent prompt version |
| `model_id` | varchar(128) | Generation model |
| `source_fingerprint` | varchar(64) | Hash of ordered official source hashes |
| `content_en` | JSON | Full validated English audit result |
| `content_zh` | JSON | Full validated Chinese audit result |
| `evidence_coverage` | varchar(32) | complete, partial, or insufficient_evidence |
| `overall_confidence` | varchar(16) | High, Medium, Low, or null |
| `node_count` | integer | Published node count |
| `edge_count` | integer | Published edge count |
| `generated_at` | timestamptz | Generation time |
| `verified_at` | timestamptz nullable | Verification time |
| `completed_at` | timestamptz nullable | Publication time |

The unique version key is `(company_id, source_fingerprint, schema_version,
prompt_version, model_id)`.

### 6.2 `supply_chain_graph_node`

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID PK | Node identity |
| `snapshot_id` | FK snapshot | Owning snapshot |
| `node_key` | varchar(160) | Stable key within snapshot |
| `kind` | varchar(24) | company, product, category, business |
| `layer` | varchar(24) | upstream, core, downstream |
| `company_id` | FK company nullable | Resolved local company |
| `symbol` | varchar(16) nullable | Public ticker |
| `cik` | varchar(16) nullable | SEC identity |
| `label_en`, `label_zh` | varchar(255) | Localized label |
| `description_en`, `description_zh` | text | Localized explanation |
| `importance` | decimal | Stable ranking from 0 to 1 |
| `confidence` | varchar(16) | High, Medium, Low |
| `rank` | integer | Stable position within layer |

`(snapshot_id, node_key)` is unique. Snapshot count fields have nonnegative
database checks. Publication service validation enforces the configured public
node limit.

### 6.3 `supply_chain_graph_edge`

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID PK | Edge identity |
| `snapshot_id` | FK snapshot | Owning snapshot |
| `edge_key` | varchar(255) | Normalized source/predicate/target key |
| `source_node_id` | FK node | Upstream side |
| `target_node_id` | FK node | Downstream side |
| `relationship_type` | varchar(64) | Controlled predicate |
| `evidence_status` | varchar(16) | verified, potential, internal |
| `confidence` | varchar(16) | High, Medium, Low |
| `explanation_en`, `explanation_zh` | text | Localized explanation |
| `first_observed_at` | date nullable | Earliest supported observation |
| `last_observed_at` | date nullable | Latest supported observation |

`(snapshot_id, edge_key)` is unique. Initial predicates are `supplies`,
`manufactures_for`, `distributes_for`, `sells_to`, `licenses_to`,
`platform_for`, `component_of`, and `serves_market`.

### 6.4 `graph_official_source`

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID PK | Source identity |
| `snapshot_id` | FK snapshot | Owning snapshot |
| `source_type` | varchar(32) | sec_filing, annual_report, ir_page, official_press_release |
| `publisher` | varchar(255) | Issuer or SEC identity |
| `title` | varchar(500) | Document title |
| `url` | text | Canonical official URL |
| `published_at` | date nullable | Publication date |
| `fetched_at` | timestamptz | Retrieval time |
| `content_hash` | varchar(64) | SHA-256 source fingerprint |
| `artifact_key` | text | Object-storage location |

`(snapshot_id, content_hash)` is unique.

### 6.5 `graph_edge_citation`

| Field | Type | Purpose |
| --- | --- | --- |
| `id` | UUID PK | Citation identity |
| `edge_id` | FK edge | Supported relationship |
| `source_id` | FK official source | Saved official material |
| `excerpt` | varchar(1500) | Exact supporting excerpt |
| `source_anchor` | varchar(500) | Section or fragment identifier |
| `support_role` | varchar(24) | primary or corroborating |

`(edge_id, source_id, source_anchor)` is unique.

### 6.6 Job and quota extensions

`ingestion_job` gains a nullable `graph_snapshot_id` foreign key and retains its
existing `snapshot_id` for company-intelligence jobs. `JobPublic` gains
`result_kind` and `graph_snapshot_id`.

The current ordered job-state helper becomes a per-job-type state machine.
Existing `company_intelligence` transitions remain unchanged. The new graph
job uses the states in Section 5.

Quota refunds require an idempotent ledger. The migration adds
`agent_quota_reservation` with:

- job ID;
- principal type and hash;
- optional IP hash;
- usage date and daily limit;
- state: reserved, consumed, refunded;
- creation and refund timestamps.

Reservation writes the ledger and increments the aggregate daily-usage rows in
one transaction. A retryable system failure transitions the ledger to
`refunded` and decrements the matching aggregates once. A completed or
insufficient-evidence job transitions it to `consumed`.

## 7. API Contract

### 7.1 Read the current graph

```http
GET /api/v1/companies/{symbol}/supply-chain-graph
    ?locale=zh
    &evidence=verified,potential
    &limit=40
```

Rules:

- `locale` accepts `en` or `zh`;
- `evidence` accepts `verified` and `potential`;
- `limit` defaults to 40 and is clamped from 10 to 40;
- the newest completed or insufficient-evidence snapshot is returned;
- an active refresh appears as `refresh_job` while the previous snapshot
  remains in the response;
- a company without a snapshot receives `GRAPH_NOT_FOUND` with HTTP 404.

Response shape:

```json
{
  "snapshot": {
    "id": "uuid",
    "symbol": "AAPL",
    "status": "completed",
    "model_id": "gpt-5-mini",
    "generated_at": "2026-07-14T00:00:00Z",
    "overall_confidence": "High",
    "evidence_coverage": "complete"
  },
  "nodes": [],
  "edges": [],
  "sources": [],
  "refresh_job": null,
  "quota": {
    "limit": 2,
    "used": 1,
    "remaining": 1,
    "resets_at": "2026-07-15T00:00:00Z"
  }
}
```

### 7.2 Generate or refresh a graph

```http
POST /api/v1/companies/{symbol}/supply-chain-graph/sync
Content-Type: application/json

{"force_refresh": false}
```

Responses reuse the current sync vocabulary:

- `reused_snapshot`: a valid snapshot exists, with zero quota charge;
- `active_job`: a matching graph job is already active, with zero additional
  quota charge;
- `accepted`: a new graph job was reserved and enqueued, with one quota charge.

`force_refresh=true` creates a new job after quota and active-job checks. A
newer SEC filing naturally changes the deduplication key and permits a new job.

The existing `GET /api/v1/jobs/{job_id}` and retry route serve both job types.
The public job payload includes `result_kind`, `snapshot_id`, and
`graph_snapshot_id`.

### 7.3 Frontend BFF

The Next.js research BFF allowlist adds:

- `GET companies/{symbol}/supply-chain-graph`;
- `POST companies/{symbol}/supply-chain-graph/sync`.

The BFF continues to create signed guest assertions, rotate authenticated
tokens, enforce same-origin mutation headers, cap request bodies, and copy only
approved response headers.

## 8. Snapshot Freshness and Deduplication

A graph snapshot remains current until one of these events occurs:

- SEC reports a newer 10-K or 10-Q for the focal company;
- the user requests a manual refresh;
- the graph schema, prompt, or model version changes and a refresh is requested.

The deduplication key includes job type, company ID, latest SEC accession,
schema version, prompt version, and model ID. Active jobs with the same key
collapse into one job.

The completed snapshot stores a source fingerprint for audit and exact replay.
Manual refresh can produce a new source fingerprint when official IR material
has changed.

## 9. Quota and Failure Semantics

Graph generation shares the existing daily Agent limits:

- guest: two accepted analyses per UTC day;
- authenticated user: ten accepted analyses per UTC day;
- guest IP protection: ten accepted analyses per UTC day.

A new graph job reserves one unit for the principal and, for guests, one IP
unit. Cached reads, active-job reuse, graph interaction, and source opening are
free.

### 9.1 Retryable system failure

Network, official-source service, model, queue, workflow, object-storage, and
database publication failures produce a stable retryable error. The quota
ledger refunds the reservation exactly once. A previous snapshot stays public.

### 9.2 Insufficient official evidence

The Agent completes its research and publishes an `insufficient_evidence`
snapshot with the focal node, supported category context, source coverage, and
an explanatory notice. The reservation is consumed because the research run
completed. Weak candidate edges remain in internal audit content.

### 9.3 Conflicting evidence

Conflicting official sources reduce edge confidence. A relationship with an
unresolved material conflict receives `internal` status. The evidence inspector
can expose conflict notes for published neighboring facts without publishing
the disputed edge.

## 10. Security and Evidence Controls

Official web content is untrusted input. Source text remains separated from
system instructions and tool definitions. Prompts explicitly treat source
content as evidence.

The collector applies:

- verified-domain allowlists;
- HTTPS and redirect validation;
- private-network and loopback blocking;
- content-type checks;
- response and decompression size limits;
- request and total-job timeouts;
- per-domain rate limits;
- HTML sanitization and plain-text extraction;
- SHA-256 content hashes;
- object-storage encryption and existing credential controls.

Every public graph edge links to a saved source artifact and canonical official
URL. The model output alone never establishes public evidence status.

## 11. Performance and Cost Controls

The first release uses these bounded budgets:

- 40 public nodes per response;
- 80 public edges per response;
- 12 official sources per generation job;
- 20 fetched pages across issuer sites per job;
- 1,500 characters per citation excerpt;
- configurable total evidence-token budget;
- one active graph job per company/version key;
- snapshot reuse across all users.

The server ranks nodes by evidence status, direct distance from the focal
company, importance, and stable key. Verified direct relationships receive the
highest priority.

React Flow loads dynamically within the client graph section. Deterministic
layer/rank coordinates avoid a continuous physics simulation. The public API
target is a compressed payload below 250 KB at the 40-node cap.

## 12. Testing Strategy

### 12.1 Backend unit tests

- structured AI draft and public response schemas;
- source-domain validation and fetch budgets;
- entity alias and ticker resolution;
- node and edge deduplication;
- direction and predicate validation;
- verbatim citation validation;
- verified, potential, and internal publication policy;
- localization invariants;
- stable ranking and 40-node cap;
- idempotent quota reserve, consume, and refund.

### 12.2 Backend integration tests

- Alembic upgrade, downgrade, and re-upgrade;
- deterministic official-source fixtures;
- full graph pipeline through publication;
- existing snapshot reuse with zero quota charge;
- concurrent sync collapse;
- newer filing creates a new deduplication key;
- retryable failure refunds quota once;
- insufficient evidence consumes quota and publishes status;
- RQ and Vercel Workflow backend contract tests;
- public API and BFF-compatible error responses.

### 12.3 Frontend tests

- response parsing and graph view-model mapping;
- deterministic coordinates;
- layer and node-type filters;
- verified and potential edge visibility;
- node and edge keyboard selection;
- evidence inspector source rendering;
- re-centering cached and accepted-job flows;
- mobile evidence panel;
- English and Chinese copy;
- loading, partial, insufficient, failed-refresh, and stale-snapshot states.

### 12.4 End-to-end tests

The deterministic E2E application gains graph fixtures and a fake Agent graph
generator. Playwright proves:

1. a guest generates an AAPL graph and consumes one unit;
2. the graph displays verified relationships and opens citation evidence;
3. a cached reload consumes zero units;
4. the potential toggle reveals dashed relationships;
5. re-centering on a company with a cached snapshot is free;
6. re-centering on a missing company accepts a new job and consumes one unit;
7. a retryable failure restores the unit;
8. Chinese and English graph content stays structurally identical.

### 12.5 Completion gates

- Ruff, backend tests, and backend coverage threshold pass;
- TypeScript, ESLint, frontend tests, and coverage thresholds pass;
- Next.js production build passes;
- Playwright graph journey passes;
- migration SQL and a live PostgreSQL cycle pass in an available environment;
- Docker smoke and Vercel build checks follow their documented environment
  prerequisites.

## 13. Observability

Structured logs include request ID, job ID, company symbol, source count,
candidate node and edge count, rejected edge count, published edge count,
model ID, prompt version, and duration by step. Excerpts, tokens, credentials,
and full model payloads stay outside logs.

Metrics include:

- graph cache-hit ratio;
- job completion, insufficient-evidence, and failure rates;
- source collection latency and source-type coverage;
- candidate-to-published edge ratio;
- verified-to-potential edge ratio;
- quota reservation and refund counts;
- model calls, latency, and token usage;
- public payload size and client render time.

## 14. Deployment

Docker uses the existing RQ worker and Redis queue with the new job type.
Vercel uses the existing Workflow adapter with graph-specific step dispatch.
Official source artifacts use the configured S3 or Vercel Blob object-storage
provider.

New configuration values have safe code defaults:

```text
GRAPH_MODEL=<defaults to RESEARCH_MODEL>
GRAPH_SCHEMA_VERSION=supply-chain-graph-v1
GRAPH_PROMPT_VERSION=supply-chain-graph-2026-07-14
GRAPH_MAX_PUBLIC_NODES=40
GRAPH_MAX_PUBLIC_EDGES=80
GRAPH_MAX_SOURCES=12
GRAPH_MAX_ISSUER_PAGES=20
```

The feature adds `@xyflow/react` to the frontend dependency set and updates the
lockfile. Docker and Vercel deployment guides document source-collection
network requirements and graph job configuration.

## 15. Rollout

The migration lands before application deployment. The backend graph API can
ship behind `SUPPLY_CHAIN_GRAPH_ENABLED`. The frontend reads the flag through
the graph API and retains the existing evidence flow during staged rollout.

Rollout stages:

1. deterministic fixtures and internal development;
2. production generation for a small issuer allowlist;
3. authenticated-user availability;
4. guest availability with the approved two-per-day quota;
5. default company-page graph after reliability and cost metrics meet targets.

Later milestones cover a 100-plus-node industry universe, collaborative
verification, manual relationship editing, graph time travel, and market-wide
scheduled refreshes.

## 16. Acceptance Criteria

The feature is accepted when all conditions below hold:

1. A company page can display a 25–40-node bilingual supply-chain graph.
2. Upstream, core, and downstream structure is visually clear at fit view.
3. Company, product, category, and business nodes have distinct semantics.
4. Verified and potential relationships use distinct edge styles and filters.
5. Selecting a relationship reveals confidence and exact official citations.
6. A resolved company node can become the focal company through the sync flow.
7. The Agent plans, collects, extracts, resolves, verifies, and localizes the
   graph through auditable job steps.
8. Every public edge passes deterministic evidence validation.
9. Cached graphs and active-job reuse consume zero quota.
10. A newly accepted graph job consumes one quota unit.
11. Retryable system failures refund that unit exactly once.
12. Existing snapshots remain visible during refresh and failure.
13. Keyboard, screen-reader, touch, desktop, and mobile paths expose equivalent
    research content.
14. Docker and Vercel execution paths share the same graph contract and tests.

## 17. Primary Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Sparse supplier/customer disclosure | Category nodes, potential status, and explicit source coverage |
| Hallucinated relationships | Verbatim citations, official domains, adversarial AI verification, deterministic evidence gate |
| Ambiguous company aliases | SEC registry resolution and internal status for ambiguous candidates |
| High model cost | Shared snapshots, bounded sources, 40-node cap, deduplicated active jobs |
| Long generation latency | Background jobs, granular progress, old-snapshot continuity |
| Source drift | Saved artifacts, content hashes, source fingerprints, versioned snapshots |
| Prompt injection in official pages | Untrusted-input isolation, constrained tools, deterministic output validation |
| Layout instability | Deterministic layer/rank coordinates and session-only dragging |

This design keeps the graph useful for retail investors while preserving the
project’s evidence-first standard: AI discovers and explains relationships,
and every public relationship remains traceable to saved official evidence.
