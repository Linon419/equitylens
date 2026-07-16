import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = {
    "SECRET_KEY_ACCESS_API": "x" * 32,
    "DATABASE_URL": "postgresql://app:app@localhost:5432/equitylens",
    "OPENAI_API_KEY": "test",
    "OPENAI_ORGANIZATION": "test",
    "FIRST_SUPERUSER": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "test-password",
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "FRONTEND_URL": "http://localhost:3000",
    "SEC_USER_AGENT": "EquityLens test admin@example.com",
    "GUEST_SIGNING_SECRET": "g" * 32,
    "QUOTA_HASH_SECRET": "q" * 32,
    "INTERNAL_JOB_SECRET": "i" * 32,
}

DOCKER_PROVIDERS = {
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_BUCKET": "filings",
    "S3_ACCESS_KEY_ID": "test-access-key",
    "S3_SECRET_ACCESS_KEY": "test-secret-key",
}

VERCEL_PROVIDERS = {
    "BLOB_READ_WRITE_TOKEN": "test-blob-token",
    "MANAGED_PARSER_API_KEY": "test-parser-key",
    "WORKFLOW_TRIGGER_URL": "https://example.vercel.app/api/internal/workflows/company-intelligence",
    "SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL": (
        "https://example.vercel.app/api/internal/workflows/supply-chain"
    ),
    "CHAT_INDEX_WORKFLOW_TRIGGER_URL": (
        "https://example.vercel.app/api/internal/workflows/chat-index"
    ),
}


@pytest.fixture(autouse=True)
def isolate_local_model_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in (
        "OPENAI_BASE_URL",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_STRUCTURED_OUTPUT_METHOD",
        "RESEARCH_MODEL",
        "SUPPLY_CHAIN_GRAPH_STAGE_TIMEOUT_SECONDS",
        "CHAT_EMBEDDING_MODEL",
        "CHAT_PROMPT_VERSION",
        "CHAT_WEB_SEARCH_PROVIDER",
        "CHAT_TAVILY_SEARCH_DEPTH",
        "CHAT_TAVILY_MAX_RESULTS",
    ):
        monkeypatch.delenv(field, raising=False)


def test_docker_profile_accepts_docker_providers() -> None:
    settings = Settings(
        _env_file=None,
        **BASE,
        **DOCKER_PROVIDERS,
        DEPLOYMENT_TARGET="docker",
        OBJECT_STORAGE_PROVIDER="s3",
        JOB_BACKEND="rq",
        DOCUMENT_PARSER="local",
    )

    assert settings.DEPLOYMENT_TARGET == "docker"
    assert settings.PROJECT_NAME == "equitylens-api"
    assert settings.SYNC_DATABASE_URI.startswith("postgresql+psycopg2://")
    assert settings.ASYNC_DATABASE_URI.startswith("postgresql+asyncpg://")
    assert "app:app@" in settings.SYNC_DATABASE_URI
    assert "app:app@" in settings.ASYNC_DATABASE_URI
    assert settings.MARKET_DATA_PROVIDER == "yahoo"
    assert settings.RESEARCH_MODEL == "gpt-5-mini"
    assert settings.GUEST_DAILY_ANALYSIS_LIMIT == 2
    assert settings.USER_DAILY_ANALYSIS_LIMIT == 10
    assert settings.IP_DAILY_ANALYSIS_LIMIT == 10
    assert settings.MARKET_QUOTE_TTL_SECONDS == 900
    assert settings.OPENAI_BASE_URL is None
    assert settings.LLM_API_KEY is None
    assert settings.LLM_BASE_URL is None
    assert settings.LLM_STRUCTURED_OUTPUT_METHOD == "json_schema"
    assert settings.LLM_API_KEY_VALUE == "test"
    assert settings.LLM_BASE_URL_VALUE is None
    assert settings.LLM_ORGANIZATION == "test"


def test_cors_origins_accepts_single_origin_environment_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    settings = Settings(_env_file=None)

    assert settings.CORS_ORIGINS == ["http://localhost:3000"]


