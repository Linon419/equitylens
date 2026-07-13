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

The five durable pipeline steps are `download`, `parse`, `analyze`, `verify`,
and `localize`. Every step checks the database job state before writing, which
supports safe replay by Workflow and RQ.

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
```

### Vercel profile

```dotenv
DEPLOYMENT_TARGET=vercel
OBJECT_STORAGE_PROVIDER=vercel_blob
JOB_BACKEND=vercel_workflow
DOCUMENT_PARSER=managed
WORKFLOW_TRIGGER_URL=https://web.example.com/api/internal/workflows/company-intelligence
```

The API and web Projects use separate Vercel roots: `backend/` and `frontend/`.
Deploy the API first, place its URL in the web Project's `BACKEND_URL`, then set
the final web origin in API `CORS_ORIGINS` and `FRONTEND_URL`.

## Durable filing artifacts

The current 10-K HTML path compresses and stores the source bytes in PostgreSQL
`filing_artifact.compressed_body`, together with size and SHA-256 metadata.
Pipeline steps rely on database state and durable source bytes. Vercel function
temporary files carry no application state.

`OBJECT_STORAGE_PROVIDER`, Vercel Blob, and S3 profile credentials reserve the
adapter boundary for larger filing libraries. A production migration to object
storage requires a write-through adapter, integrity verification, and retention
policy before database blobs can be retired.

## Data-source operations

SEC EDGAR requests must carry `SEC_USER_AGENT` with an application name and
contact address. Keep request volume within the [SEC automated-access policy](https://www.sec.gov/about/webmaster-frequently-asked-questions).

The Yahoo adapter supplies compact research-use quote and company-profile data.
Commercial or public distribution requires a data-license review against the
[Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
and [Yahoo Developer Network Guidelines](https://legal.yahoo.com/us/en/yahoo/guidelines/ydn/index.html).

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
