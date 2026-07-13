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
    assert function["maxDuration"] == 300
