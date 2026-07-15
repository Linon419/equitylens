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
    assert services["db"]["image"].startswith("pgvector/pgvector:")
    assert {
        "db",
        "redis",
        "minio",
        "minio-init",
        "migrate",
        "api",
        "worker",
        "web",
    } <= set(services)
    init = services["minio-init"]
    assert init["depends_on"]["minio"]["condition"] == "service_healthy"
    assert "ports" not in services["minio"]
    assert services["minio"]["environment"]["MINIO_ROOT_USER"].startswith(
        "${MINIO_ROOT_USER:?"
    )
    assert services["minio"]["environment"]["MINIO_ROOT_PASSWORD"].startswith(
        "${MINIO_ROOT_PASSWORD:?"
    )
    assert "mc ready local" in init["command"]
    assert "mc mb --ignore-existing" in init["command"]
    assert "mc anonymous set none" in init["command"]
    assert "mc admin user add" in init["command"]
    assert "mc admin policy create" in init["command"]
    assert "mc admin policy attach" in init["command"]
    assert '"arn:aws:s3:::%s/*"' in init["command"]
    assert '"$${S3_BUCKET}" "$${S3_BUCKET}"' in init["command"]
    assert init["environment"]["S3_BUCKET"] == "${S3_BUCKET:-filings}"
    assert services["api"]["build"]["target"] == "api"
    assert services["api"]["ports"] == ["${API_PORT:-8000}:8000"]
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
    for service_name in ("api", "worker"):
        service = services[service_name]
        assert service["depends_on"]["minio-init"]["condition"] == (
            "service_completed_successfully"
        )
        assert service["environment"]["OBJECT_STORAGE_PROVIDER"] == (
            "${OBJECT_STORAGE_PROVIDER:-s3}"
        )
        assert service["environment"]["S3_ENDPOINT_URL"] == (
            "${S3_ENDPOINT_URL:-http://minio:9000}"
        )
        assert service["environment"]["S3_BUCKET"] == "${S3_BUCKET:-filings}"
        assert service["environment"]["S3_ACCESS_KEY_ID"].startswith(
            "${S3_ACCESS_KEY_ID:?"
        )
        assert service["environment"]["S3_SECRET_ACCESS_KEY"].startswith(
            "${S3_SECRET_ACCESS_KEY:?"
        )
        assert service["environment"]["SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE"] == (
            "${SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE:-}"
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


def test_worker_image_packages_the_graph_runtime_and_s3_client() -> None:
    pyproject = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())
    dockerfile = (ROOT / "backend" / "Dockerfile").read_text()
    tasks = (ROOT / "backend" / "app" / "jobs" / "tasks.py").read_text()

    assert any(
        dependency.startswith("boto3")
        for dependency in pyproject["project"]["dependencies"]
    )
    assert "COPY app ./app" in dockerfile
    assert "SupplyChainGraphPipeline" in tasks
    assert "run_supply_chain_graph" in tasks


def test_docker_worker_and_proxy_guidance_support_research_chat() -> None:
    rq_backend = (ROOT / "backend" / "app" / "jobs" / "rq_backend.py").read_text()
    tasks = (ROOT / "backend" / "app" / "jobs" / "tasks.py").read_text()
    guide = (ROOT / "deploy" / "docker" / "README.md").read_text()

    assert '"filing_index": "app.jobs.tasks.run_filing_index"' in rq_backend
    assert "def run_filing_index(" in tasks
    assert "proxy_buffering off;" in guide
    assert "X-Accel-Buffering" in guide
    assert "text/event-stream" in guide


def test_environment_template_contains_placeholders_only() -> None:
    template = (ROOT / ".env.example").read_text()

    assert "DEPLOYMENT_TARGET=docker" in template
    assert "OPENAI_API_KEY=replace-with-openai-key" in template
    assert "OPENAI_BASE_URL=" in template
    assert "LLM_API_KEY=" in template
    assert "LLM_BASE_URL=" in template
    assert "LLM_STRUCTURED_OUTPUT_METHOD=json_schema" in template
    assert (
        "SECRET_KEY_ACCESS_API=replace-with-at-least-32-random-characters" in template
    )
    assert "GOOGLE_CLIENT_ID=replace-with-google-client-id" in template
    assert "BACKEND_URL=http://api:8000" in template
    assert "NEXT_PUBLIC_GOOGLE_CLIENT_ID=replace-with-google-client-id" in template
    assert "SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE=" in template
    assert "SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL=" in template
    assert "CHAT_INDEX_WORKFLOW_TRIGGER_URL=" in template
    assert "CHAT_GUEST_DAILY_LIMIT=2" in template
    assert "CHAT_USER_DAILY_LIMIT=10" in template
    assert "CHAT_GUEST_RETENTION_DAYS=7" in template
    assert "MINIO_ROOT_USER=replace-with-minio-root-user" in template
    assert "MINIO_ROOT_PASSWORD=replace-with-minio-root-password" in template
    assert "S3_ACCESS_KEY_ID=replace-with-minio-app-user" in template
    assert "S3_SECRET_ACCESS_KEY=replace-with-minio-app-password" in template


def test_native_backend_template_uses_local_service_addresses() -> None:
    template = (ROOT / "backend" / ".env.example").read_text()

    assert (
        "DATABASE_URL=postgresql://app:app@localhost:5432/equitylens" in template
    )
    assert "REDIS_URL=redis://localhost:6379/0" in template
    assert "S3_ENDPOINT_URL=http://localhost:9000" in template
    assert "OPENAI_BASE_URL=" in template
    assert "LLM_API_KEY=" in template
    assert "LLM_BASE_URL=" in template
    assert "LLM_STRUCTURED_OUTPUT_METHOD=json_schema" in template
