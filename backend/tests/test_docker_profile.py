import json
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_compose_defines_the_complete_application_stack() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = compose["services"]

    assert compose["name"] == "equitylens"
    assert services["db"]["environment"]["POSTGRES_DB"] == (
        "${POSTGRES_DB:-equitylens}"
    )
    assert {"db", "redis", "minio", "migrate", "api", "worker", "web"} <= set(
        services
    )
    assert services["api"]["build"]["target"] == "api"
    assert services["worker"]["build"]["target"] == "worker"
    assert services["web"]["build"]["context"] == "./frontend"
    assert services["web"]["environment"]["GUEST_SIGNING_SECRET"] == (
        "${GUEST_SIGNING_SECRET}"
    )
    assert services["web"]["environment"]["INTERNAL_JOB_SECRET"] == (
        "${INTERNAL_JOB_SECRET}"
    )
    assert services["api"]["depends_on"]["migrate"]["condition"] == (
        "service_completed_successfully"
    )


def test_dockerfiles_use_pinned_runtimes_and_reproducible_installs() -> None:
    backend = (ROOT / "backend" / "Dockerfile").read_text()
    frontend = (ROOT / "frontend" / "Dockerfile").read_text()

    assert "FROM python:3.12-slim" in backend
    assert "uv sync --frozen --no-dev" in backend
    assert "COPY alembic.ini ./" in backend
    assert 'CMD ["uvicorn", "app.app:app"' in backend
    assert (
        'CMD ["rq", "worker", "--url", "redis://redis:6379/0", '
        '"company-intelligence"]' in backend
    )
    assert "FROM node:22-alpine" in frontend
    assert "COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./" in frontend
    assert "pnpm install --frozen-lockfile" in frontend
    assert "/app/.next/standalone" in frontend


def test_migration_runtime_includes_alembic() -> None:
    pyproject = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())
    package = json.loads((ROOT / "frontend" / "package.json").read_text())

    assert pyproject["project"]["name"] == "equitylens-api"
    assert package["name"] == "equitylens-web"
    assert any(
        dependency.startswith("alembic")
        for dependency in pyproject["project"]["dependencies"]
    )


def test_environment_template_contains_placeholders_only() -> None:
    template = (ROOT / ".env.example").read_text()

    assert "DEPLOYMENT_TARGET=docker" in template
    assert "OPENAI_API_KEY=replace-with-openai-key" in template
    assert (
        "SECRET_KEY_ACCESS_API=replace-with-at-least-32-random-characters" in template
    )
    assert "GOOGLE_CLIENT_ID=replace-with-google-client-id" in template
    assert "BACKEND_URL=http://api:8000" in template
    assert "NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id" in template


def test_native_backend_template_uses_local_service_addresses() -> None:
    template = (ROOT / "backend" / ".env.example").read_text()

    assert (
        "DATABASE_URL=postgresql://app:app@localhost:5432/equitylens" in template
    )
    assert "REDIS_URL=redis://localhost:6379/0" in template
    assert "S3_ENDPOINT_URL=http://localhost:9000" in template
