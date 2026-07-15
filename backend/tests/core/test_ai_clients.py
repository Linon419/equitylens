from types import SimpleNamespace
from typing import Any

import pytest

from app.core import ai_clients


@pytest.fixture
def recording_clients(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, Any]]:
    recorded: dict[str, dict[str, Any]] = {}

    def record(name: str):
        def constructor(**kwargs: Any) -> object:
            recorded[name] = kwargs
            return object()

        return constructor

    monkeypatch.setattr(ai_clients, "ChatOpenAI", record("chat"))
    monkeypatch.setattr(ai_clients, "OpenAIEmbeddings", record("embeddings"))
    monkeypatch.setattr(ai_clients, "AsyncOpenAI", record("responses"))
    monkeypatch.setattr(
        ai_clients,
        "settings",
        SimpleNamespace(
            LLM_API_KEY_VALUE="deepseek-key",
            LLM_BASE_URL_VALUE="https://api.deepseek.com",
            LLM_ORGANIZATION=None,
            OPENAI_API_KEY="openai-key",
            OPENAI_BASE_URL="https://api.openai.com/v1",
            OPENAI_ORGANIZATION="openai-organization",
        ),
    )
    return recorded


def test_chat_model_uses_the_configured_llm_endpoint(
    recording_clients: dict[str, dict[str, Any]],
) -> None:
    ai_clients.create_chat_model(model="deepseek-chat", temperature=0)

    assert recording_clients["chat"] == {
        "api_key": "deepseek-key",
        "base_url": "https://api.deepseek.com",
        "organization": None,
        "model": "deepseek-chat",
        "temperature": 0,
    }


def test_embeddings_keep_the_openai_endpoint(
    recording_clients: dict[str, dict[str, Any]],
) -> None:
    ai_clients.create_embedding_model(model="text-embedding-3-small")

    assert recording_clients["embeddings"] == {
        "api_key": "openai-key",
        "base_url": "https://api.openai.com/v1",
        "organization": "openai-organization",
        "model": "text-embedding-3-small",
    }


def test_responses_client_keeps_the_openai_endpoint(
    recording_clients: dict[str, dict[str, Any]],
) -> None:
    ai_clients.create_responses_client()

    assert recording_clients["responses"] == {
        "api_key": "openai-key",
        "base_url": "https://api.openai.com/v1",
        "organization": "openai-organization",
    }
