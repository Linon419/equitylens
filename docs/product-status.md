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
6. Key businesses and upstream/company/downstream claims retain citation IDs,
   filing sections, capped excerpts, and source links.
7. Visitors receive two Agent analyses per UTC day. Authenticated users receive
   ten. A shared IP ceiling protects the guest path.
8. Google users can persist and remove watchlist companies.

## Implemented engineering surface

| Surface | Current implementation |
|---|---|
| Frontend | Next.js 16, React 19, bilingual public dashboard and dossier |
| Backend | FastAPI, SQLModel, Alembic, provider contracts |
| Market context | Yahoo development adapter with cache and stale fallback |
| Financials | SEC XBRL Company Facts mapping with annual/TTM provenance |
| Filings | Latest 10-K selection, compressed artifact persistence, section parsing |
| Intelligence | Structured generation, verification, localization invariants, citations |
| Jobs | Database state machine with Vercel Workflow and Redis/RQ adapters |
| Identity | Signed guest principal, rotating Google sessions, same-origin BFF |
| Quality | Unit, API, integration, migration, build, and Playwright journeys |

## Launch gates

- Licensed production market-data source and redistribution terms
- Production PostgreSQL, Redis, Workflow, secrets, and monitoring
- Object-storage adapter for large filing libraries and lifecycle policies
- Model evaluation set for business and value-chain claim quality
- Abuse telemetry, rate monitoring, privacy review, and incident runbooks
- Accessibility and cross-browser release audit

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
