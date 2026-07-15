import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import TypeAdapter, ValidationError
from sqlmodel import Session

from app.chat.answer_schemas import stored_response_kind
from app.chat.intents import AgentRouteDecision
from app.chat.quota import ChatQuotaLease, ChatQuotaService
from app.chat.repository import ConversationRepository
from app.chat.schemas import (
    AcceptedEvent,
    AnswerEvidencePack,
    CitationPublic,
    CompleteEvent,
    ContextSelection,
    ErrorEvent,
    MessageCreate,
    MessagePublic,
    ResearchAnswerPlan,
    SectionEvent,
    StageEvent,
    StoredAgentAnswer,
    StoredPlainAnswer,
    StoredResearchAnswer,
    StructuredContextPack,
)
from app.chat.sse import ChatStreamEvent
from app.chat.validator import validate_answer_plan
from app.chat.web_trace import WebSearchTraceRecord
from app.core.errors import DomainError
from app.models.chat_model import (
    CompanyConversation,
    ConversationMessage,
)
from app.models.company_model import Company
from app.quota.identity import RequestPrincipal

_CONTEXT_LIST = TypeAdapter(list[ContextSelection])
_STORED_ANSWER = TypeAdapter(StoredAgentAnswer)
_RETRYABLE_CODES = {
    "CHAT_INTENT_ROUTING_FAILED",
    "CHAT_RETRIEVAL_FAILED",
    "CHAT_WEB_SEARCH_FAILED",
    "CHAT_ANSWER_GENERATION_FAILED",
    "CHAT_ANSWER_VERIFICATION_FAILED",
    "CHAT_STREAM_CANCELLED",
}
_STAGE_CODES = {
    "route": "CHAT_INTENT_ROUTING_FAILED",
    "retrieval": "CHAT_RETRIEVAL_FAILED",
    "web": "CHAT_WEB_SEARCH_FAILED",
    "compose": "CHAT_ANSWER_GENERATION_FAILED",
    "verify": "CHAT_ANSWER_VERIFICATION_FAILED",
}


@dataclass(frozen=True, slots=True)
class MessageCommand:
    company: Company
    conversation_id: UUID
    principal: RequestPrincipal
    message: MessageCreate


@dataclass(frozen=True, slots=True)
class RetryCommand:
    conversation_id: UUID
    assistant_message_id: UUID
    client_request_id: UUID
    principal: RequestPrincipal


@dataclass(frozen=True, slots=True)
class PreparedAnswerEvidence:
    evidence: AnswerEvidencePack
    web_traces: list[WebSearchTraceRecord]


class ContextProvider(Protocol):
    async def resolve(self, **kwargs: Any) -> StructuredContextPack: ...


class EvidencePipeline(Protocol):
    async def prepare_internal(self, **kwargs: Any) -> object: ...

    async def add_web(self, **kwargs: Any) -> PreparedAnswerEvidence: ...


class AnswerAgent(Protocol):
    model_id: str

    async def create_plan(
        self,
        question: str,
        evidence: AnswerEvidencePack,
        **kwargs: Any,
    ) -> ResearchAnswerPlan: ...


class IntentRouter(Protocol):
    model_id: str

    async def route(self, **kwargs: Any) -> AgentRouteDecision: ...


class ConversationSummarizer(Protocol):
    async def summarize(self, **kwargs: Any) -> str: ...


