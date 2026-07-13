# Docker deployment profile

Copy `.env.example` to `.env`, replace every secret, then run:

Authentication requires these profile values:

```dotenv
GOOGLE_CLIENT_ID=replace-with-google-client-id
NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id
FRONTEND_URL=https://equitylens.example.com
BACKEND_URL=http://api:8000
COOKIE_SECURE=true
GUEST_SIGNING_SECRET=replace-with-shared-32-character-secret
INTERNAL_JOB_SECRET=replace-with-shared-32-character-secret
QUOTA_HASH_SECRET=replace-with-backend-32-character-secret
SEC_USER_AGENT=EquityLens admin@example.com
```

Use `COOKIE_SECURE=false` only for native HTTP development on localhost.

```bash
docker compose config
docker compose build
docker compose up --wait
```

Health endpoints:

- Frontend: `http://localhost:3000/api/health`
- Public dashboard: `http://localhost:3000/en-US/dashboard`
- Backend: `http://localhost:8000/api/v1/health`

The API creates durable job records and Redis dispatches them to the
`company-intelligence` RQ queue. The worker runs the same idempotent five-step
pipeline used by Vercel Workflow.

The current compact filing path stores compressed 10-K source bytes in
PostgreSQL. MinIO and the S3 profile reserve the object-storage adapter boundary
for larger filing libraries.

Run the full smoke path after startup:

```bash
./scripts/smoke.sh
```

`API_PORT` and `WEB_PORT` can change the host ports when either default port is
already occupied.

Stop the containers started by this profile with:

```bash
docker compose down
```
