# EquityLens — US Equity Research Knowledge Base

EquityLens is a full-stack foundation for evidence-backed US equity research. It
combines a localized Next.js interface, FastAPI, PostgreSQL with pgvector, and
asynchronous filing-processing contracts in one repository.

The current milestone is the Phase 0 engineering baseline. It delivers the
runtimes, test frameworks, database migration authority, provider boundaries,
health contracts, and Docker/Vercel deployment profiles. The product roadmap in
[`docs/superpowers/specs`](docs/superpowers/specs) covers users, company data,
SEC retrieval, valuation, document upload, and cited RAG research.

## Applications

| Directory | Purpose | Runtime |
|---|---|---|
| `frontend/` | React, Next.js App Router, English and Chinese UI | Node.js 22 |
| `backend/` | FastAPI API, Alembic migrations, provider contracts | Python 3.12 |
| `deploy/` | Docker and Vercel operating guides | Platform-specific |
| `scripts/` | Shared deployment smoke checks | Bash and curl |

## Local development without Docker

Create the backend environment file and replace the placeholder credentials:

```bash
cp backend/.env.example backend/.env
```

Start the API:

```bash
cd backend
uv sync --frozen
uv run uvicorn app.app:app --reload
```

The health endpoints start with the configured provider addresses. Database,
queue, object-storage, authentication, and ingestion workflows use local
PostgreSQL/pgvector, Redis, and S3-compatible services from that environment.

Start the frontend in a second terminal:

```bash
cd frontend
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Open `http://localhost:3000`. Browser language detection selects `/en-US` or
`/zh-CN`, and the language selector persists the user's choice in a cookie.

## Database migrations

With PostgreSQL and pgvector available at `DATABASE_URL`:

```bash
cd backend
uv run alembic upgrade head
uv run alembic heads
```

The Phase 0 schema head is `20260713_0001`.

## Docker profile

```bash
cp .env.example .env
docker compose config
docker compose build
docker compose up --wait
./scripts/smoke.sh
```

The stack includes Next.js, FastAPI, an RQ worker, PostgreSQL/pgvector, Redis,
and MinIO. Host ports can be changed through `API_PORT` and `WEB_PORT`. Detailed
operations are in [`deploy/docker/README.md`](deploy/docker/README.md).

## Vercel profile

Vercel uses two Projects connected to this repository:

- `frontend/` with the Next.js framework preset
- `backend/` with the FastAPI framework preset

Project roots, environment variables, and Preview build commands are in
[`deploy/vercel/README.md`](deploy/vercel/README.md).

## Health and smoke checks

- Frontend: `GET /api/health`
- Backend liveness: `GET /api/v1/health/live`
- Backend readiness: `GET /api/v1/health/ready`

Run the same health contract against any deployment:

```bash
WEB_BASE_URL=https://web.example.com \
API_BASE_URL=https://api.example.com \
./scripts/smoke.sh
```

## Quality checks

```bash
cd backend
uv lock --check
uv run pytest --cov=app.core.config --cov=app.providers --cov=app.api.routes.health --cov=app.main --cov-report=term-missing
uv run ruff check app/app.py app/main.py app/core/config.py app/providers app/api/deps.py app/api/main.py app/api/routes/health.py app/migrations tests

cd ../frontend
corepack pnpm install --frozen-lockfile
corepack pnpm test
corepack pnpm lint
corepack pnpm build

cd ..
git diff --check
```

## Deployment references

- [Next.js internationalization](https://nextjs.org/docs/app/guides/internationalization)
- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [pnpm workspace settings](https://pnpm.io/settings)
