import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from app.chat.intents import AgentRouteDecision
from app.chat.quota import ChatQuotaService, SqlChatQuotaRepository
from app.chat.repository import ConversationRepository
from app.chat.schemas import (
    AnswerEvidencePack,
    ChatReadiness,
    MessageCreate,
    ReadinessResource,
    ResearchAnswerPlan,
    StructuredContextPack,
)
from app.chat.service import (
    CompanyResearchChatService,
    MessageCommand,
    PreparedAnswerEvidence,
    RetryCommand,
)
from app.chat.web_trace import WebSearchTraceRecord
from app.core.errors import DomainError
from app.models.chat_model import (
    ChatQuotaLedger,
    ConversationMessage,
    MessageCitation,
    WebSearchTrace,
)
from app.models.company_model import Company
from app.quota.identity import RequestPrincipal

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)
GUEST = RequestPrincipal.guest("g" * 64, "i" * 64)
OTHER_GUEST = RequestPrincipal.guest("h" * 64, "j" * 64)
FIXTURES = Path(__file__).parents[1] / "fixtures" / "chat"


def load_evidence() -> AnswerEvidencePack:
    return AnswerEvidencePack.model_validate_json(
        (FIXTURES / "aapl_evidence.json").read_text()
    )


def load_answers() -> dict[str, dict]:
    return json.loads((FIXTURES / "aapl_answers.json").read_text())


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


@dataclass
class FakeContextProvider:
    result: StructuredContextPack = field(default_factory=ready_context)
    error: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def resolve(self, **kwargs: Any) -> StructuredContextPack:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


@dataclass
class FakeEvidencePipeline:
    pack: AnswerEvidencePack = field(default_factory=load_evidence)
    traces: list[WebSearchTraceRecord] = field(default_factory=list)
    internal_error: BaseException | None = None
    web_error: BaseException | None = None
    internal_calls: list[dict[str, Any]] = field(default_factory=list)
    web_calls: list[dict[str, Any]] = field(default_factory=list)

    async def prepare_internal(self, **kwargs: Any) -> object:
        self.internal_calls.append(kwargs)
        if self.internal_error is not None:
            raise self.internal_error
        return {"internal": True}

    async def add_web(self, **kwargs: Any) -> PreparedAnswerEvidence:
        self.web_calls.append(kwargs)
        if self.web_error is not None:
            raise self.web_error
        return PreparedAnswerEvidence(self.pack, web_traces=self.traces)


@dataclass
class FakeAnswerAgent:
    outputs: list[Any]
    model_id: str = "gpt-fixture"
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_plan(self, question: str, evidence, **kwargs: Any):
        self.calls.append({"question": question, "evidence": evidence, **kwargs})
        output = self.outputs.pop(0)
        if isinstance(output, BaseException):
            raise output
        return ResearchAnswerPlan.model_validate(output)


@dataclass
class FakeIntentRouter:
    decision: AgentRouteDecision | None = None
    model_id: str = "deepseek-fixture"
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def route(self, **kwargs: Any) -> AgentRouteDecision:
        self.calls.append(kwargs)
        return self.decision or AgentRouteDecision(
            interaction_mode="research",
            is_follow_up=False,
            resolved_question=kwargs["question"],
        )