def test_custom_llm_endpoint_is_independent_from_openai_services() -> None:
    settings = Settings(
        **BASE,
        **DOCKER_PROVIDERS,
        OPENAI_BASE_URL="https://openai-proxy.example/v1/",
        LLM_API_KEY="deepseek-key",
        LLM_BASE_URL="https://api.deepseek.com/beta/",
        LLM_STRUCTURED_OUTPUT_METHOD="function_calling",
    )

    assert settings.OPENAI_BASE_URL == "https://openai-proxy.example/v1"
    assert settings.LLM_API_KEY_VALUE == "deepseek-key"
    assert settings.LLM_BASE_URL_VALUE == "https://api.deepseek.com/beta"
    assert settings.LLM_STRUCTURED_OUTPUT_METHOD == "function_calling"
    assert settings.LLM_ORGANIZATION is None


def test_json_mode_is_available_for_thinking_model_providers() -> None:
    settings = Settings(
        **BASE,
        **DOCKER_PROVIDERS,
        LLM_API_KEY="deepseek-key",
        LLM_BASE_URL="https://api.deepseek.com",
        LLM_STRUCTURED_OUTPUT_METHOD="json_mode",
    )

    assert settings.LLM_STRUCTURED_OUTPUT_METHOD == "json_mode"


def test_blank_llm_overrides_fall_back_to_openai() -> None:
    settings = Settings(
        **BASE,
        **DOCKER_PROVIDERS,
        LLM_API_KEY=" ",
        LLM_BASE_URL=" ",
    )

    assert settings.LLM_API_KEY is None
    assert settings.LLM_BASE_URL is None
    assert settings.LLM_API_KEY_VALUE == "test"
    assert settings.LLM_ORGANIZATION == "test"


