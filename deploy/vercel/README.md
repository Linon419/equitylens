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
- `CORS_ORIGINS`

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
```

Use exact HTTPS origins and omit trailing slashes.

## 3. Connect both origins

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
| Frontend | `BACKEND_URL`, `FRONTEND_URL`, `NEXT_PUBLIC_GOOGLE_CLIENT_ID`, `COOKIE_SECURE=true` |
| Backend | `GOOGLE_CLIENT_ID`, `FRONTEND_URL`, `SECRET_KEY_ACCESS_API`, `DATABASE_URL` |

## 4. Verify production

```bash
WEB_BASE_URL=https://equitylens-web.example.com \
API_BASE_URL=https://equitylens-api.example.com \
./scripts/smoke.sh
```

The expected endpoints are:

- Web health: `GET /api/health`
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
