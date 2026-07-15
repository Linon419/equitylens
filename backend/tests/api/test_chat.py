from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import (
    get_agent_principal,
    get_chat_context_provider,
    get_chat_service,
    get_db,
    get_job_backend,
    get_sec_data_provider,
)
from app.chat.repository import ConversationRepository
from app.chat.schemas import (
    AcceptedEvent,
    ChatQuotaStatus,
    ChatReadiness,
    ReadinessResource,
    StructuredContextPack,
)
from app.chat.sse import ChatStreamEvent
from app.core.errors import DomainError
from app.jobs.schemas import JobSubmission
from app.main import create_app
from app.models.company_model import Company
from app.models.research_model import Filing, FilingSection
from app.models.user_model import User
from app.quota.identity import RequestPrincipal

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)
GUEST = RequestPrincipal.guest("g" * 64, "i" * 64)
OTHER_GUEST = RequestPrincipal.guest("h" * 64, "j" * 64)
USER = RequestPrincipal.user(7, "q" * 32)


def quota() -> ChatQuotaStatus:
    return ChatQuotaStatus(
        limit=2,
        used=1,
        remaining=1,
        resets_at=NOW + timedelta(hours=12),
    )


def context_pack() -> StructuredContextPack:
    ready = ReadinessResource(state="ready", action=None)
    return StructuredContextPack(
        items=[],
        evidence=[],
        readiness=ChatReadiness(
            company_symbol="AAPL",
            intelligence=ready,
            filing_text=ready,
            filing_index=ready,
            supply_chain_graph=ready,
            web_recency=ready,
        ),
        gaps=[],
    )


@dataclass
class FakeContextProvider:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def resolve(self, **kwargs: Any) -> StructuredContextPack:
        self.calls.append(kwargs)
        return context_pack()


@dataclass
class FakeChatService:
    messages: list[Any] = field(default_factory=list)
    retries: list[Any] = field(default_factory=list)

    def quota_status(self, principal: RequestPrincipal) -> ChatQuotaStatus:
        return quota()

    async def stream_message(self, command):
        self.messages.append(command)
        if command.message.content == "quota exceeded":
            raise DomainError("CHAT_DAILY_QUOTA_EXCEEDED", 429)
        if command.message.context:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        yield ChatStreamEvent(
            "accepted",
            AcceptedEvent(
                user_message_id=uuid4(),
                assistant_message_id=uuid4(),
                conversation_id=command.conversation_id,
                quota=quota(),
            ),
        )

    async def stream_retry(self, command):
        self.retries.append(command)
        yield ChatStreamEvent(
            "accepted",
            AcceptedEvent(
                user_message_id=uuid4(),
                assistant_message_id=command.assistant_message_id,
                conversation_id=command.conversation_id,
                quota=quota(),
            ),
        )


@dataclass
class FakeJobBackend:
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def enqueue(self, *, job_type: str, payload: dict) -> JobSubmission:
        self.calls.append({"job_type": job_type, "payload": payload})
        return JobSubmission(job_id=f"workflow:{payload['job_id']}")


class FakeSecProvider:
    async def resolve_company(self, symbol: str):
        raise AssertionError(f"unexpected company lookup: {symbol}")


@dataclass
class ChatApiHarness:
    client: TestClient
    engine: Any
    chat: FakeChatService
    context: FakeContextProvider
    jobs: FakeJobBackend


