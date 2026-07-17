# Deployment and operations

EquityLens uses Docker/RQ for the FastAPI domain pipeline and Vercel for the
Next.js frontend. A deterministic SQLite harness provides the shortest local
validation path.

## Execution modes

| Mode | API and web | Job execution | Persistent state |
|---|---|---|---|
| Deterministic local validation | TestClient + Next.js dev server | In-process fixture runner | Temporary SQLite |
| Docker | FastAPI + Next.js containers | Redis queue and RQ worker | PostgreSQL |
| Vercel + VPS | Next.js on Vercel; FastAPI on a long-lived VPS | Redis and RQ worker on the VPS | Managed PostgreSQL |

Company intelligence uses `download`, `parse`, `analyze`, `verify`, and
`localize`. Supply-chain research uses `collect`, `extract`, `resolve`,
`verify`, `localize`, and `publish`. Every step checks durable job and stage
state before writing, which supports safe replay by Workflow and RQ.

Company research chat uses a durable filing-index job followed by synchronous
query rewriting, hybrid full-text/vector retrieval, structured context
resolution, bounded Agent-selected web evidence, answer validation, and an SSE
response. Conversation messages and citations are committed before the stream
reports completion.

## Required environment

### Shared application values

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection used by API and workers |
| `SECRET_KEY_ACCESS_API` | Access-token signing secret |
| `GOOGLE_CLIENT_ID` | Google ID-token audience on FastAPI |
| `FRONTEND_URL` | Exact public web origin |
| `OPENAI_API_KEY` | Filing embeddings and optional OpenAI Responses fallback |
| `OPENAI_ORGANIZATION` | OpenAI organization scope |
| `OPENAI_BASE_URL` | Optional base URL for OpenAI Responses and embedding clients |
| `LLM_API_KEY` | Optional Chat Completions provider key; defaults to `OPENAI_API_KEY` |
| `LLM_BASE_URL` | Optional Chat Completions provider URL; defaults to `OPENAI_BASE_URL` |
| `LLM_STRUCTURED_OUTPUT_METHOD` | `json_schema` for OpenAI, `json_mode` for DeepSeek thinking models, or `function_calling` for strict tool providers |
| `TAVILY_API_KEY` | Optional Tavily credential; blank enables free keyless search |
| `SEC_USER_AGENT` | Application name plus monitored contact email |
| `GUEST_SIGNING_SECRET` | Shared BFF/backend guest assertion secret |
| `QUOTA_HASH_SECRET` | Backend principal hashing secret |
| `INTERNAL_JOB_SECRET` | Shared Workflow/API step secret |
| `RESEARCH_MODEL` | Structured intelligence model identifier |
| `SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE` | Optional graph-specific model identifier |
| `SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION` | Persisted graph contract version |
| `SUPPLY_CHAIN_GRAPH_PROMPT_VERSION` | Agent prompt/evaluation version |
| `SUPPLY_CHAIN_GRAPH_SOURCE_LIMIT` | Maximum official sources per graph run |
| `SUPPLY_CHAIN_GRAPH_SOURCE_BYTES` | Total compressed-source input ceiling; default `64000000` |
| `SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET` | Agent evidence context ceiling |
| `SUPPLY_CHAIN_GRAPH_STAGE_TIMEOUT_SECONDS` | Per-stage model timeout in seconds; default `180` |
| `SUPPLY_CHAIN_GRAPH_MAX_OUTPUT_TOKENS` | Graph model output ceiling; default `16000` |
| `GRAPH_ARTIFACT_PREFIX` | Private object-storage key namespace |
| `CHAT_GUEST_DAILY_LIMIT` | Independent guest messages per UTC day; default `2` |
| `CHAT_USER_DAILY_LIMIT` | Independent authenticated messages per UTC day; default `10` |
| `CHAT_GUEST_RETENTION_DAYS` | Guest conversation lifecycle; default `7` |
| `CHAT_MAX_MESSAGE_CHARS` | Maximum user-message size |
| `CHAT_MAX_HISTORY_MESSAGES` | Conversation turns supplied to rewriting |
| `CHAT_CHUNK_TARGET_TOKENS` | Deterministic filing chunk target |
| `CHAT_CHUNK_OVERLAP_TOKENS` | Filing chunk overlap |
| `CHAT_CHUNK_MIN_FINAL_TOKENS` | Minimum final chunk before merging |
| `CHAT_RETRIEVAL_CANDIDATES` | Candidate count per FTS and vector channel |
| `CHAT_RETRIEVAL_MAX_CHUNKS` | Maximum chunks in answer context |
| `CHAT_RETRIEVAL_MAX_PER_SECTION` | Per-section diversity ceiling |
| `CHAT_RETRIEVAL_TOKEN_BUDGET` | Filing evidence context budget |
| `CHAT_RRF_K` | Reciprocal-rank-fusion constant |
| `CHAT_WEB_MAX_QUERIES` | Maximum Agent-selected search queries |
| `CHAT_WEB_MAX_PAGES` | Maximum fetched web evidence pages |
| `CHAT_WEB_SEARCH_PROVIDER` | `tavily` by default; `openai` keeps the Responses fallback |
| `CHAT_TAVILY_SEARCH_DEPTH` | Tavily relevance/cost mode; default `basic` uses one credit per query |
| `CHAT_TAVILY_MAX_RESULTS` | Tavily candidates returned per query; default `5` |
| `CHAT_EMBEDDING_MODEL` | Filing chunk embedding model |
| `CHAT_EMBEDDING_DIMENSIONS` | pgvector embedding dimensions |
| `CHAT_MODEL_OVERRIDE` | Optional chat-specific model |
| `CHAT_PROMPT_VERSION` | Persisted chat prompt identity |
| `CHAT_ANSWER_SCHEMA_VERSION` | Persisted answer contract identity |
| `CHAT_INDEX_SCHEMA_VERSION` | Filing-index contract identity |
| `CHAT_WEB_ARTIFACT_PREFIX` | Private web artifact namespace; default `chat-web` |