@dataclass
class FakeSummarizer:
    result: str = "Earlier research summary."
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def summarize(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.result


@dataclass
class Harness:
    service: CompanyResearchChatService
    repository: ConversationRepository
    context: FakeContextProvider
    evidence: FakeEvidencePipeline
    router: FakeIntentRouter
    agent: FakeAnswerAgent
    summarizer: FakeSummarizer
    company: Company
    conversation_id: UUID


def harness(
    session: Session,
    *,
    outputs: list[Any] | None = None,
    context: FakeContextProvider | None = None,
    evidence: FakeEvidencePipeline | None = None,
    router: FakeIntentRouter | None = None,
) -> Harness:
    repository = ConversationRepository(session)
    conversation = repository.create_or_get_guest(
        company_id=1,
        principal=GUEST,
        locale="en-US",
        title="Apple research",
        now=NOW,
        retention_days=7,
    )
    session.commit()
    company = session.get(Company, 1)
    assert company is not None
    context = context or FakeContextProvider()
    evidence = evidence or FakeEvidencePipeline()
    router = router or FakeIntentRouter()
    agent = FakeAnswerAgent(outputs or [load_answers()["valid_en"]])
    summarizer = FakeSummarizer()
    service = CompanyResearchChatService(
        session,
        repository=repository,
        quota=ChatQuotaService(SqlChatQuotaRepository(session)),
        context_provider=context,
        evidence_pipeline=evidence,
        intent_router=router,
        answer_agent=agent,
        summarizer=summarizer,
        now=lambda: NOW,
    )
    return Harness(
        service,
        repository,
        context,
        evidence,
        router,
        agent,
        summarizer,
        company,
        conversation.id,
    )


def command(
    value: Harness,
    *,
    request_id: UUID | None = None,
    content: str = "Analyze Apple's revenue, margins, supply chain, and current risk.",
) -> MessageCommand:
    return MessageCommand(
        company=value.company,
        conversation_id=value.conversation_id,
        principal=GUEST,
        message=MessageCreate(
            client_request_id=request_id or uuid4(),
            content=content,
            locale="en-US",
            context=[],
        ),
    )


async def collect(stream) -> list:
    return [event async for event in stream]


@pytest.mark.asyncio
async def test_success_is_durable_before_first_section(
    chat_session: Session,
) -> None:
    value = harness(chat_session)
    events = []
    assistant_id = None

    async for event in value.service.stream_message(command(value)):
        events.append(event)
        if event.kind == "accepted":
            assistant_id = event.payload.assistant_message_id
        if event.kind == "section":
            assert assistant_id is not None
            stored = chat_session.get(ConversationMessage, assistant_id)
            assert stored is not None and stored.state == "completed"
            assert stored.answer_plan is not None
            assert value.repository.list_citations(assistant_id)

    assert [event.kind for event in events] == [
        "accepted",
        "stage",
        "stage",
        "stage",
        "stage",
        "stage",
        "section",
        "section",
        "section",
        "section",
        "citation",
        "citation",
        "citation",
        "citation",
        "complete",
    ]
    assert [event.payload.stage for event in events if event.kind == "stage"] == [
        "route",
        "retrieval",
        "web",
        "compose",
        "verify",
    ]
    ledger = chat_session.exec(select(ChatQuotaLedger)).one()
    assert ledger.state == "consumed"
    assert [
        row.ordinal for row in chat_session.exec(select(MessageCitation)).all()
    ] == [
        0,
        1,
        2,
        3,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["conversation", "clarification"])
async def test_non_research_route_skips_evidence_and_persists_plain_response(
    chat_session: Session,
    mode: str,
) -> None:
    response = (
        "你好，我可以帮你研究这家公司的业务、产业链、财报和估值。"
        if mode == "conversation"
        else "你想先研究这家公司的业务、产业链、财报还是估值？"
    )
    router = FakeIntentRouter(
        AgentRouteDecision(
            interaction_mode=mode,
            is_follow_up=False,
            response=response,
        )
    )
    value = harness(chat_session, router=router)
    request_id = uuid4()

    events = await collect(
        value.service.stream_message(
            command(value, request_id=request_id, content="你好")
        )
    )
    replay = await collect(
        value.service.stream_message(
            command(value, request_id=request_id, content="你好")
        )
    )

    assert [event.kind for event in events] == ["accepted", "stage", "complete"]
    assert events[1].payload.stage == "route"
    completed = events[-1].payload
    assert completed.message.response_kind == mode
    assert completed.message.content == response
    assert completed.evidence_coverage is None
    assert completed.citations == []
    assert value.evidence.internal_calls == []
    assert value.evidence.web_calls == []
    assert value.agent.calls == []
    assert [event.kind for event in replay] == ["accepted", "complete"]
    assert replay[-1].payload.message.response_kind == mode
    assert len(value.router.calls) == 1
    assert chat_session.exec(select(ChatQuotaLedger)).one().state == "consumed"


@pytest.mark.asyncio
async def test_research_follow_up_uses_model_resolved_question(
    chat_session: Session,
) -> None:
    resolved = "What is Apple Inc.'s current trailing P/E ratio?"
    router = FakeIntentRouter(
        AgentRouteDecision(
            interaction_mode="research",
            is_follow_up=True,
            analysis_skills=["company-valuation"],
            resolved_question=resolved,
        )
    )
    value = harness(chat_session, router=router)

    events = await collect(
        value.service.stream_message(command(value, content="What about its P/E?"))
    )

    assert events[-1].kind == "complete"
    assert value.evidence.internal_calls[0]["question"] == resolved
    assert value.evidence.internal_calls[0]["analysis_skills"] == ["company-valuation"]
    assert value.evidence.web_calls[0]["question"] == resolved
    assert value.agent.calls[0]["question"] == resolved
    assert value.agent.calls[0]["analysis_skills"] == ["company-valuation"]
    stored = chat_session.get(
        ConversationMessage,
        events[-1].payload.message.id,
    )
    assert stored is not None
    assert stored.answer_plan["is_follow_up"] is True
    assert stored.answer_plan["resolved_question"] == resolved


@pytest.mark.asyncio
async def test_authorization_and_context_validation_precede_quota(
    chat_session: Session,
) -> None:
    value = harness(chat_session)
    unauthorized = command(value)
    unauthorized = MessageCommand(
        company=unauthorized.company,
        conversation_id=unauthorized.conversation_id,
        principal=OTHER_GUEST,
        message=unauthorized.message,
    )

    with pytest.raises(DomainError, match="CHAT_CONVERSATION_NOT_FOUND"):
        await collect(value.service.stream_message(unauthorized))
    assert value.context.calls == []
    assert chat_session.exec(select(ChatQuotaLedger)).all() == []

    value.context.error = DomainError("CHAT_CONTEXT_INVALID", 422)
    with pytest.raises(DomainError, match="CHAT_CONTEXT_INVALID"):
        await collect(value.service.stream_message(command(value)))
    assert chat_session.exec(select(ChatQuotaLedger)).all() == []


@pytest.mark.asyncio
async def test_replayed_request_uses_durable_records_without_new_quota(
    chat_session: Session,
) -> None:
    value = harness(chat_session)
    request_id = uuid4()
    first = await collect(
        value.service.stream_message(command(value, request_id=request_id))
    )
    assistant = chat_session.get(
        ConversationMessage,
        first[-1].payload.message.id,
    )
    assert assistant is not None and assistant.answer_plan is not None
    assistant.answer_plan = assistant.answer_plan["answer"]
    chat_session.add(assistant)
    chat_session.commit()

    replay = await collect(
        value.service.stream_message(command(value, request_id=request_id))
    )

    assert first[-1].kind == replay[-1].kind == "complete"
    assert replay[-1].payload.message.response_kind == "research"
    assert [event.kind for event in replay].count("section") == 4
    assert len(value.evidence.internal_calls) == 1
    assert len(value.agent.calls) == 1
    assert len(chat_session.exec(select(ChatQuotaLedger)).all()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_stage", "error", "expected_code"),
    [
        ("retrieval", RuntimeError("retrieval secret"), "CHAT_RETRIEVAL_FAILED"),
        (
            "web",
            DomainError("CHAT_WEB_SEARCH_FAILED", 503, {"retryable": True}),
            "CHAT_WEB_SEARCH_FAILED",
        ),
        (
            "compose",
            DomainError("CHAT_ANSWER_GENERATION_FAILED", 503, {"retryable": True}),
            "CHAT_ANSWER_GENERATION_FAILED",
        ),
    ],
)
async def test_pre_persistence_failures_refund_quota(
    chat_session: Session,
    failure_stage: str,
    error: Exception,
    expected_code: str,
) -> None:
    evidence = FakeEvidencePipeline(
        internal_error=error if failure_stage == "retrieval" else None,
        web_error=error if failure_stage == "web" else None,
    )
    outputs = [error] if failure_stage == "compose" else None
    value = harness(chat_session, evidence=evidence, outputs=outputs)

    events = await collect(value.service.stream_message(command(value)))

    assert events[-1].kind == "error"
    assert events[-1].payload.code == expected_code
    ledger = chat_session.exec(select(ChatQuotaLedger)).one()
    assistant = chat_session.get(ConversationMessage, ledger.assistant_message_id)
    assert ledger.state == "refunded"
    assert assistant is not None and assistant.state == "failed"
    assert assistant.error_code == expected_code


@pytest.mark.asyncio
async def test_unknown_citation_is_filtered_and_answer_completes(
    chat_session: Session,
) -> None:
    value = harness(
        chat_session,
        outputs=[load_answers()["invalid_citation"]],
    )

    events = await collect(value.service.stream_message(command(value)))

    assert events[-1].kind == "complete"
    assert [citation.title for citation in events[-1].payload.citations] == [
        "Apple Supplier Responsibility"
    ]
    assert chat_session.exec(select(ChatQuotaLedger)).one().state == "consumed"


@pytest.mark.asyncio
async def test_cancellation_marks_failed_and_refunds_before_durability(
    chat_session: Session,
) -> None:
    evidence = FakeEvidencePipeline(internal_error=asyncio.CancelledError())
    value = harness(chat_session, evidence=evidence)

    with pytest.raises(asyncio.CancelledError):
        await collect(value.service.stream_message(command(value)))

    ledger = chat_session.exec(select(ChatQuotaLedger)).one()
    assistant = chat_session.get(ConversationMessage, ledger.assistant_message_id)
    assert ledger.state == "refunded"
    assert assistant is not None and assistant.error_code == "CHAT_STREAM_CANCELLED"


@pytest.mark.asyncio
async def test_disconnect_after_accepted_refunds_reserved_attempt(
    chat_session: Session,
) -> None:
    value = harness(chat_session)
    stream = value.service.stream_message(command(value))

    accepted = await anext(stream)
    await stream.aclose()

    assert accepted.kind == "accepted"
    ledger = chat_session.exec(select(ChatQuotaLedger)).one()
    assistant = chat_session.get(ConversationMessage, ledger.assistant_message_id)
    assert ledger.state == "refunded"
    assert assistant is not None and assistant.error_code == "CHAT_STREAM_CANCELLED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("coverage", "answer_name"),
    [
        ("complete", "valid_en"),
        ("partial", "partial"),
        ("insufficient", "insufficient"),
    ],
)
async def test_every_terminal_coverage_consumes_one_unit(
    chat_session: Session,
    coverage: str,
    answer_name: str,
) -> None:
    evidence = load_evidence()
    if coverage != "complete":
        evidence = evidence.model_copy(
            update={"evidence_gaps": ["FILING_INDEX_MISSING"]}
        )
    value = harness(
        chat_session,
        outputs=[load_answers()[answer_name]],
        evidence=FakeEvidencePipeline(pack=evidence),
    )

    events = await collect(value.service.stream_message(command(value)))

    assert events[-1].payload.evidence_coverage == coverage
    assert chat_session.exec(select(ChatQuotaLedger)).one().state == "consumed"


