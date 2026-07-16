import json
from pathlib import Path


def test_vercel_deploys_only_the_web_service() -> None:
    root = Path(__file__).resolve().parents[2]
    config = json.loads((root / "vercel.json").read_text())

    web = config["services"]["web"]
    assert set(config["services"]) == {"web"}
    assert web["root"] == "frontend/"
    assert web["framework"] == "nextjs"
    assert "bindings" not in web
    assert config["rewrites"] == [
        {"source": "/(.*)", "destination": {"service": "web"}},
    ]


def test_vercel_docs_include_vps_wiring() -> None:
    root = Path(__file__).resolve().parents[2]
    guide = (root / "deploy" / "vercel" / "README.md").read_text()

    assert "INTERNAL_JOB_SECRET" in guide
    assert "BACKEND_URL" in guide
    assert "Sydney VPS" in guide
    assert "Redis" in guide
    assert "RQ" in guide
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