@pytest.fixture
def chat_api() -> Generator[ChatApiHarness, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        company = Company(
            id=1,
            symbol="AAPL",
            cik="0000320193",
            name="Apple Inc.",
        )
        filing = Filing(
            company_id=1,
            accession_number="0000320193-25-000079",
            form="10-K",
            fiscal_period="FY2025",
            filed_at=date(2025, 10, 31),
            report_date=date(2025, 9, 27),
            primary_document="aapl-20250927.htm",
            source_url="https://www.sec.gov/Archives/aapl-20250927.htm",
            retrieved_at=NOW,
        )
        session.add_all(
            [
                company,
                User(id=7, email="investor@example.com"),
                filing,
            ]
        )
        session.flush()
        session.add(
            FilingSection(
                filing_id=filing.id,
                heading="Item 8",
                source_anchor="item-8",
                ordinal=0,
                text="Apple financial statements.",
            )
        )
        session.commit()

    chat = FakeChatService()
    context = FakeContextProvider()
    jobs = FakeJobBackend()
    app = create_app()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def override_principal(
        x_test_user_id: Annotated[int | None, Header()] = None,
        x_test_guest: Annotated[str | None, Header()] = None,
    ) -> RequestPrincipal:
        if x_test_user_id is not None:
            return RequestPrincipal.user(x_test_user_id, "q" * 32)
        return OTHER_GUEST if x_test_guest == "other" else GUEST

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_agent_principal] = override_principal
    app.dependency_overrides[get_sec_data_provider] = lambda: FakeSecProvider()
    app.dependency_overrides[get_chat_service] = lambda: chat
    app.dependency_overrides[get_chat_context_provider] = lambda: context
    app.dependency_overrides[get_job_backend] = lambda: jobs
    with TestClient(app) as client:
        yield ChatApiHarness(client, engine, chat, context, jobs)


def create_conversation(
    chat_api: ChatApiHarness,
    *,
    headers: dict[str, str] | None = None,
    locale: str = "en-US",
    title: str | None = None,
) -> dict:
    body: dict[str, Any] = {"locale": locale}
    if title is not None:
        body["title"] = title
    response = chat_api.client.post(
        "/api/v1/companies/AAPL/conversations",
        headers=headers,
        json=body,
    )
    assert response.status_code == 201
    return response.json()


def test_guest_create_reuses_singleton_and_preserves_locale(chat_api) -> None:
    first = create_conversation(chat_api, locale="en-US")
    second = create_conversation(chat_api, locale="zh-CN")
    listed = chat_api.client.get("/api/v1/companies/AAPL/conversations")

    assert first["id"] == second["id"]
    assert second["locale"] == "en-US"
    assert [item["id"] for item in listed.json()] == [first["id"]]


def test_user_can_create_rename_archive_and_reload_multiple(chat_api) -> None:
    headers = {"x-test-user-id": "7"}
    first = create_conversation(chat_api, headers=headers, title="Margins")
    second = create_conversation(chat_api, headers=headers, title="Supply chain")

    renamed = chat_api.client.patch(
        f"/api/v1/conversations/{first['id']}",
        headers=headers,
        json={"title": "Gross margins"},
    )
    archived = chat_api.client.delete(
        f"/api/v1/conversations/{first['id']}",
        headers=headers,
    )
    missing = chat_api.client.get(
        f"/api/v1/conversations/{first['id']}",
        headers=headers,
    )
    listed = chat_api.client.get(
        "/api/v1/companies/AAPL/conversations",
        headers=headers,
    )

    assert first["id"] != second["id"]
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Gross margins"
    assert archived.status_code == 204
    assert missing.status_code == 404
    assert [item["id"] for item in listed.json()] == [second["id"]]


def test_guest_rename_policy_and_ownership_use_stable_errors(chat_api) -> None:
    conversation = create_conversation(chat_api)
    renamed = chat_api.client.patch(
        f"/api/v1/conversations/{conversation['id']}",
        json={"title": "Guest rename"},
    )
    foreign = chat_api.client.get(
        f"/api/v1/conversations/{conversation['id']}",
        headers={"x-test-guest": "other"},
    )

    assert renamed.status_code == 403
    assert renamed.json()["code"] == "CHAT_CONVERSATION_RENAME_FORBIDDEN"
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "CHAT_CONVERSATION_NOT_FOUND"