@pytest.mark.asyncio
async def test_web_trace_is_persisted_with_completed_answer(
    chat_session: Session,
) -> None:
    trace = WebSearchTraceRecord(
        normalized_query="Apple current regulatory risk",
        search_decision="required_current",
        search_reason="required_current",
        candidate_results=[],
        selected_result_ids=["result-1"],
        artifact_key="chat-web/aapl/page.json.gz",
        artifact_sha256="a" * 64,
        provider_request_id="request-1",
        duration_ms=15,
        tool_ordinal=0,
    )
    value = harness(
        chat_session,
        evidence=FakeEvidencePipeline(traces=[trace]),
    )

    await collect(value.service.stream_message(command(value)))

    stored = chat_session.exec(select(WebSearchTrace)).one()
    assert stored.artifact_key == trace.artifact_key
    assert stored.artifact_sha256 == trace.artifact_sha256


@pytest.mark.asyncio
async def test_refunded_attempt_retries_once_and_replay_is_idempotent(
    chat_session: Session,
) -> None:
    failure = DomainError(
        "CHAT_ANSWER_GENERATION_FAILED",
        503,
        {"retryable": True},
    )
    value = harness(
        chat_session,
        outputs=[failure, load_answers()["valid_en"]],
    )
    failed_events = await collect(value.service.stream_message(command(value)))
    failed_id = failed_events[-1].payload.assistant_message_id
    retry_id = uuid4()
    retry = RetryCommand(
        conversation_id=value.conversation_id,
        assistant_message_id=failed_id,
        client_request_id=retry_id,
        principal=GUEST,
    )

    completed = await collect(value.service.stream_retry(retry))
    replay = await collect(value.service.stream_retry(retry))

    assert completed[-1].kind == replay[-1].kind == "complete"
    assistant = chat_session.get(ConversationMessage, failed_id)
    assert assistant is not None and assistant.attempt_count == 1
    assert assistant.state == "completed"
    assert len(value.agent.calls) == 2
    ledgers = chat_session.exec(select(ChatQuotaLedger)).all()
    assert sorted(row.state for row in ledgers) == ["consumed", "refunded"]
    assert value.service.quota_status(GUEST).used == 1


