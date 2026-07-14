# Product status

Status date: 2026-07-14  
Release stage: Phase 2 beta

## Implemented user journey

1. A visitor opens the English or Chinese public research dashboard.
2. Company search resolves a US ticker through a replaceable market provider.
3. The company dossier presents identity, sector, industry, current price,
   market cap, EPS, trailing P/E, forward P/E, and source timestamps.
4. SEC Company Facts supplies four fiscal years plus TTM for revenue, net
   income, operating cash flow, capital expenditure, and free cash flow.
5. The research Agent retrieves the latest 10-K and moves through durable
   download, parse, analyze, verify, and localize states.
6. Key businesses retain citation IDs, filing sections, capped excerpts, and
   source links.
7. The supply-chain Agent plans official sources, extracts relationships,
   resolves entities, verifies evidence, localizes labels, and publishes a
   25–40 node graph.
8. Investors can inspect verified and potential relationships, exact official
   excerpts, evidence URLs, upstream/downstream layers, and related public
   companies that can become the next research center.
9. Visitors receive two accepted Agent jobs per UTC day across the shared
   intelligence and graph quota pool. Authenticated users receive ten. Active
   jobs and cached graph snapshots cost zero additional units.
10. Retryable graph failures refund quota idempotently and preserve the latest
    published graph during refresh.
11. Google users can persist and remove watchlist companies.

## Implemented engineering surface

| Surface | Current implementation |
|---|---|
| Frontend | Next.js 16, React 19, bilingual public dashboard and dossier |
| Backend | FastAPI, SQLModel, Alembic, provider contracts |
| Market context | Yahoo development adapter with cache and stale fallback |
| Financials | SEC XBRL Company Facts mapping with annual/TTM provenance |
| Filings | Latest 10-K selection, compressed artifact persistence, section parsing |
| Intelligence | Structured generation, verification, localization invariants, citations |
| Supply-chain graph | AI source planning/extraction/verification/localization plus deterministic publication gates |
| Graph evidence | Private S3/MinIO or Vercel Blob artifacts with public capped excerpts |
| Jobs | Database state machine with Vercel Workflow and Redis/RQ adapters |
| Identity | Signed guest principal, rotating Google sessions, same-origin BFF |
| Quality | Backend suite, 126 frontend tests, production build, and 9 Playwright journeys |

## Release validation (Docker host gate pending)

The native and Vercel-build graph slice passed the backend suite, Ruff,
deployment contract tests, 126 frontend tests, TypeScript, ESLint, the Next.js
production build, and all 9 Chromium journeys on 2026-07-14. Docker descriptor
structure passed YAML and contract validation. Release status remains pending
until Docker Compose config and image builds pass on a Docker-enabled release host.

## Launch gates

- Licensed production market-data source and redistribution terms
- Production PostgreSQL, Redis, Workflow, secrets, and monitoring
- Object-storage adapter for large filing libraries and lifecycle policies
- Model evaluation set for business and value-chain claim quality
- Abuse telemetry, rate monitoring, privacy review, and incident runbooks
- Accessibility and cross-browser release audit
- Docker Compose config and image build on a Docker-enabled release host

## Planned product work

- Manual filing upload
- Research chat with citation-level retrieval
- DCF, peer multiples, and valuation scenarios
- Saved notes and research history
- 10-Q and additional source coverage
- Company refresh policies and change detection

The shipped interface focuses on business understanding, industry position,
financial context, and source evidence. Historical price charts remain outside
the current product scope.
