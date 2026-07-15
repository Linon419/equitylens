import json
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.api.deps import (
    get_agent_principal,
    get_chat_answer_agent,
    get_chat_context_provider,
    get_chat_evidence_pipeline,
    get_chat_intent_router,
    get_db,
    get_sec_data_provider,
)
from app.chat.intents import AgentRouteDecision
from app.chat.schemas import (
    AnswerEvidencePack,
    ChatReadiness,
    ReadinessResource,
    ResearchAnswerPlan,
    StructuredContextPack,
)
from app.chat.service import PreparedAnswerEvidence
from app.core.errors import DomainError
from app.main import create_app
from app.models.chat_model import ChatQuotaLedger, ConversationMessage, MessageCitation
from app.models.company_model import Company
from app.quota.identity import RequestPrincipal

FIXTURES = Path(__file__).parents[1] / "fixtures" / "chat"


@dataclass
class JourneyHarness:
    client: TestClient
    engine: object
    agent: "JourneyAnswerAgent"


@dataclass
class JourneyContextProvider:
    context: StructuredContextPack

    async def resolve(self, **_kwargs) -> StructuredContextPack:
        return self.context


@dataclass
class JourneyEvidencePipeline:
    async def prepare_internal(self, **kwargs):
        return kwargs["question"]

    async def add_web(self, **kwargs) -> PreparedAnswerEvidence:
        question = kwargs["question"].casefold()
        evidence = AnswerEvidencePack.model_validate_json(
            (FIXTURES / "aapl_evidence.json").read_text()
        )
        use_web = any(term in question for term in ("current", "recent", "latest"))
        if use_web:
            return PreparedAnswerEvidence(evidence, [])
        return PreparedAnswerEvidence(
            evidence.model_copy(
                update={
                    "records": [
                        record
                        for record in evidence.records
                        if record.candidate.source_kind != "web"
                    ],
                    "web_search_used": False,
                }
            ),
            [],
        )


@dataclass
class JourneyIntentRouter:
    model_id: str = "deterministic-journey-router"

    async def route(self, **kwargs) -> AgentRouteDecision:
        return AgentRouteDecision(
            interaction_mode="research",
            is_follow_up=bool(kwargs["history"]),
            resolved_question=kwargs["question"],
        )


@dataclass
class JourneyAnswerAgent:
    model_id: str = "deterministic-journey-agent"
    failed_once: set[str] = field(default_factory=set)

    async def create_plan(
        self,
        question: str,
        evidence: AnswerEvidencePack,
        **kwargs,
    ) -> ResearchAnswerPlan:
        if (
            "force model failure" in question.casefold()
            and question not in self.failed_once
        ):
            self.failed_once.add(question)
            raise DomainError("CHAT_ANSWER_GENERATION_FAILED", 503)
        answers = json.loads((FIXTURES / "aapl_answers.json").read_text())
        answer = answers["valid_zh" if kwargs["locale"] == "zh-CN" else "valid_en"]
        if not evidence.web_search_used:
            answer["risks_and_uncertainties"] = []
            answer["sources"] = [
                source for source in answer["sources"] if not source.startswith("web:")
            ]
            answer["web_search_used"] = False
        return ResearchAnswerPlan.model_validate(answer)


@pytest.fixture
def journey() -> Generator[JourneyHarness, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_foreign_keys)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Company(
                id=1,
                symbol="AAPL",
                cik="0000320193",
                name="Apple Inc.",
                exchange="Nasdaq",
            )
        )
        session.commit()

    context = JourneyContextProvider(ready_context())
    evidence = JourneyEvidencePipeline()
    intent_router = JourneyIntentRouter()
    answer_agent = JourneyAnswerAgent()
    application = create_app()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    def override_principal(request: Request) -> RequestPrincipal:
        identity = request.headers.get("x-journey-principal", "primary")
        return RequestPrincipal.guest(identity.ljust(64, "0")[:64], "i" * 64)

    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_agent_principal] = override_principal
    application.dependency_overrides[get_sec_data_provider] = lambda: object()
    application.dependency_overrides[get_chat_context_provider] = lambda: context
    application.dependency_overrides[get_chat_evidence_pipeline] = lambda: evidence
    application.dependency_overrides[get_chat_intent_router] = lambda: intent_router
    application.dependency_overrides[get_chat_answer_agent] = lambda: answer_agent
    with TestClient(application) as client:
        yield JourneyHarness(client, engine, answer_agent)