@pytest.mark.asyncio
async def test_completed_message_rejects_fresh_retry_request(
    chat_session: Session,
) -> None:
    value = harness(chat_session)
    completed = await collect(value.service.stream_message(command(value)))
    assistant_id = completed[-1].payload.message.id

    with pytest.raises(DomainError, match="CHAT_MESSAGE_RETRY_INVALID"):
        await collect(
            value.service.stream_retry(
                RetryCommand(
                    conversation_id=value.conversation_id,
                    assistant_message_id=assistant_id,
                    client_request_id=uuid4(),
                    principal=GUEST,
                )
            )
        )

    assert len(chat_session.exec(select(ChatQuotaLedger)).all()) == 1


@pytest.mark.asyncio
async def test_summary_checkpoint_keeps_latest_eight_messages(
    chat_session: Session,
) -> None:
    value = harness(chat_session)
    for index in range(9):
        value.repository.add_user_message(
            conversation_id=value.conversation_id,
            request_id=uuid4(),
            content=f"Old question {index}",
            locale="en-US",
            context_selection=[],
            created_at=NOW - timedelta(minutes=20 - index),
        )
    chat_session.commit()

    await collect(value.service.stream_message(command(value)))

    conversation = value.repository.get_owned(
        value.conversation_id,
        GUEST,
        now=NOW,
    )
    assert conversation is not None
    assert conversation.summary == "Earlier research summary."
    assert conversation.summary_through_message_id is not None
    assert len(value.summarizer.calls) == 1
    internal_call = value.evidence.internal_calls[0]
    assert internal_call["summary"] == "Earlier research summary."
    assert len(internal_call["history"]) <= 8
