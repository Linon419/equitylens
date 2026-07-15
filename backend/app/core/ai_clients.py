from typing import Any

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import AsyncOpenAI

from app.core.config import settings


def create_chat_model(**kwargs: Any) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.LLM_API_KEY_VALUE,
        base_url=settings.LLM_BASE_URL_VALUE,
        organization=settings.LLM_ORGANIZATION,
        **kwargs,
    )


def create_embedding_model(**kwargs: Any) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        organization=settings.OPENAI_ORGANIZATION,
        **kwargs,
    )


def create_responses_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        organization=settings.OPENAI_ORGANIZATION,
    )