@pytest.mark.parametrize("field", ["OPENAI_BASE_URL", "LLM_BASE_URL"])
def test_provider_base_urls_require_absolute_http_urls(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        Settings(
            **BASE,
            **DOCKER_PROVIDERS,
            **{field: "api.provider.example/v1"},
        )


def test_supply_chain_graph_defaults_follow_research_model(monkeypatch) -> None:
    research_model = "test-research-model"
    monkeypatch.setenv("RESEARCH_MODEL", research_model)
    monkeypatch.delenv("SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE", raising=False)
    settings = Settings(_env_file=None)

    assert research_model == settings.RESEARCH_MODEL
    assert settings.SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE is None
    assert research_model == settings.SUPPLY_CHAIN_GRAPH_MODEL
    assert settings.SUPPLY_CHAIN_GRAPH_SCHEMA_VERSION == "supply-chain-graph.v1"
    assert settings.SUPPLY_CHAIN_GRAPH_PROMPT_VERSION == "supply-chain-graph.2026-07-14"
    assert settings.SUPPLY_CHAIN_GRAPH_MAX_NODES == 40
    assert settings.SUPPLY_CHAIN_GRAPH_MIN_NODES == 25
    assert settings.SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD == 0.75
    assert settings.SUPPLY_CHAIN_GRAPH_SOURCE_BYTES == 32_000_000
    assert settings.SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET == 100_000
    assert settings.SUPPLY_CHAIN_GRAPH_STAGE_TIMEOUT_SECONDS == 180
    assert settings.SUPPLY_CHAIN_GRAPH_MAX_OUTPUT_TOKENS == 16_000


def test_supply_chain_graph_model_override_takes_precedence(monkeypatch) -> None:
    research_model = "test-research-model"
    graph_model = "test-graph-model"
    monkeypatch.setenv("RESEARCH_MODEL", research_model)
    monkeypatch.setenv("SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE", graph_model)
    settings = Settings(_env_file=None)

    assert research_model == settings.RESEARCH_MODEL
    assert graph_model == settings.SUPPLY_CHAIN_GRAPH_MODEL_OVERRIDE
    assert graph_model == settings.SUPPLY_CHAIN_GRAPH_MODEL


def test_chat_defaults_follow_approved_contract() -> None:
    value = Settings(
        _env_file=None,
        **BASE,
        **DOCKER_PROVIDERS,
        RESEARCH_MODEL="gpt-5-mini",
        CHAT_MODEL_OVERRIDE=None,
    )

    assert value.CHAT_MODEL == "gpt-5-mini"
    assert value.CHAT_GUEST_DAILY_LIMIT == 2
    assert value.CHAT_USER_DAILY_LIMIT == 10
    assert value.CHAT_GUEST_RETENTION_DAYS == 7
    assert value.CHAT_MAX_MESSAGE_CHARS == 2_000
    assert value.CHAT_MAX_HISTORY_MESSAGES == 8
    assert value.CHAT_CHUNK_TARGET_TOKENS == 700
    assert value.CHAT_CHUNK_OVERLAP_TOKENS == 100
    assert value.CHAT_CHUNK_MIN_FINAL_TOKENS == 120
    assert value.CHAT_RETRIEVAL_CANDIDATES == 20
    assert value.CHAT_RETRIEVAL_MAX_CHUNKS == 8
    assert value.CHAT_RETRIEVAL_MAX_PER_SECTION == 3
    assert value.CHAT_RETRIEVAL_TOKEN_BUDGET == 6_000
    assert value.CHAT_RRF_K == 60
    assert value.CHAT_WEB_MAX_QUERIES == 3
    assert value.CHAT_WEB_MAX_PAGES == 8
    assert value.CHAT_WEB_SEARCH_PROVIDER == "tavily"
    assert value.CHAT_TAVILY_SEARCH_DEPTH == "basic"
    assert value.CHAT_TAVILY_MAX_RESULTS == 5
    assert value.CHAT_EMBEDDING_MODEL == "text-embedding-3-small"
    assert value.CHAT_EMBEDDING_DIMENSIONS == 1_536
    assert value.CHAT_PROMPT_VERSION == "company-chat.2026-07-15-market-analysis"
    assert value.CHAT_ANSWER_SCHEMA_VERSION == "company-chat.v1"
    assert value.CHAT_INDEX_SCHEMA_VERSION == "filing-chunk.v1"


def test_chat_model_override_takes_precedence() -> None:
    value = Settings(
        **BASE,
        **DOCKER_PROVIDERS,
        RESEARCH_MODEL="gpt-5-mini",
        CHAT_MODEL_OVERRIDE="gpt-5.4",
    )

    assert value.CHAT_MODEL == "gpt-5.4"


@pytest.mark.parametrize(
    ("overrides", "invalid_field"),
    [
        ({"CHAT_WEB_SEARCH_PROVIDER": "unknown"}, "CHAT_WEB_SEARCH_PROVIDER"),
        ({"CHAT_TAVILY_SEARCH_DEPTH": "deep"}, "CHAT_TAVILY_SEARCH_DEPTH"),
    ],
)
def test_chat_rejects_unknown_web_search_configuration(
    overrides: dict[str, str],
    invalid_field: str,
) -> None:
    with pytest.raises(ValidationError, match=invalid_field):
        Settings(**BASE, **DOCKER_PROVIDERS, **overrides)


@pytest.mark.parametrize(
    ("overrides", "invalid_field"),
    [
        (
            {
                "CHAT_CHUNK_TARGET_TOKENS": 100,
                "CHAT_CHUNK_OVERLAP_TOKENS": 100,
            },
            "CHAT_CHUNK_OVERLAP_TOKENS",
        ),
        (
            {
                "CHAT_CHUNK_TARGET_TOKENS": 100,
                "CHAT_CHUNK_OVERLAP_TOKENS": 10,
                "CHAT_CHUNK_MIN_FINAL_TOKENS": 101,
            },
            "CHAT_CHUNK_MIN_FINAL_TOKENS",
        ),
        (
            {
                "CHAT_RETRIEVAL_CANDIDATES": 7,
                "CHAT_RETRIEVAL_MAX_CHUNKS": 8,
            },
            "CHAT_RETRIEVAL_MAX_CHUNKS",
        ),
        (
            {
                "CHAT_RETRIEVAL_MAX_CHUNKS": 2,
                "CHAT_RETRIEVAL_MAX_PER_SECTION": 3,
            },
            "CHAT_RETRIEVAL_MAX_PER_SECTION",
        ),
        (
            {"CHAT_EMBEDDING_DIMENSIONS": 3_072},
            "CHAT_EMBEDDING_DIMENSIONS",
        ),
        (
            {"CHAT_WEB_MAX_QUERIES": 0},
            "CHAT_WEB_MAX_QUERIES",
        ),
    ],
)
def test_chat_rejects_invalid_bounds(
    overrides: dict[str, int],
    invalid_field: str,
) -> None:
    with pytest.raises(ValidationError, match=invalid_field):
        Settings(**BASE, **DOCKER_PROVIDERS, **overrides)


@pytest.mark.parametrize(
    ("overrides", "invalid_field"),
    [
        ({"SUPPLY_CHAIN_GRAPH_MIN_NODES": 0}, "SUPPLY_CHAIN_GRAPH_MIN_NODES"),
        (
            {
                "SUPPLY_CHAIN_GRAPH_MIN_NODES": 25,
                "SUPPLY_CHAIN_GRAPH_MAX_NODES": 24,
            },
            "SUPPLY_CHAIN_GRAPH_MAX_NODES",
        ),
        (
            {"SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD": -0.01},
            "SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD",
        ),
        (
            {"SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD": 1.01},
            "SUPPLY_CHAIN_GRAPH_EVIDENCE_THRESHOLD",
        ),
        (
            {"SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET": 0},
            "SUPPLY_CHAIN_GRAPH_EVIDENCE_TOKEN_BUDGET",
        ),
    ],
)
def test_supply_chain_graph_rejects_invalid_bounds(
    overrides: dict[str, int | float], invalid_field: str
) -> None:
    with pytest.raises(ValidationError, match=invalid_field):
        Settings(**BASE, **DOCKER_PROVIDERS, **overrides)


def test_vercel_profile_accepts_vercel_providers() -> None:
    settings = Settings(
        **BASE,
        **VERCEL_PROVIDERS,
        DEPLOYMENT_TARGET="vercel",
        OBJECT_STORAGE_PROVIDER="vercel_blob",
        JOB_BACKEND="vercel_workflow",
        DOCUMENT_PARSER="managed",
    )

    assert settings.DEPLOYMENT_TARGET == "vercel"


def test_profile_rejects_mixed_provider_configuration() -> None:
    with pytest.raises(ValidationError, match="Docker profile requires"):
        Settings(
            **BASE,
            **DOCKER_PROVIDERS,
            DEPLOYMENT_TARGET="docker",
            OBJECT_STORAGE_PROVIDER="vercel_blob",
            JOB_BACKEND="rq",
            DOCUMENT_PARSER="local",
        )


@pytest.mark.parametrize(
    "field",
    ["GUEST_SIGNING_SECRET", "QUOTA_HASH_SECRET", "INTERNAL_JOB_SECRET"],
)
def test_profile_rejects_short_phase_2_secrets(field: str) -> None:
    values = {**BASE, **DOCKER_PROVIDERS, field: "short"}

    with pytest.raises(ValidationError, match=field):
        Settings(**values)


@pytest.mark.parametrize(
    "field",
    [
        "WORKFLOW_TRIGGER_URL",
        "SUPPLY_CHAIN_WORKFLOW_TRIGGER_URL",
        "CHAT_INDEX_WORKFLOW_TRIGGER_URL",
    ],
)
def test_vercel_profile_requires_workflow_trigger_url(field: str) -> None:
    providers = {**VERCEL_PROVIDERS, field: None}

    with pytest.raises(ValidationError, match=field):
        Settings(
            **BASE,
            **providers,
            DEPLOYMENT_TARGET="vercel",
            OBJECT_STORAGE_PROVIDER="vercel_blob",
            JOB_BACKEND="vercel_workflow",
            DOCUMENT_PARSER="managed",
        )