class CompanyResearchChatService:
    def __init__(
        self,
        session: Session,
        *,
        repository: ConversationRepository,
        quota: ChatQuotaService,
        context_provider: ContextProvider,
        evidence_pipeline: EvidencePipeline,
        intent_router: IntentRouter,
        answer_agent: AnswerAgent,
        summarizer: ConversationSummarizer,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._session = session
        self._repository = repository
        self._quota = quota
        self._context_provider = context_provider
        self._evidence_pipeline = evidence_pipeline
        self._intent_router = intent_router
        self._answer_agent = answer_agent
        self._summarizer = summarizer
        self._now = now or (lambda: datetime.now(UTC))

    def quota_status(self, principal: RequestPrincipal):
        return self._quota.status(principal, now=self._now())

    async def stream_message(
        self,
        command: MessageCommand,
    ) -> AsyncIterator[ChatStreamEvent]:
        conversation = self._owned_conversation(
            command.conversation_id,
            command.principal,
            company_id=command.company.id,
        )
        structured = await self._context_provider.resolve(
            company=command.company,
            selections=command.message.context,
            locale=command.message.locale,
        )
        replay = self._repository.message_by_request(
            conversation.id,
            command.message.client_request_id,
        )
        if replay is not None:
            assistant = self._repository.assistant_for_user(replay.id)
            if assistant is None:
                raise DomainError("CHAT_REQUEST_CONFLICT", 409)
            async for event in self._replay(
                conversation,
                replay,
                assistant,
                command.principal,
            ):
                yield event
            return

        lease = self._quota.reserve(
            command.message.client_request_id,
            command.principal,
            conversation.id,
            now=self._now(),
        )
        replay = self._repository.message_by_request(
            conversation.id,
            command.message.client_request_id,
        )
        if replay is not None:
            assistant = self._repository.assistant_for_user(replay.id)
            self._session.rollback()
            if assistant is None:
                raise DomainError("CHAT_REQUEST_CONFLICT", 409)
            async for event in self._replay(
                conversation,
                replay,
                assistant,
                command.principal,
            ):
                yield event
            return
        try:
            user_message = self._repository.add_user_message(
                conversation_id=conversation.id,
                request_id=command.message.client_request_id,
                content=command.message.content,
                locale=command.message.locale,
                context_selection=[
                    item.model_dump(mode="json") for item in command.message.context
                ],
                created_at=self._now(),
            )
            assistant = self._repository.add_assistant_message(
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                locale=command.message.locale,
                created_at=self._now(),
            )
            self._quota.attach_messages(
                lease.ledger_id,
                user_message_id=user_message.id,
                assistant_message_id=assistant.id,
            )
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise

        attempt = self._accepted_attempt(
            conversation=conversation,
            company=command.company,
            principal=command.principal,
            user_message=user_message,
            assistant=assistant,
            structured=structured,
            lease=lease,
        )
        try:
            async for event in attempt:
                yield event
        finally:
            await attempt.aclose()

    async def stream_retry(
        self,
        command: RetryCommand,
    ) -> AsyncIterator[ChatStreamEvent]:
        conversation = self._owned_conversation(
            command.conversation_id,
            command.principal,
        )
        company = self._session.get(Company, conversation.company_id)
        assistant = self._repository.get_message(command.assistant_message_id)
        if (
            company is None
            or assistant is None
            or assistant.conversation_id != conversation.id
            or assistant.role != "assistant"
            or assistant.reply_to_message_id is None
        ):
            raise DomainError("CHAT_MESSAGE_NOT_FOUND", 404)
        user_message = self._repository.get_message(assistant.reply_to_message_id)
        if user_message is None or user_message.role != "user":
            raise DomainError("CHAT_MESSAGE_NOT_FOUND", 404)
        selections = _CONTEXT_LIST.validate_python(user_message.context_selection)
        structured = await self._context_provider.resolve(
            company=company,
            selections=selections,
            locale=user_message.locale,
        )

        replay = self._repository.attempt_by_quota_request(
            conversation.id,
            command.client_request_id,
        )
        if replay is not None:
            async for event in self._replay(
                conversation,
                replay[0],
                replay[1],
                command.principal,
            ):
                yield event
            return
        if assistant.state != "failed" or assistant.error_code not in _RETRYABLE_CODES:
            raise DomainError("CHAT_MESSAGE_RETRY_INVALID", 409)

        lease = self._quota.reserve(
            command.client_request_id,
            command.principal,
            conversation.id,
            now=self._now(),
            attempt_number=assistant.attempt_count + 1,
        )
        replay = self._repository.attempt_by_quota_request(
            conversation.id,
            command.client_request_id,
        )
        if replay is not None:
            self._session.rollback()
            async for event in self._replay(
                conversation,
                replay[0],
                replay[1],
                command.principal,
            ):
                yield event
            return
        try:
            assistant = self._repository.prepare_retry(assistant.id)
            self._quota.attach_messages(
                lease.ledger_id,
                user_message_id=user_message.id,
                assistant_message_id=assistant.id,
            )
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise

        attempt = self._accepted_attempt(
            conversation=conversation,
            company=company,
            principal=command.principal,
            user_message=user_message,
            assistant=assistant,
            structured=structured,
            lease=lease,
        )
        try:
            async for event in attempt:
                yield event
        finally:
            await attempt.aclose()

    async def _accepted_attempt(
        self,
        *,
        conversation: CompanyConversation,
        company: Company,
        principal: RequestPrincipal,
        user_message: ConversationMessage,
        assistant: ConversationMessage,
        structured: StructuredContextPack,
        lease: ChatQuotaLease,
    ) -> AsyncIterator[ChatStreamEvent]:
        try:
            yield ChatStreamEvent(
                "accepted",
                AcceptedEvent(
                    user_message_id=user_message.id,
                    assistant_message_id=assistant.id,
                    conversation_id=conversation.id,
                    quota=lease.status,
                ),
            )
            execution = self._execute_attempt(
                conversation=conversation,
                company=company,
                principal=principal,
                user_message=user_message,
                assistant=assistant,
                structured=structured,
                lease=lease,
            )
            try:
                async for event in execution:
                    yield event
            finally:
                await execution.aclose()
        finally:
            current = self._repository.get_message(assistant.id)
            if current is not None and current.state in {"pending", "planning"}:
                self._abort(lease, current, "CHAT_STREAM_CANCELLED")

    async def _execute_attempt(
        self,
        *,
        conversation: CompanyConversation,
        company: Company,
        principal: RequestPrincipal,
        user_message: ConversationMessage,
        assistant: ConversationMessage,
        structured: StructuredContextPack,
        lease: ChatQuotaLease,
    ) -> AsyncIterator[ChatStreamEvent]:
        stage = "route"
        try:
            self._repository.set_planning(assistant.id)
            self._session.commit()
            yield self._stage_event("route")
            history, summary = await self._conversation_context(
                conversation,
                current_message_id=user_message.id,
            )
            route = await self._intent_router.route(
                question=user_message.content,
                company_name=company.name,
                symbol=company.symbol,
                locale=user_message.locale,
                history=history,
                summary=summary,
            )
            if route.interaction_mode != "research":
                stored = self._complete_plain_answer(
                    assistant=assistant,
                    route=route,
                    lease=lease,
                )
                yield ChatStreamEvent(
                    "complete",
                    CompleteEvent(
                        message=_public_message(stored, []),
                        citations=[],
                        evidence_coverage=None,
                        quota=self.quota_status(principal),
                    ),
                )
                return

            question = route.resolved_question
            if question is None:
                raise ValueError("research route requires resolved question")

            stage = "retrieval"
            yield self._stage_event("retrieval")
            internal = await self._evidence_pipeline.prepare_internal(
                company=company,
                structured_context=structured,
                question=question,
                context_labels=[item.label for item in structured.items],
                history=history,
                summary=summary,
                locale=user_message.locale,
            )

            stage = "web"
            yield self._stage_event("web")
            prepared = await self._evidence_pipeline.add_web(
                internal=internal,
                company=company,
                question=question,
                locale=user_message.locale,
                principal=principal,
                conversation_id=conversation.id,
                assistant_message_id=assistant.id,
            )

            stage = "compose"
            yield self._stage_event("compose")
            plan = await self._answer_agent.create_plan(
                question,
                prepared.evidence,
                locale=user_message.locale,
                history=history,
            )

            stage = "verify"
            yield self._stage_event("verify")
            validated = validate_answer_plan(
                plan,
                prepared.evidence,
                locale=user_message.locale,
            )
            content = _render_content(
                validated.plan,
                validated.citations,
                user_message.locale,
            )
            stored = self._repository.complete_assistant(
                assistant.id,
                content=content,
                answer_plan=StoredResearchAnswer(
                    is_follow_up=route.is_follow_up,
                    resolved_question=question,
                    answer=validated.plan,
                ).model_dump(mode="json"),
                model_id=self._answer_agent.model_id,
                evidence_coverage=validated.plan.evidence_coverage,
                citations=validated.citations,
                web_traces=prepared.web_traces,
                completed_at=self._now(),
            )
            self._quota.consume(
                lease.ledger_id,
                validated.plan.evidence_coverage,
                now=self._now(),
            )
            self._session.commit()
        except asyncio.CancelledError:
            self._session.rollback()
            self._abort(lease, assistant, "CHAT_STREAM_CANCELLED")
            raise
        except Exception as error:
            self._session.rollback()
            code = _error_code(error, stage)
            failed = self._abort(lease, assistant, code)
            yield ChatStreamEvent(
                "error",
                ErrorEvent(
                    code=code,
                    retryable=code in _RETRYABLE_CODES,
                    assistant_message_id=failed.id,
                    quota=self.quota_status(principal),
                ),
            )
            return

        citations = self._public_citations(stored.id)
        for event in _section_events(validated.plan, citations):
            yield event
        for citation in citations:
            yield ChatStreamEvent("citation", citation)
        yield ChatStreamEvent(
            "complete",
            CompleteEvent(
                message=_public_message(stored, citations),
                citations=citations,
                evidence_coverage=validated.plan.evidence_coverage,
                quota=self.quota_status(principal),
            ),
        )

    def _complete_plain_answer(
        self,
        *,
        assistant: ConversationMessage,
        route: AgentRouteDecision,
        lease: ChatQuotaLease,
    ) -> ConversationMessage:
        response = route.response
        if response is None:
            raise ValueError("plain route requires response")
        stored_answer = StoredPlainAnswer(
            response_kind=route.interaction_mode,
            is_follow_up=route.is_follow_up,
            content=response,
        )
        stored = self._repository.complete_assistant(
            assistant.id,
            content=response,
            answer_plan=stored_answer.model_dump(mode="json"),
            model_id=self._intent_router.model_id,
            evidence_coverage=None,
            citations=(),
            web_traces=[],
            completed_at=self._now(),
        )
        self._quota.consume(
            lease.ledger_id,
            route.interaction_mode,
            now=self._now(),
        )
        self._session.commit()
        return stored

    async def _conversation_context(
        self,
        conversation: CompanyConversation,
        *,
        current_message_id: UUID,
    ) -> tuple[list[str], str | None]:
        messages = self._repository.completed_unsummarized(conversation)
        if len(messages) > 8:
            prefix = messages[:-8]
            summary = await self._summarizer.summarize(
                previous_summary=conversation.summary,
                messages=[_history_line(message) for message in prefix],
                locale=conversation.locale,
            )
            self._repository.update_summary(
                conversation,
                summary=summary,
                through_message_id=prefix[-1].id,
                updated_at=self._now(),
            )
            self._session.commit()
            messages = self._repository.completed_unsummarized(conversation)
        history = [
            _history_line(message)
            for message in messages
            if message.id != current_message_id
        ]
        return history[-8:], conversation.summary

    async def _replay(
        self,
        conversation: CompanyConversation,
        user_message: ConversationMessage,
        assistant: ConversationMessage,
        principal: RequestPrincipal,
    ) -> AsyncIterator[ChatStreamEvent]:
        quota = self.quota_status(principal)
        yield ChatStreamEvent(
            "accepted",
            AcceptedEvent(
                user_message_id=user_message.id,
                assistant_message_id=assistant.id,
                conversation_id=conversation.id,
                quota=quota,
            ),
        )
        if assistant.state == "completed" and assistant.answer_plan is not None:
            stored_answer = _stored_answer(assistant.answer_plan)
            citations = self._public_citations(assistant.id)
            coverage = None
            if isinstance(stored_answer, StoredResearchAnswer):
                plan = stored_answer.answer
                coverage = plan.evidence_coverage
                for event in _section_events(plan, citations):
                    yield event
                for citation in citations:
                    yield ChatStreamEvent("citation", citation)
            yield ChatStreamEvent(
                "complete",
                CompleteEvent(
                    message=_public_message(assistant, citations),
                    citations=citations,
                    evidence_coverage=coverage,
                    quota=quota,
                ),
            )
            return
        code = assistant.error_code or "CHAT_REQUEST_IN_PROGRESS"
        yield ChatStreamEvent(
            "error",
            ErrorEvent(
                code=code,
                retryable=code in _RETRYABLE_CODES,
                assistant_message_id=assistant.id,
                quota=quota,
            ),
        )

    def _abort(
        self,
        lease: ChatQuotaLease,
        assistant: ConversationMessage,
        code: str,
    ) -> ConversationMessage:
        current = self._repository.get_message(assistant.id)
        if current is None:
            raise DomainError("CHAT_MESSAGE_NOT_FOUND", 404)
        if current.state != "completed":
            current = self._repository.fail_assistant(
                current.id,
                error_code=code,
                completed_at=self._now(),
            )
            self._quota.refund(lease.ledger_id, code, now=self._now())
            self._session.commit()
        return current

    def _owned_conversation(
        self,
        conversation_id: UUID,
        principal: RequestPrincipal,
        *,
        company_id: int | None = None,
    ) -> CompanyConversation:
        conversation = self._repository.get_owned(
            conversation_id,
            principal,
            now=self._now(),
            company_id=company_id,
        )
        if conversation is None:
            raise DomainError("CHAT_CONVERSATION_NOT_FOUND", 404)
        return conversation

    def _public_citations(self, message_id: UUID) -> list[CitationPublic]:
        return [
            CitationPublic.model_validate(citation)
            for citation in self._repository.list_citations(message_id)
        ]

    @staticmethod
    def _stage_event(stage: str) -> ChatStreamEvent:
        return ChatStreamEvent(
            "stage",
            StageEvent(stage=stage, status_key=f"chat.stage.{stage}"),
        )


def _section_events(
    plan: ResearchAnswerPlan,
    citations: list[CitationPublic],
) -> list[ChatStreamEvent]:
    sections = _section_values(plan, citations)
    return [
        ChatStreamEvent("section", SectionEvent(section=name, delta=text))
        for name, text in sections
    ]


def _render_content(plan, citations, locale: str) -> str:
    headings = (
        ("结论", "关键证据", "风险与不确定性", "来源")
        if locale == "zh-CN"
        else ("Conclusion", "Key evidence", "Risks and uncertainties", "Sources")
    )
    values = [value for _, value in _section_values(plan, citations)]
    return "\n\n".join(
        f"## {heading}\n\n{value}"
        for heading, value in zip(headings, values, strict=True)
    )


def _section_values(plan, citations) -> tuple[tuple[str, str], ...]:
    source_lines = [
        f"- [{citation.ordinal + 1}] {citation.title}" for citation in citations
    ]
    return (
        ("direct_conclusion", plan.direct_conclusion.text),
        ("key_evidence", _point_list(plan.key_evidence)),
        ("risks_and_uncertainties", _point_list(plan.risks_and_uncertainties)),
        ("sources", "\n".join(source_lines)),
    )


def _point_list(points) -> str:
    return "\n".join(f"- {point.text}" for point in points)


def _history_line(message: ConversationMessage) -> str:
    return f"{message.role}: {message.content}"


def _public_message(
    message: ConversationMessage,
    citations: list[CitationPublic],
) -> MessagePublic:
    return MessagePublic(
        id=message.id,
        conversation_id=message.conversation_id,
        reply_to_message_id=message.reply_to_message_id,
        role=message.role,
        state=message.state,
        content=message.content,
        locale=message.locale,
        response_kind=_message_response_kind(message),
        evidence_coverage=message.evidence_coverage,
        error_code=message.error_code,
        attempt_count=message.attempt_count,
        created_at=message.created_at,
        completed_at=message.completed_at,
        citations=citations,
    )


def _error_code(error: Exception, stage: str) -> str:
    if isinstance(error, DomainError) and error.code.startswith("CHAT_"):
        return error.code
    return _STAGE_CODES[stage]


def _stored_answer(payload: dict) -> StoredResearchAnswer | StoredPlainAnswer:
    try:
        return _STORED_ANSWER.validate_python(payload)
    except ValidationError:
        return StoredResearchAnswer(
            is_follow_up=False,
            resolved_question="",
            answer=ResearchAnswerPlan.model_validate(payload),
        )


def _message_response_kind(message: ConversationMessage):
    if message.role != "assistant" or message.answer_plan is None:
        return None
    return stored_response_kind(message.answer_plan)
