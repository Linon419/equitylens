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
company-intelligence pipeline and the six-step supply-chain graph pipeline used
by Vercel Workflow.

The current compact filing path stores compressed 10-K source bytes in
PostgreSQL. Supply-chain research stores compressed official-source artifacts
in the private MinIO bucket configured by `S3_BUCKET`. The one-shot
`minio-init` service creates the bucket, removes anonymous access, creates a
bucket-scoped application user, and attaches its least-privilege policy before
the API and worker start. MinIO stays on the private Compose network;
administration runs through `docker compose exec` from the host.

Graph profile values:

```dotenv
OBJECT_STORAGE_PROVIDER=s3
S3_ENDPOINT_URL=http://minio:9000
S3_BUCKET=filings
S3_ACCESS_KEY_ID=replace-with-minio-app-user
S3_SECRET_ACCESS_KEY=replace-with-minio-app-password
MINIO_ROOT_USER=replace-with-minio-root-user
MINIO_ROOT_PASSWORD=replace-with-minio-root-password
SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE=
```

The shared guest pool permits two accepted graph jobs per UTC day when devoted
to graph research; company intelligence uses the same pool. Active-job and
cached-result reuse costs zero additional units, and retryable system failures
refund the reservation idempotently.

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
