# Vercel deployment profile

Create two Vercel Projects from this Git repository:

| Project | Root directory | Framework |
|---|---|---|
| `equity-research-web` | `frontend` | Next.js |
| `equity-research-api` | `backend` | FastAPI |

Set the backend environment variables for the Vercel profile:

```dotenv
DEPLOYMENT_TARGET=vercel
OBJECT_STORAGE_PROVIDER=vercel_blob
JOB_BACKEND=vercel_workflow
DOCUMENT_PARSER=managed
```

Add these values through Vercel Environment Variables:

- `DATABASE_URL`
- `SECRET_KEY_ACCESS_API`
- `OPENAI_API_KEY` and `OPENAI_ORGANIZATION`
- `FIRST_SUPERUSER` and `FIRST_SUPERUSER_PASSWORD`
- `BLOB_READ_WRITE_TOKEN`
- `MANAGED_PARSER_API_KEY`
- `CORS_ORIGINS` with the deployed frontend origin

The frontend project needs `NEXT_PUBLIC_API_BASE_URL` set to the deployed API
origin.

Pull project settings and run local builds with Vercel CLI 48.1.8 or newer:

```bash
pnpm dlx vercel@latest pull --cwd frontend --yes --environment=preview
pnpm dlx vercel@latest build --cwd frontend
pnpm dlx vercel@latest pull --cwd backend --yes --environment=preview
pnpm dlx vercel@latest build --cwd backend
```

Vercel currently recognizes `app/app.py` as a FastAPI entrypoint and supports
Python 3.12 from the project runtime files. See the official
[FastAPI guide](https://vercel.com/docs/frameworks/backend/fastapi) and
[Python runtime guide](https://vercel.com/docs/functions/runtimes/python).
