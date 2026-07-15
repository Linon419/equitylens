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

OpenAI-compatible Chat Completions providers can power intelligence generation,
the supply-chain Agent, and query rewriting. This example uses DeepSeek while
OpenAI supplies research-chat Responses and embeddings:

```dotenv
OPENAI_API_KEY=replace-with-openai-key
OPENAI_ORGANIZATION=replace-with-openai-organization
OPENAI_BASE_URL=
LLM_API_KEY=replace-with-deepseek-key
LLM_BASE_URL=https://api.deepseek.com/beta
LLM_STRUCTURED_OUTPUT_METHOD=function_calling
RESEARCH_MODEL=deepseek-v4-pro
CHAT_MODEL_OVERRIDE=deepseek-v4-pro
SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE=deepseek-v4-pro
```

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
company-intelligence pipeline, six-step supply-chain graph pipeline, and 10-K
filing-index job used by Vercel Workflow.

Research chat streams through the existing web port (`3000`) and API port
(`8000`). Preserve Server-Sent Events when an HTTPS reverse proxy fronts the
Compose services. An Nginx location can use:

```nginx
location /api/research/ {
    proxy_pass http://web:3000;
    proxy_http_version 1.1;
    proxy_buffering off;
    proxy_cache off;
    add_header X-Accel-Buffering no;
}
```

The chat response uses `Content-Type: text/event-stream`,
`Cache-Control: no-cache, no-transform`, and `X-Accel-Buffering: no`. Carry
these headers through every proxy layer so answer events reach the browser as
they are emitted.

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

Chat has an independent message quota: guests receive two messages per UTC day
and authenticated users receive ten. Starting the latest 10-K filing-index job
uses zero Agent and chat quota units.

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