Use independent random values of at least 32 characters for every secret. The
frontend and backend receive the same `GUEST_SIGNING_SECRET` and
`INTERNAL_JOB_SECRET` values.

The intelligence generator, supply-chain graph Agent, query rewriter, web-search
router, and answer planner use the `LLM_*` endpoint. This supports
OpenAI-compatible Chat Completions providers such as DeepSeek. Tavily performs
web discovery, while the `OPENAI_*` endpoint supplies filing embeddings. Setting
`CHAT_WEB_SEARCH_PROVIDER=openai` restores the OpenAI Responses search path.

Example mixed-provider configuration:

```dotenv
OPENAI_API_KEY=replace-with-openai-key
OPENAI_ORGANIZATION=replace-with-openai-organization
OPENAI_BASE_URL=
LLM_API_KEY=replace-with-deepseek-key
LLM_BASE_URL=https://api.deepseek.com
LLM_STRUCTURED_OUTPUT_METHOD=json_mode
TAVILY_API_KEY=
CHAT_WEB_SEARCH_PROVIDER=tavily
CHAT_TAVILY_SEARCH_DEPTH=basic
CHAT_TAVILY_MAX_RESULTS=5
RESEARCH_MODEL=deepseek-v4-pro
CHAT_MODEL_OVERRIDE=deepseek-chat
SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE=deepseek-v4-pro
```

Keyless Tavily search is free and rate-limited. A free API key raises the
allowance to 1,000 credits per month; `basic` search consumes one credit per
query. Production deployments should set `TAVILY_API_KEY` for predictable rate
limits.

### Frontend values

| Variable | Purpose |
|---|---|
| `BACKEND_URL` | Server-side FastAPI origin |
| `FRONTEND_URL` | Optional explicit same-origin validation override |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google browser client ID |
| `COOKIE_SECURE` | `true` for HTTPS deployments |

### Docker profile

```dotenv
DEPLOYMENT_TARGET=docker
OBJECT_STORAGE_PROVIDER=s3
JOB_BACKEND=rq
DOCUMENT_PARSER=local
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET=filings
S3_ACCESS_KEY_ID=replace-with-minio-app-user
S3_SECRET_ACCESS_KEY=replace-with-minio-app-password
MINIO_ROOT_USER=replace-with-minio-root-user
MINIO_ROOT_PASSWORD=replace-with-minio-root-password
SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE=
```

Compose waits for MinIO readiness, creates `S3_BUCKET` through `minio-init`,
removes anonymous access, and provisions a bucket-scoped application identity
before API and worker startup. MinIO stays on the private Compose network. The
worker listens on the `company-intelligence` queue and routes company
intelligence, supply-chain graph, and `filing_index` jobs:

```bash
uv run rq worker --with-scheduler \
  --url redis://redis:6379/0 company-intelligence
```

### Vercel web + VPS API profile

Vercel builds only `frontend/`. Set `BACKEND_URL` to the public HTTPS origin of
the VPS API. The BFF preserves same-origin browser traffic, guest assertions,
authentication cookies, and SSE streaming while making server-to-server calls
to the VPS.

The VPS profile in `deploy/vps/` runs FastAPI, an RQ worker, Redis, and Caddy.
Neon supplies PostgreSQL and Vercel Blob stores private research artifacts.
This removes Python serverless dependency installation from page requests and
keeps Agent dependencies loaded in long-lived containers.

Set `REVERSE_PROXY_MODE=external` when the VPS already runs 1Panel/OpenResty or
another HTTPS proxy. FastAPI is then published only on
`127.0.0.1:${API_PORT:-18000}` for the host proxy. The `caddy` mode activates
the Compose Caddy profile when the project owns ports 80 and 443.

```dotenv
DEPLOYMENT_TARGET=vps
OBJECT_STORAGE_PROVIDER=vercel_blob
JOB_BACKEND=rq
REDIS_URL=redis://redis:6379/0
DOCUMENT_PARSER=managed
BLOB_READ_WRITE_TOKEN=replace-with-private-store-token
```

