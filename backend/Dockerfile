# syntax=docker/dockerfile:1
FROM python:3.12-slim AS api-build

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY alembic.ini ./
COPY app ./app

FROM api-build AS worker-build
RUN uv sync --frozen --no-dev --group worker

FROM python:3.12-slim AS api
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=api-build /app /app
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health/live')"
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.12-slim AS worker
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=worker-build /app /app
CMD ["rq", "worker", "--url", "redis://redis:6379/0", "ingestion"]