def test_completed_replay_and_quota_journey(journey: JourneyHarness) -> None:
    conversation_id = create_conversation(journey.client)
    request_id = uuid4()
    first = send_message(
        journey.client, conversation_id, request_id, "Analyze FY2025 revenue"
    )
    replay = send_message(
        journey.client, conversation_id, request_id, "Analyze FY2025 revenue"
    )
    second = send_message(
        journey.client,
        conversation_id,
        uuid4(),
        "What is Apple's current regulatory risk?",
    )
    blocked = journey.client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json=message_body(uuid4(), "One more question"),
    )
    foreign = journey.client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={"x-journey-principal": "foreign"},
    )

    assert [name for name in event_names(first) if name != "stage"] == event_names(
        replay
    )
    assert terminal(first)["message"]["id"] == terminal(replay)["message"]["id"]
    assert terminal(first)["quota"]["used"] == 1
    assert terminal(second)["quota"]["used"] == 2
    assert any(item["source_kind"] == "web" for item in terminal(second)["citations"])
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "CHAT_DAILY_QUOTA_EXCEEDED"
    assert foreign.status_code == 404

    with Session(journey.engine) as session:
        ledgers = session.exec(select(ChatQuotaLedger)).all()
        citations = session.exec(select(MessageCitation)).all()
        assert [ledger.state for ledger in ledgers] == ["consumed", "consumed"]
        assert len(citations) == 7
        assert all(citation.source_url.startswith("https://") for citation in citations)


def test_failure_refund_retry_and_immutable_citations(journey: JourneyHarness) -> None:
    headers = {"x-journey-principal": "retry-principal"}
    conversation_id = create_conversation(journey.client, headers=headers)
    failed = send_message(
        journey.client,
        conversation_id,
        uuid4(),
        "Force model failure while analyzing FY2025 revenue",
        headers=headers,
    )
    failed_terminal = terminal(failed, kind="error")
    assistant_id = failed_terminal["assistant_message_id"]
    retried = journey.client.post(
        f"/api/v1/conversations/{conversation_id}/messages/{assistant_id}/retry",
        headers=headers,
        json={"client_request_id": str(uuid4())},
    )
    retry_events = parse_sse(retried.text)
    before = terminal(retry_events)["citations"]
    replayed = journey.client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
    ).json()["items"]

    assert failed_terminal["code"] == "CHAT_ANSWER_GENERATION_FAILED"
    assert retried.status_code == 200
    assert terminal(retry_events)["quota"]["used"] == 1
    assert replayed[-1]["citations"] == before
    with Session(journey.engine) as session:
        ledgers = session.exec(select(ChatQuotaLedger)).all()
        assistant = session.get(ConversationMessage, UUID(assistant_id))
        assert sorted(ledger.state for ledger in ledgers) == ["consumed", "refunded"]
        assert assistant is not None and assistant.attempt_count == 1
        assert assistant.state == "completed"


def ready_context() -> StructuredContextPack:
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


def enable_foreign_keys(connection, _record) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_conversation(client: TestClient, *, headers: dict | None = None) -> str:
    response = client.post(
        "/api/v1/companies/AAPL/conversations",
        headers=headers,
        json={"locale": "en-US"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def message_body(request_id, content: str) -> dict:
    return {
        "client_request_id": str(request_id),
        "content": content,
        "locale": "en-US",
        "context": [],
    }


def send_message(
    client,
    conversation_id,
    request_id,
    content,
    *,
    headers=None,
) -> list[dict]:
    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json=message_body(request_id, content),
    )
    assert response.status_code == 200
    return parse_sse(response.text)


def parse_sse(value: str) -> list[dict]:
    events = []
    for block in value.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in lines:
            events.append(
                {"kind": lines["event"], "payload": json.loads(lines["data"])}
            )
    return events


def event_names(events: list[dict]) -> list[str]:
    return [event["kind"] for event in events]


def terminal(events: list[dict], *, kind: str = "complete") -> dict:
    return next(event["payload"] for event in reversed(events) if event["kind"] == kind)
