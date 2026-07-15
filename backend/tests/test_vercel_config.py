import json
from pathlib import Path

from fastapi import FastAPI

from app.app import app


def test_vercel_entrypoint_exports_fastapi_app() -> None:
    assert isinstance(app, FastAPI)


def test_vercel_bundle_excludes_tests() -> None:
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "vercel.json").read_text())
    function = config["functions"]["app/app.py"]

    assert "tests/**" in function["excludeFiles"]
    assert "app/ingestion/**" in function["excludeFiles"]
    assert "data/**" in function["excludeFiles"]
    assert "app/supply_chain/**" not in function["excludeFiles"]
    assert "app/jobs/**" not in function["excludeFiles"]
    assert function["maxDuration"] == 300


def test_vercel_docs_include_workflow_wiring() -> None:
    root = Path(__file__).resolve().parents[2]
    guide = (root / "deploy" / "vercel" / "README.md").read_text()

    assert "INTERNAL_JOB_SECRET" in guide
    assert "WORKFLOW_TRIGGER_URL" in guide
    assert "SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL" in guide
    assert "CHAT_INDEX_WORKFLOW_TRIGGER_URL" in guide
    assert "/api/internal/workflows/company-intelligence" in guide
    assert "/api/internal/workflows/supply-chain-graph" in guide
    assert "/api/internal/workflows/filing-index" in guide
    assert "BLOB_READ_WRITE_TOKEN" in guide
    assert "private Vercel Blob" in guide


def test_vercel_has_a_durable_filing_index_workflow() -> None:
    root = Path(__file__).resolve().parents[2]
    route = root / "frontend/src/app/api/internal/workflows/filing-index/route.ts"
    workflow = root / "frontend/src/workflows/filing-index.ts"

    assert route.exists()
    assert workflow.exists()
    assert "filingIndexWorkflow" in route.read_text()
    assert "/filing-index" in workflow.read_text()
    assert "filing-index:v1" in workflow.read_text()


def test_research_bff_forces_dynamic_uncached_streaming() -> None:
    root = Path(__file__).resolve().parents[2]
    route = (
        root / "frontend/src/app/api/research/[...path]/route.ts"
    ).read_text()

    assert 'export const dynamic = "force-dynamic"' in route
    assert 'export const fetchCache = "force-no-store"' in route
    assert "streaming" in route and "upstream.body" in route
    assert '"cache-control"' in route
    assert '"x-accel-buffering"' in route
