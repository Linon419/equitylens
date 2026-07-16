# Vercel web deployment

EquityLens deploys only the Next.js frontend to Vercel. FastAPI, the RQ worker,
Redis, and Caddy run on the Sydney VPS profile documented in
[`deploy/vps/README.md`](../vps/README.md).

## Architecture

```text
Browser
  -> Vercel Next.js + same-origin BFF
  -> https://api.example.com
  -> Caddy -> FastAPI -> Redis/RQ
  -> Neon PostgreSQL + Vercel Blob
```

The root [`vercel.json`](../../vercel.json) builds `frontend/` as the `web`
Service. Browser requests remain same-origin. The server-side BFF calls the VPS
through `BACKEND_URL` and forwards authentication cookies, signed guest
assertions, response status, and streaming bodies.

## 1. Deploy the VPS first

Follow [`deploy/vps/README.md`](../vps/README.md). Confirm that these endpoints
are reachable over HTTPS:

```bash
curl https://api.example.com/api/v1/health/live
curl https://api.example.com/api/v1/health/ready
```

## 2. Configure Vercel

Import the repository with the repository root as the Vercel Project Root.
Set these values for Production and Preview:

```dotenv
BACKEND_URL=https://api.example.com
NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id
GUEST_SIGNING_SECRET=replace-with-the-same-vps-secret
INTERNAL_JOB_SECRET=replace-with-the-same-vps-secret
COOKIE_SECURE=true
```

`BACKEND_URL` is server-only and must use HTTPS. `GUEST_SIGNING_SECRET` must
match the VPS because the BFF signs anonymous research assertions that FastAPI
verifies. `NEXT_PUBLIC_GOOGLE_CLIENT_ID` must match the VPS
`GOOGLE_CLIENT_ID`.

Database, LLM, SEC, private Vercel Blob, quota, and superuser secrets belong on
the VPS. `BLOB_READ_WRITE_TOKEN` stays out of the Vercel web project.

## 3. Configure Google OAuth

Add the Vercel Production origin to Authorized JavaScript origins:

```text
https://equitylens-nu.vercel.app
```

Add selected Preview origins when Google sign-in needs Preview testing.

## 4. Deploy and verify

Push `main` or redeploy the Vercel project, then run:

```bash
curl https://equitylens-nu.vercel.app/api/health
curl https://equitylens-nu.vercel.app/api/research/companies/SNDK
```

Open the dashboard and company page. Verify market data, financials, graph
refresh, chat streaming, and Google sign-in. The VPS `api` and `worker`
containers should remain warm between visits.

## Local build

```bash
cd frontend
corepack pnpm install --frozen-lockfile
BACKEND_URL=http://localhost:8000 corepack pnpm build
```
