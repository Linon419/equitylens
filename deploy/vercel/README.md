# Vercel deployment

EquityLens deploys from one Git repository into two Vercel Projects.

| Deployment order | Project | Root directory | Framework |
|---|---|---|---|
| 1 | `equitylens-api` | `backend` | FastAPI |
| 2 | `equitylens-web` | `frontend` | Next.js |

Deploy the API Project first so its production URL can be supplied to the Web
Project.

## 1. Deploy the API

Use the API Deploy Button in the root [`README.md`](../../README.md), or import
the repository through the Vercel dashboard and choose `backend` as the Root
Directory.

Set the public deployment profile values:

```dotenv
DEPLOYMENT_TARGET=vercel
OBJECT_STORAGE_PROVIDER=vercel_blob
JOB_BACKEND=vercel_workflow
DOCUMENT_PARSER=managed
```

Provide the required secrets and service addresses through Vercel Environment
Variables:

- `DATABASE_URL`
- `SECRET_KEY_ACCESS_API`
- `OPENAI_API_KEY`
- `OPENAI_ORGANIZATION`
- `FIRST_SUPERUSER`
- `FIRST_SUPERUSER_PASSWORD`
- `GOOGLE_CLIENT_ID`
- `FRONTEND_URL`
- `BLOB_READ_WRITE_TOKEN`
- `MANAGED_PARSER_API_KEY`
- `GUEST_SIGNING_SECRET`
- `QUOTA_HASH_SECRET`
- `INTERNAL_JOB_SECRET`
- `WORKFLOW_TRIGGER_URL`
- `CORS_ORIGINS`
- `SEC_USER_AGENT`
- `MARKET_DATA_PROVIDER`
- `RESEARCH_MODEL`

Use a temporary trusted origin for `CORS_ORIGINS` during the first deployment.
The production Web origin is applied in step 3.

## 2. Deploy the Web app

Use the Web Deploy Button in the root [`README.md`](../../README.md), or import
the repository and choose `frontend` as the Root Directory.

Set the server-only API origin, public web origin, Google browser client ID,
and production cookie policy:

```dotenv
BACKEND_URL=https://equitylens-api.example.com
FRONTEND_URL=https://equitylens-web.example.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id
COOKIE_SECURE=true
GUEST_SIGNING_SECRET=replace-with-shared-32-character-secret
INTERNAL_JOB_SECRET=replace-with-shared-32-character-secret
```

Set the API Project's `WORKFLOW_TRIGGER_URL` to the Web Project trigger route:

```dotenv
WORKFLOW_TRIGGER_URL=https://equitylens-web.example.com/api/internal/workflows/company-intelligence
```

Use the same `GUEST_SIGNING_SECRET` and `INTERNAL_JOB_SECRET` values in both
Vercel Projects. The guest secret signs short-lived anonymous research
assertions. The internal secret starts a durable Workflow run and signs each
idempotent FastAPI step request using only the database job ID.

Use exact HTTPS origins and omit trailing slashes.

## 3. Data and artifact constraints

Set `SEC_USER_AGENT` to an application name and monitored contact email. SEC
traffic follows the published [automated-access guidance](https://www.sec.gov/about/webmaster-frequently-asked-questions).

The current Yahoo adapter supports research and evaluation. Complete a market
data licensing review before public or commercial distribution.

The compact 10-K pipeline persists compressed source bytes and integrity
metadata in PostgreSQL. Workflow steps depend exclusively on durable database
records. `BLOB_READ_WRITE_TOKEN`
reserves the configured object-storage boundary for the larger artifact adapter.

## 4. Connect both origins

Set the API Project's `CORS_ORIGINS` to the Web production origin, then redeploy
the API:

```dotenv
CORS_ORIGINS=https://equitylens-web.example.com
FRONTEND_URL=https://equitylens-web.example.com
```

Set the same `GOOGLE_CLIENT_ID` value in the Backend project and
`NEXT_PUBLIC_GOOGLE_CLIENT_ID` in the Frontend project.

| Project | Required authentication variables |
|---|---|
| Frontend | `BACKEND_URL`, `FRONTEND_URL`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, `COOKIE_SECURE=true`, shared guest/job secrets |
| Backend | `GOOGLE_CLIENT_ID`, `FRONTEND_URL`, `SECRET_KEY_ACCESS_API`, `DATABASE_URL`, shared guest/job secrets |

## 5. Verify production

```bash
WEB_BASE_URL=https://equitylens-web.example.com \
API_BASE_URL=https://equitylens-api.example.com \
./scripts/smoke.sh
```

The expected endpoints are:

- Web health: `GET /api/health`
- Public dashboard: `GET /en-US/dashboard`
- Research BFF: `GET /api/research/companies/search?q=AAPL`
- API smoke alias: `GET /api/v1/health`
- API liveness: `GET /api/v1/health/live`
- API readiness: `GET /api/v1/health/ready`

## Local Vercel builds

Use Vercel CLI 20.1.0 or newer:

```bash
pnpm dlx vercel@latest pull --cwd backend --yes --environment=preview
pnpm dlx vercel@latest build --cwd backend
pnpm dlx vercel@latest pull --cwd frontend --yes --environment=preview
pnpm dlx vercel@latest build --cwd frontend
```

Vercel recognizes `app/app.py` as the FastAPI entry point. Runtime configuration
is defined in [`backend/vercel.json`](../../backend/vercel.json) and
[`backend/runtime.txt`](../../backend/runtime.txt).

References:

- [FastAPI on Vercel](https://vercel.com/docs/frameworks/backend/fastapi)
- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [Vercel monorepos](https://vercel.com/docs/monorepos)
- [Deploy Button parameters](https://vercel.com/docs/deploy-button)
