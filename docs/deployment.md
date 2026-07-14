# Deployment and operations

EquityLens supports Docker/RQ and Vercel Workflow with one FastAPI domain
pipeline. A deterministic SQLite harness provides the shortest local validation
path.

## Execution modes

| Mode | API and web | Job execution | Persistent state |
|---|---|---|---|
| Deterministic local validation | TestClient + Next.js dev server | In-process fixture runner | Temporary SQLite |
| Docker | FastAPI + Next.js containers | Redis queue and RQ worker | PostgreSQL |
| Vercel | Separate FastAPI and Next.js Projects | Vercel Workflow calling idempotent API steps | Managed PostgreSQL |

Company intelligence uses `download`, `parse`, `analyze`, `verify`, and
`localize`. Supply-chain research uses `collect`, `extract`, `resolve`,
`verify`, `localize`, and `publish`. Every step checks durable job and stage
state before writing, which supports safe replay by Workflow and RQ.

## Required environment

### Shared application values

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection used by API and workers |
| `SECRET_KEY_ACCESS_API` | Access-token signing secret |
| `GOOGLE_CLIENT_ID` | Google ID-token audience on FastAPI |
| `FRONTEND_URL` | Exact public web origin |
| `OPENAI_API_KEY` | Structured research generation and verification |
| `OPENAI_ORGANIZATION` | OpenAI organization scope |
| `SEC_USER_AGENT` | Application name plus monitored contact email |
| `GUEST_SIGNING_SECRET` | Shared BFF/backend guest assertion secret |
| `QUOTA_HASH_SECRET` | Backend principal hashing secret |
| `INTERNAL_JOB_SECRET` | Shared Workflow/API step secret |
| `RESEARCH_MODEL` | Structured intelligence model identifier |
| `SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE` | Optional graph-specific model identifier |
| `SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION` | Persisted graph contract version |
| `SUPPLY_CHAIN_GRAPH_PROMPT_VERSION` | Agent prompt/evaluation version |
| `SUPPLY_CHAIN_GRAPH_SOURCE_LIMIT` | Maximum official sources per graph run |
| `SUPPLY_CHAIN_GRAPH_SOURCE_BYTES` | Total compressed-source input ceiling |
| `SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET` | Agent evidence context ceiling |
| `GRAPH_ARTIFACT_PREFIX` | Private object-storage key namespace |

Use independent random values of at least 32 characters for every secret. The
frontend and backend receive the same `GUEST_SIGNING_SECRET` and
`INTERNAL_JOB_SECRET` values.

### Frontend values

| Variable | Purpose |
|---|---|
| `BACKEND_URL` | Server-side FastAPI origin |
| `FRONTEND_URL` | Same-origin mutation validation |
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
worker listens on the `company-intelligence` queue and routes both durable job
types:

```bash
uv run rq worker --url redis://redis:6379/0 company-intelligence
```

### Vercel profile

```dotenv
DEPLOYMENT_TARGET=vercel
OBJECT_STORAGE_PROVIDER=vercel_blob
JOB_BACKEND=vercel_workflow
DOCUMENT_PARSER=managed
WORKFLOW_TRIGGER_URL=https://web.example.com/api/internal/workflows/company-intelligence
SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL=https://web.example.com/api/internal/workflows/supply-chain-graph
BLOB_READ_WRITE_TOKEN=replace-with-private-store-token
```

The API and web Projects use separate Vercel roots: `backend/` and `frontend/`.
Deploy the API first, place its URL in the web Project's `BACKEND_URL`, then set
the final web origin in API `CORS_ORIGINS` and `FRONTEND_URL`.

Create the Vercel Blob store with private access and connect it to the API
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

## Data-source operations

SEC EDGAR requests must carry `SEC_USER_AGENT` with an application name and
contact address. Keep request volume within the [SEC automated-access policy](https://www.sec.gov/about/webmaster-frequently-asked-questions).

The Yahoo adapter supplies compact research-use quote and company-profile data.
Commercial or public distribution requires a data-license review against the
[Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
and [Yahoo Developer Network Guidelines](https://legal.yahoo.com/us/en/yahoo/guidelines/ydn/index.html).

The default graph collector accepts up to 24 official sources and 8 MB total.
It applies allowlists, DNS pinning, redirect checks, MIME validation,
decompression bounds, and host pacing. Evidence publication requires an exact
capped excerpt and the originating official URL.

The shared guest pool permits two accepted graph jobs per UTC day when devoted
to graph research; company intelligence uses the same pool. Authenticated users
receive ten total Agent jobs. A new accepted job reserves one unit. Active jobs
and cached snapshots use zero additional units. Retryable system or collection
failures refund the reservation idempotently. Published insufficient-evidence
results consume the accepted unit.

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
uv run rq worker --url redis://localhost:6379/0 company-intelligence
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

## Verification commands

```bash
cd backend
uv lock --check
uv run ruff check app tests
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
uv run alembic upgrade head
uv run alembic downgrade 20260713_0002
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