The root `vercel.json` defines only the `web` Service. Configure
`BACKEND_URL=https://api.example.com` in Vercel. Configure the VPS with the
matching `FRONTEND_URL`, `CORS_ORIGINS`, and `GUEST_SIGNING_SECRET` values.
Vercel Server Functions run in `syd1` so SSR and BFF traffic stay close to the
Sydney VPS.

Create the Vercel Blob store with private access and connect it to the Services
Project. `BLOB_READ_WRITE_TOKEN` stays server-side. The graph artifact adapter
uses private writes and reads for every official-source object.

## Durable research artifacts

The current 10-K HTML path compresses and stores the source bytes in PostgreSQL
`filing_artifact.compressed_body`, together with size and SHA-256 metadata.
Pipeline steps rely on database state and durable source bytes. Vercel function
temporary files carry no application state.

Supply-chain source bodies are compressed, content-addressed, and written to
the selected private object store. PostgreSQL keeps source metadata, integrity
digests, Agent stage artifacts, graph snapshots, nodes, edges, and evidence
references. Schema and prompt version changes create distinct cache identities.

Alembic revision `20260714_0005` creates the chat conversation, message,
citation, quota, filing-chunk, and web-source tables. PostgreSQL applies a GIN
full-text index and pgvector HNSW index to filing chunks. Re-indexing replaces a
filing's chunk set idempotently.

Agent-selected web evidence is compressed and content-addressed beneath the
private `chat-web/` object-storage prefix. Public citations expose the source
URL and a bounded supporting excerpt. Guest conversations, messages, and their
citations are deleted after seven days by the lifecycle cleanup path.

## Data-source operations

SEC EDGAR requests must carry `SEC_USER_AGENT` with an application name and
contact address. Keep request volume within the [SEC automated-access policy](https://www.sec.gov/about/webmaster-frequently-asked-questions).

The Yahoo adapter supplies compact research-use quote and company-profile data.
Commercial or public distribution requires a data-license review against the
[Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
and [Yahoo Developer Network Guidelines](https://legal.yahoo.com/us/en/yahoo/guidelines/ydn/index.html).

The default graph collector accepts up to 24 official sources and 64 MB total.
It applies allowlists, DNS pinning, redirect checks, MIME validation,
decompression bounds, and host pacing. Evidence publication requires an exact
capped excerpt and the originating official URL.

The shared guest pool permits two accepted graph jobs per UTC day when devoted
to graph research; company intelligence uses the same pool. Authenticated users
receive ten total Agent jobs. A new accepted job reserves one unit. Active jobs
and cached snapshots use zero additional units. Retryable system or collection
failures refund the reservation idempotently. Published insufficient-evidence
results consume the accepted unit.

Research chat maintains a separate quota ledger. Guests receive two chat
messages per UTC day and authenticated users receive ten chat messages per UTC
day. Filing-index preparation consumes zero chat and Agent units. Retryable
answer failures refund the reserved message idempotently, and replaying an
accepted client message ID returns its durable result.

## Streaming proxy contract

The Next.js research BFF forces dynamic execution, disables fetch caching, and
passes the FastAPI response body through as a stream. Preserve
`Content-Type: text/event-stream`, `Cache-Control: no-cache, no-transform`, and
`X-Accel-Buffering: no` across CDN and reverse-proxy layers. Nginx deployments
should include:

```nginx
location /api/research/ {
    proxy_pass http://web:3000;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    add_header X-Accel-Buffering no;
}
```

## Reproducible setup

```bash
cd backend
uv sync --frozen
uv run alembic upgrade head

cd ../frontend
corepack pnpm install --frozen-lockfile
```

Docker startup:

```bash
cp .env.example .env
docker compose config
docker compose up --build --wait
```

Native RQ worker:

```bash
cd backend
uv run rq worker --with-scheduler --worker-class rq.worker.SimpleWorker \
  --url redis://localhost:6379/0 company-intelligence
```

Native applications:

```bash
cd backend
uv run uvicorn app.app:app --reload

cd ../frontend
BACKEND_URL=http://127.0.0.1:8000 corepack pnpm dev
```

Deterministic graph journey:

```bash
cd frontend
corepack pnpm exec playwright test e2e/company-intelligence.spec.ts
```

Deterministic research-chat validation:

```bash
cd backend
uv run pytest tests/chat/test_rag_evaluation.py \
  tests/integration/test_company_chat_journey.py -q

cd ../frontend
corepack pnpm exec playwright test e2e/company-chat.spec.ts
```

## Verification commands

```bash
cd backend
uv lock --check
uv run ruff check app tests
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
uv run alembic upgrade head
uv run alembic downgrade 20260714_0004
uv run alembic upgrade head

cd ../frontend
corepack pnpm test
corepack pnpm exec tsc --noEmit
corepack pnpm lint
corepack pnpm build
corepack pnpm exec playwright test

cd ..
WEB_BASE_URL=https://web.example.com \
API_BASE_URL=https://api.example.com \
./scripts/smoke.sh
```

The smoke script verifies API health, web health, the English public dashboard,
and company search through the same-origin research BFF.