def test_readiness_and_zero_quota_index_sync(chat_api) -> None:
    readiness = chat_api.client.get(
        "/api/v1/companies/AAPL/chat-readiness?locale=zh-CN"
    )
    indexed = chat_api.client.post("/api/v1/companies/AAPL/chat-index/sync")

    assert readiness.status_code == 200
    assert readiness.json()["company_symbol"] == "AAPL"
    assert chat_api.context.calls[0]["locale"] == "zh-CN"
    assert indexed.status_code == 202
    assert indexed.json()["status"] == "accepted"
    assert chat_api.jobs.calls[0]["job_type"] == "filing_index"


def test_message_history_is_cursor_paginated_and_keeps_locale(chat_api) -> None:
    headers = {"x-test-user-id": "7"}
    conversation = create_conversation(chat_api, headers=headers)
    with Session(chat_api.engine) as session:
        repository = ConversationRepository(session)
        for index, locale in enumerate(("en-US", "zh-CN", "en-US")):
            repository.add_user_message(
                conversation_id=UUID(conversation["id"]),
                request_id=uuid4(),
                content=f"Question {index}",
                locale=locale,
                context_selection=[],
                created_at=NOW + timedelta(seconds=index),
            )
        session.commit()

    first = chat_api.client.get(
        f"/api/v1/conversations/{conversation['id']}/messages?limit=2",
        headers=headers,
    )
    second = chat_api.client.get(
        f"/api/v1/conversations/{conversation['id']}/messages",
        headers=headers,
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )

    assert [item["locale"] for item in first.json()["items"]] == [
        "en-US",
        "zh-CN",
    ]
    assert [item["content"] for item in second.json()["items"]] == ["Question 2"]
    assert second.json()["next_cursor"] is None


def test_message_stream_prefetches_errors_and_sets_sse_headers(chat_api) -> None:
    conversation = create_conversation(chat_api)
    path = f"/api/v1/conversations/{conversation['id']}/messages"
    request_id = str(uuid4())
    streamed = chat_api.client.post(
        path,
        json={
            "client_request_id": request_id,
            "content": "Analyze Apple",
            "locale": "en-US",
            "context": [],
        },
    )
    quota_error = chat_api.client.post(
        path,
        json={
            "client_request_id": str(uuid4()),
            "content": "quota exceeded",
            "locale": "en-US",
            "context": [],
        },
    )
    context_error = chat_api.client.post(
        path,
        json={
            "client_request_id": str(uuid4()),
            "content": "Analyze selected claim",
            "locale": "en-US",
            "context": [
                {
                    "kind": "business_claim",
                    "id": "claim-1",
                    "snapshot_id": str(uuid4()),
                }
            ],
        },
    )

    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert streamed.headers["cache-control"] == "no-cache, no-transform"
    assert streamed.headers["x-accel-buffering"] == "no"
    assert "event: accepted" in streamed.text
    assert quota_error.status_code == 429
    assert quota_error.json()["code"] == "CHAT_DAILY_QUOTA_EXCEEDED"
    assert context_error.status_code == 422
    assert context_error.json()["code"] == "CHAT_CONTEXT_INVALID"


def test_retry_and_quota_routes_use_current_principal(chat_api) -> None:
    conversation = create_conversation(chat_api)
    assistant_id = uuid4()
    retried = chat_api.client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/{assistant_id}/retry",
        json={"client_request_id": str(uuid4())},
    )
    foreign = chat_api.client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/{assistant_id}/retry",
        headers={"x-test-guest": "other"},
        json={"client_request_id": str(uuid4())},
    )
    current_quota = chat_api.client.get("/api/v1/chat-quota")

    assert retried.status_code == 200
    assert "event: accepted" in retried.text
    assert foreign.status_code == 404
    assert chat_api.chat.retries[0].assistant_message_id == assistant_id
    assert current_quota.status_code == 200
    assert current_quota.json()["remaining"] == 2
