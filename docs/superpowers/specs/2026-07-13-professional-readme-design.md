# EquityLens Professional README Design

## Goal

Replace the repository root README with a polished, accurate entry point for
contributors and self-hosters. The README will explain the retail-investor
research product, distinguish the Phase 0 foundation from roadmap capabilities,
provide two Vercel deployment buttons for the monorepo, and credit the upstream
project that informed the original backend foundation.

## Audience and Voice

- Primary audience: developers evaluating, running, or contributing to EquityLens.
- Secondary audience: individual investors who want to understand the product
  direction.
- Language: English.
- Voice: concise, evidence-oriented, technically precise, and transparent about
  delivery status.
- Project status: `Early Development / Phase 0`.

## README Structure

1. **Hero**
   - EquityLens title and a one-sentence value proposition.
   - Static technology badges and an `Early Development` status badge.
   - Two Vercel deployment buttons, ordered API first and Web second.
2. **Why EquityLens**
   - Explain the connected research model: business, value chain, filings,
     financials, valuation, and cited answers.
3. **Project status**
   - A capability table separating implemented Phase 0 foundations from planned
     product features.
4. **Architecture**
   - A compact Mermaid diagram covering browser, Next.js, FastAPI, PostgreSQL /
     pgvector, object storage, job backend, SEC data, market data, and the LLM.
   - A short deployment-profile comparison for Vercel and Docker.
5. **Repository layout and stack**
   - Directory responsibilities and pinned runtime families.
6. **Quick start**
   - Native backend and frontend commands.
   - Health URLs and expected local ports.
7. **Deployment**
   - Vercel two-project flow with environment prerequisites and a link to the
     detailed guide.
   - Docker Compose flow with a link to the Docker guide.
8. **Quality**
   - Backend and frontend verification commands already supported by the repo.
9. **Roadmap**
   - User accounts, company data, SEC retrieval, filing ingestion, value-chain
     mapping, valuation, and cited RAG research.
10. **Contributing, security, and disclaimer**
    - Issue-first contribution guidance.
    - Secret-handling guidance.
    - Research and education disclaimer for financial information.
11. **Acknowledgements**
    - Credit `mazzasaverio/fastapi-langchain-rag` for the original FastAPI,
      LangChain, PostgreSQL / pgvector, ingestion, and infrastructure foundation.
    - Describe EquityLens as a substantial product-specific evolution with a new
      frontend, engineering baseline, provider boundaries, and dual deployment
      profiles.

## Vercel Deploy Buttons

Vercel requires a separate Project for each deployable monorepo directory. Each
button will use Vercel's official Deploy Button URL and the `root-directory`
parameter.

### API button

- Repository: `https://github.com/Linon419/equitylens`
- Root directory: `backend`
- Default project name: `equitylens-api`
- Required environment keys:
  - `DATABASE_URL`
  - `SECRET_KEY_ACCESS_API`
  - `OPENAI_API_KEY`
  - `OPENAI_ORGANIZATION`
  - `FIRST_SUPERUSER`
  - `FIRST_SUPERUSER_PASSWORD`
  - `BLOB_READ_WRITE_TOKEN`
  - `MANAGED_PARSER_API_KEY`
  - `CORS_ORIGINS`
  - `DEPLOYMENT_TARGET`
  - `OBJECT_STORAGE_PROVIDER`
  - `JOB_BACKEND`
  - `DOCUMENT_PARSER`
- Non-secret defaults:
  - `DEPLOYMENT_TARGET=vercel`
  - `OBJECT_STORAGE_PROVIDER=vercel_blob`
  - `JOB_BACKEND=vercel_workflow`
  - `DOCUMENT_PARSER=managed`

### Web button

- Repository: `https://github.com/Linon419/equitylens`
- Root directory: `frontend`
- Default project name: `equitylens-web`
- Required environment key: `NEXT_PUBLIC_API_BASE_URL`

The README will explain that the API is deployed first. After the Web URL is
known, `CORS_ORIGINS` is updated on the API Project and the API is redeployed.
Sensitive values will always be entered through Vercel; they will never appear
as URL defaults.

## Supporting Documentation Changes

Update `deploy/vercel/README.md` to use `equitylens-api` and `equitylens-web`,
match the API-first deployment sequence, and explain the final CORS update.
The generated Create Next App text in `frontend/README.md` will be replaced with
a short component README that points readers to the root quick start and the
Vercel guide.

## Validation

- Parse every Deploy Button URL and assert its repository, root directory,
  project name, environment keys, and non-secret defaults.
- Check all local Markdown links referenced from the root README.
- Search repository-facing documentation for stale product and deployment names.
- Run `git diff --check`.
- Run the existing backend and frontend test, lint, and build gates because the
  deployment documentation describes those commands as supported workflows.

## Scope Boundaries

- This change updates documentation and deployment entry points.
- It does not create Vercel Projects or perform a production deployment.
- It does not add a software license; license selection remains an explicit
  repository-owner decision.
