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
    assert "/api/internal/workflows/company-intelligence" in guide
    assert "/api/internal/workflows/supply-chain-graph" in guide
    assert "BLOB_READ_WRITE_TOKEN" in guide
    assert "private Vercel Blob" in guide
