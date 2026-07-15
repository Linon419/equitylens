<div align="center">

# EquityLens

**Evidence-backed US equity research for individual investors.**

Connect a company's business model, value-chain position, SEC filings,
financial performance, market price, and valuation in one research workspace.

![Project Status](https://img.shields.io/badge/status-Phase%202%20beta-2563EB)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![Languages](https://img.shields.io/badge/UI-English%20%7C%20简体中文-2563EB)

| Deploy the API | Deploy the Web app |
|---|---|
| [![Deploy API with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FLinon419%2Fequitylens&root-directory=backend&project-name=equitylens-api&env=DATABASE_URL%2CSECRET_KEY_ACCESS_API%2CGOOGLE_CLIENT_ID%2CFRONTEND_URL%2COPENAI_API_KEY%2COPENAI_ORGANIZATION%2COPENAI_BASE_URL%2CLLM_API_KEY%2CLLM_BASE_URL%2CLLM_STRUCTURED_OUTPUT_METHOD%2CTAVILY_API_KEY%2CCHAT_WEB_SEARCH_PROVIDER%2CCHAT_TAVILY_SEARCH_DEPTH%2CCHAT_TAVILY_MAX_RESULTS%2CFIRST_SUPERUSER%2CFIRST_SUPERUSER_PASSWORD%2CBLOB_READ_WRITE_TOKEN%2CMANAGED_PARSER_API_KEY%2CCORS_ORIGINS%2CDEPLOYMENT_TARGET%2COBJECT_STORAGE_PROVIDER%2CJOB_BACKEND%2CDOCUMENT_PARSER%2CSEC_USER_AGENT%2CGUEST_SIGNING_SECRET%2CQUOTA_HASH_SECRET%2CINTERNAL_JOB_SECRET%2CWORKFLOW_TRIGGER_URL%2CSUPPLY_CHAIN_WORKFLOW_TRIGGER_URL%2CCHAT_INDEX_WORKFLOW_TRIGGER_URL%2CMARKET_DATA_PROVIDER%2CRESEARCH_MODEL%2CSUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE&envDefaults=%7B%22DEPLOYMENT_TARGET%22%3A%22vercel%22%2C%22OBJECT_STORAGE_PROVIDER%22%3A%22vercel_blob%22%2C%22JOB_BACKEND%22%3A%22vercel_workflow%22%2C%22DOCUMENT_PARSER%22%3A%22managed%22%7D&envDescription=Configure+the+EquityLens+API+deployment+profile+and+required+credentials.&envLink=https%3A%2F%2Fgithub.com%2FLinon419%2Fequitylens%2Fblob%2Fmain%2Fdeploy%2Fvercel%2FREADME.md) | [![Deploy Web with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FLinon419%2Fequitylens&root-directory=frontend&project-name=equitylens-web&env=BACKEND_URL%2CFRONTEND_URL%2CNEXT_PUBLIC_GOOGLE_CLIENT_ID%2CCOOKIE_SECURE%2CGUEST_SIGNING_SECRET%2CINTERNAL_JOB_SECRET&envDescription=Configure+the+FastAPI+origin%2C+public+web+origin%2C+Google+client+ID%2C+shared+signing+secrets%2C+and+secure+cookies.&envLink=https%3A%2F%2Fgithub.com%2FLinon419%2Fequitylens%2Fblob%2Fmain%2Fdeploy%2Fvercel%2FREADME.md) |

[Quick start](#quick-start) · [Architecture](#architecture) · [Deployment](#deployment) · [Roadmap](#roadmap) · [Contributing](#contributing)

</div>

> [!IMPORTANT]
> **Phase 2 Beta.** Public company search, compact valuation context, four-year
> SEC financials, automated 10-K analysis, an AI-generated supply-chain graph,
> citation-backed research chat, guest quotas, Google authentication, and
> persistent watchlists are implemented.
> Market-data licensing review and production infrastructure remain launch gates.

## Why EquityLens

Retail investors often assemble company research across filings, quote pages,
spreadsheets, and disconnected notes. EquityLens is designed around one company
and six connected questions:

1. What does the company sell, and which businesses drive revenue?
2. Where does it sit in the industry value chain?
3. What do its 10-K and 10-Q filings actually say?
4. How are revenue, margins, cash flow, and balance-sheet quality changing?
5. How does the current price compare with earnings and peer valuations?
6. Which primary source supports each conclusion?

## Project status

| Capability | Status |
|---|---|
| Localized Next.js shell with browser language detection | Available |
| FastAPI application factory, provider contracts, and health endpoints | Available |
| PostgreSQL / pgvector schema managed by Alembic | Available |
| Reproducible Python and Node.js dependency locks | Available |
| Docker and Vercel deployment profiles | Available |
| Public bilingual dashboard and company search | Available |
| Current price, market cap, EPS, trailing P/E, and forward P/E | Available |
| Four fiscal years plus TTM from SEC Company Facts | Available |
| Automated 10-K retrieval and durable analysis jobs | Available |
| AI-generated supply-chain graph with verified and potential edges | Available |
| Relationship evidence drawers with official-source excerpts | Available |
| Guest two/day and authenticated ten/day Agent quotas | Available |
| Google sign-in, rotating sessions, and persistent watchlists | Available |
| Citation-backed company research chat with durable citations | Available |
| DeepSeek-directed conversation, clarification, and research routing | Available |
| DeepSeek-directed Tavily web discovery | Available |
| Manual filing upload, DCF, and peer valuation | Planned |

The detailed product design lives in
[`docs/superpowers/specs/2026-07-13-us-equity-research-platform-design.md`](docs/superpowers/specs/2026-07-13-us-equity-research-platform-design.md).
The shipped surface and launch gates are tracked in
[`docs/product-status.md`](docs/product-status.md).
The graph-specific decisions and implementation sequence live in the
[`agentic graph design`](docs/superpowers/specs/2026-07-14-agentic-supply-chain-graph-design.md)
and [`agentic graph plan`](docs/superpowers/plans/2026-07-14-agentic-supply-chain-graph.md).
The research-chat retrieval, citation, streaming, and lifecycle decisions live
in the [`company research chat design`](docs/superpowers/specs/2026-07-14-company-research-chat-design.md)
and [`company research chat plan`](docs/superpowers/plans/2026-07-14-company-research-chat.md).

## Architecture

```mermaid
flowchart LR
    investor["Investor browser"] --> web["Next.js web app"]
    web --> bff["Same-origin research BFF"]
    bff --> api["FastAPI API"]
    api --> db[("PostgreSQL + pgvector")]
    api --> storage["Document storage"]
    api --> jobs["Durable job record"]
    jobs --> graph["Supply-chain graph Agent"]
    api --> chat["Company research chat Agent"]
    jobs --> workflow["Vercel Workflow"]
    jobs --> worker["RQ worker"]
    workflow --> api
    api --> sec["SEC EDGAR"]
    api --> market["Yahoo adapter"]
    api --> search["Tavily Search"]
    api --> llm["Structured LLM generation"]
    worker --> sec
    worker --> llm
    worker --> db
    graph --> storage
    graph --> llm
    chat --> db
    chat --> storage
    chat --> llm
    chat --> search
    db --> api
```

The provider contracts keep deployment-specific infrastructure at the edges:

| Profile | Web / API | Storage | Jobs | Document parsing |
|---|---|---|---|---|
| Vercel | Two Vercel Projects | PostgreSQL + private Vercel Blob evidence | Vercel Workflow | Managed profile |
| Docker | Next.js + FastAPI containers | PostgreSQL + private MinIO evidence bucket | Redis + RQ | Local parser |

Graph generation uses AI for source planning, relationship extraction,
entity interpretation, claim verification, and Chinese localization.
Deterministic publication gates enforce source allowlists, evidence excerpts,
confidence thresholds, graph size, and schema invariants. The shared guest pool
permits two accepted graph jobs per UTC day when devoted to graph research;
company intelligence uses the same pool. Active jobs and cached snapshots reuse
the existing result at zero quota cost.

Citation-backed company research chat combines the latest indexed 10-K,
structured company context, and bounded Agent-selected web evidence. Hybrid
full-text and vector retrieval keeps filing citations grounded in exact
excerpts, and the answer streams through the same-origin BFF. Guests receive
two chat messages per UTC day. Authenticated users receive ten chat messages per UTC day,
and guest conversations are retained for seven days. This message
quota is independent from the Agent job quota; filing-index preparation costs
zero units.

DeepSeek first reads the current message, company context, and conversation
history. It can answer conversational messages directly, ask one focused
clarification question, or resolve a follow-up into a standalone research
question. Only the research route enters filing retrieval, Tavily discovery,
and strict citation validation. Deterministic controls remain responsible for
quota, source policy, timeouts, persistence, and replay.

With `CHAT_WEB_SEARCH_PROVIDER=tavily`, DeepSeek decides whether external
evidence is material and generates up to three focused queries. Tavily discovers
candidate sources; the API independently validates, fetches, archives, and cites
approved pages. The default `basic` search depth uses one Tavily credit per query.
With a blank `TAVILY_API_KEY`, Tavily's rate-limited keyless mode keeps local
search available without an additional paid account.

## Repository layout

```text
.
├── frontend/          # Next.js 16 and React 19 web application
├── backend/           # FastAPI API, providers, tests, and Alembic migrations
├── deploy/            # Docker and Vercel operating guides
├── docs/              # Product design, engineering plans, and reference notes
└── scripts/           # Cross-deployment smoke checks
```

## Quick start

### Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Node.js 22 and Corepack
- PostgreSQL with pgvector, Redis, and S3-compatible object storage
- Docker with Compose for the full-stack container profile

### Run with Docker

```bash
cp .env.example .env
# Replace every credential placeholder in .env.
docker compose up --build --wait
./scripts/smoke.sh
```

Open `http://localhost:3000/en-US/dashboard`. The API is available at
`http://localhost:8000`, with liveness and readiness endpoints under
`/api/v1/health`.

Detailed operations: [`deploy/docker/README.md`](deploy/docker/README.md).

### Run the applications natively

Copy the local backend environment template and point it at your local
PostgreSQL, Redis, and S3-compatible services:

```bash
cp backend/.env.example backend/.env
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.app:app --reload
```

Run the RQ worker in another terminal:

```bash
cd backend
uv run rq worker --with-scheduler --worker-class rq.worker.SimpleWorker \
  --url redis://localhost:6379/0 company-intelligence
```

`SimpleWorker` keeps native development compatible with macOS process-safety
rules. The Docker worker continues to use RQ's fork-based worker.

Start the web application in a second terminal:

```bash
cd frontend
cp .env.example .env.local
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

Browser language detection selects `/en-US` or `/zh-CN`. The language selector
stores the user's choice in a cookie.

The deterministic local journey uses SQLite and synchronous fake providers:

```bash
cd backend
uv run pytest tests/integration/test_company_research_journey.py \
  tests/integration/test_company_chat_journey.py \
  tests/chat/test_rag_evaluation.py -q
```

This test mode exercises the real routes, database models, quotas, pipeline,
citations, chat retrieval, Agent web decisions, streaming persistence, and
serializers with deterministic provider responses.

Research Agent deployment variables:

| Variable | Purpose |
|---|---|
| `SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE` | Optional graph-specific model; `RESEARCH_MODEL` remains the default |
| `SUPPLY_CHAIN_GRAPH_STAGE_TIMEOUT_SECONDS` | Per-stage model timeout; default `180` |
| `SUPPLY_CHAIN_GRAPH_MAX_OUTPUT_TOKENS` | Graph model output ceiling; default `16000` |
| `WORKFLOW_TRIGGER_URL` | Company-intelligence Workflow trigger |
| `SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL` | Supply-chain graph Workflow trigger |
| `CHAT_INDEX_WORKFLOW_TRIGGER_URL` | Zero-quota latest-10-K index Workflow trigger |
| `BLOB_READ_WRITE_TOKEN` | Private Vercel Blob access for official-source artifacts |
| `S3_ENDPOINT_URL`, `S3_BUCKET` | MinIO or S3-compatible graph artifact storage |
| `CHAT_WEB_ARTIFACT_PREFIX` | Private bounded web-evidence namespace; default `chat-web` |

Chat defaults allocate two guest messages and ten authenticated messages per
UTC day, retain guest conversations for seven days, retrieve at most eight
filing chunks, and fetch at most eight bounded web pages when the Agent elects
to search. Every `CHAT_*` setting is documented in
[`docs/deployment.md`](docs/deployment.md) and both environment templates.

### Google authentication

Create an OAuth 2.0 Web application in Google Cloud Console and configure these
Authorized JavaScript origins:

- `http://localhost:3000`
- the Vercel Preview origin used for verification
- the Vercel Production origin
- the public Docker deployment origin

Set the same client ID as `GOOGLE_CLIENT_ID` for FastAPI and
`NEXT_PUBLIC_GOOGLE_CLIENT_ID` for Next.js. FastAPI validates the Google ID
token. Next.js stores the resulting EquityLens access and refresh tokens in
HttpOnly cookies. Set `FRONTEND_URL` to the exact public web origin used by each
environment so same-origin mutation checks remain valid behind a proxy.

## Deployment

### Vercel

EquityLens uses two Vercel Projects connected to the repository:

1. Deploy `backend/` with the **Deploy API** button.
2. Copy the resulting API production URL.
3. Deploy `frontend/` with the **Deploy Web** button and set `BACKEND_URL` to
   the API URL.
4. Point `WORKFLOW_TRIGGER_URL`, `SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL`, and
   `CHAT_INDEX_WORKFLOW_TRIGGER_URL` at their Web Project Workflow routes.
5. Set the API Project's `CORS_ORIGINS` to the Web production origin and
   redeploy the API.
6. Run the shared smoke check against both production origins.

The API button requests the database, authentication, OpenAI, Blob, and parser
credentials required by the Vercel profile. Deploy Button defaults contain only
public profile values.

Full environment reference: [`deploy/vercel/README.md`](deploy/vercel/README.md).
The shared profile comparison and verification commands live in
[`docs/deployment.md`](docs/deployment.md).

### Docker

The Docker profile runs the web app, API, worker, PostgreSQL / pgvector, Redis,
and MinIO as one Compose project. See
[`deploy/docker/README.md`](deploy/docker/README.md) for lifecycle and
troubleshooting commands, including the SSE reverse-proxy contract.

## Health checks

| Service | Endpoint |
|---|---|
| Web | `GET /api/health` |
| API smoke alias | `GET /api/v1/health` |
| API liveness | `GET /api/v1/health/live` |
| API readiness | `GET /api/v1/health/ready` |

```bash
WEB_BASE_URL=https://web.example.com \
API_BASE_URL=https://api.example.com \
./scripts/smoke.sh
```

## Quality gates

```bash
cd backend
uv lock --check
uv run ruff check app tests
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
uv run alembic upgrade head
uv run alembic downgrade 20260714_0004
uv run alembic upgrade head

cd ../frontend
corepack pnpm install --frozen-lockfile
corepack pnpm test
corepack pnpm test:e2e
corepack pnpm exec tsc --noEmit
corepack pnpm lint
corepack pnpm build

cd ..
git diff --check
```

## Data-source boundaries

- SEC EDGAR supplies company identity, 10-K source documents, and XBRL Company
  Facts. Set `SEC_USER_AGENT` to an application name and monitored contact email,
  and respect the SEC's published automated-access policy.
- Yahoo data enters through a replaceable `MarketDataProvider` adapter for local
  research and evaluation. Public or commercial launch requires a separate
  data-license review. See the [Yahoo Terms of Service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html)
  and [Yahoo Developer Network Guidelines](https://legal.yahoo.com/us/en/yahoo/guidelines/ydn/index.html).
- Company conclusions come from automated model output and retain citations to
  the underlying SEC filing excerpt.

## Roadmap

- Manual filing upload and user-owned source libraries
- Saved research notes and exports
- DCF, peer multiples, and valuation scenario analysis
- Licensed production market-data adapter
- Additional filing types and refresh policies

## Contributing

Issues and pull requests are welcome during the Phase 2 beta.

1. Open an [issue](https://github.com/Linon419/equitylens/issues) for a feature,
   defect, or design proposal.
2. Create a focused branch and include tests or documentation for the change.
3. Run the relevant quality gates locally.
4. Open a pull request that explains the user impact and verification evidence.

## Security

- Store credentials in `.env`, Vercel Environment Variables, or your secret
  manager.
- Keep `.env` files, API keys, database URLs, and tokens out of commits and
  Deploy Button defaults.
- Report sensitive findings privately to the repository owner before opening a
  public issue.

## Acknowledgements

EquityLens builds on the original FastAPI, LangChain, PostgreSQL / pgvector,
ingestion, and infrastructure foundation from
[mazzasaverio/fastapi-langchain-rag](https://github.com/mazzasaverio/fastapi-langchain-rag).
Thank you to Saverio Mazza and the project's contributors for sharing that work.

This repository evolves the foundation into a product-specific US equity
research platform with a localized React interface, reproducible engineering
baseline, provider boundaries, database migration authority, and Vercel / Docker
deployment profiles.

## Disclaimer

EquityLens is research and educational software. Its outputs may contain errors,
delays, or incomplete information. Investment decisions require independent
verification and professional advice appropriate to the investor's situation.
