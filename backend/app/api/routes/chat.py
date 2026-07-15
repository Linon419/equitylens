from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import (
    AgentPrincipal,
    ChatContextProviderDep,
    ChatQuotaServiceDep,
    ChatRepositoryDep,
    ChatServiceDep,
    JobBackendDep,
    SecDataProviderDep,
    SessionDep,
)
from app.chat.answer_schemas import stored_response_kind
from app.chat.schemas import (
    ChatQuotaStatus,
    ChatReadiness,
    CitationPublic,
    ConversationCreate,
    ConversationPatch,
    ConversationPublic,
    MessageCreate,
    MessagePage,
    MessagePublic,
    RetryCreate,
)
from app.chat.service import MessageCommand, RetryCommand
from app.chat.sse import SSE_HEADERS, ChatStreamEvent, encode_sse_stream
from app.chat.structured_repository import SqlStructuredContextRepository
from app.companies.service import get_or_create_company
from app.core.config import settings
from app.core.errors import DomainError
from app.jobs._filing_index import (
    FilingIndexSynchronizationServices,
    synchronize_filing_index,
)
from app.jobs.schemas import FilingIndexSyncResponse
from app.models.company_model import Company

router = APIRouter()


@router.get(
    "/companies/{symbol}/chat-readiness",
    response_model=ChatReadiness,
)
async def get_chat_readiness(
    symbol: str,
    session: SessionDep,
    principal: AgentPrincipal,
    context_provider: ChatContextProviderDep,
    sec_provider: SecDataProviderDep,
    locale: Literal["en-US", "zh-CN"] = "en-US",
) -> ChatReadiness:
    del principal
    company = await get_or_create_company(session, sec_provider, symbol)
    context = await context_provider.resolve(
        company=company,
        selections=[],
        locale=locale,
    )
    return context.readiness


@router.post(
    "/companies/{symbol}/chat-index/sync",
    response_model=FilingIndexSyncResponse,
)
async def synchronize_chat_index(
    symbol: str,
    response: Response,
    session: SessionDep,
    principal: AgentPrincipal,
    backend: JobBackendDep,
    sec_provider: SecDataProviderDep,
) -> FilingIndexSyncResponse:
    company = await get_or_create_company(session, sec_provider, symbol)
    if company.id is None:
        raise DomainError("COMPANY_NOT_FOUND", 404)
    filing = SqlStructuredContextRepository(session).latest_filing(company.id)
    if filing is None:
        raise DomainError("FILING_NOT_FOUND", 404)
    result = await synchronize_filing_index(
        session,
        company=company,
        principal=principal,
        filing=filing,
        services=FilingIndexSynchronizationServices(
            job_backend=backend,
            schema_version=settings.CHAT_INDEX_SCHEMA_VERSION,
            embedding_model=settings.CHAT_EMBEDDING_MODEL,
        ),
    )
    if result.status == "accepted":
        response.status_code = status.HTTP_202_ACCEPTED
    return result


@router.get(
    "/companies/{symbol}/conversations",
    response_model=list[ConversationPublic],
)
async def list_conversations(
    symbol: str,
    session: SessionDep,
    principal: AgentPrincipal,
    repository: ChatRepositoryDep,
    sec_provider: SecDataProviderDep,
) -> list[ConversationPublic]:
    company = await get_or_create_company(session, sec_provider, symbol)
    if company.id is None:
        raise DomainError("COMPANY_NOT_FOUND", 404)
    return [
        ConversationPublic.model_validate(item)
        for item in repository.list_for_company(
            company.id,
            principal,
            now=datetime.now(UTC),
        )
    ]


@router.post(
    "/companies/{symbol}/conversations",
    response_model=ConversationPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    symbol: str,
    command: ConversationCreate,
    session: SessionDep,
    principal: AgentPrincipal,
    repository: ChatRepositoryDep,
    sec_provider: SecDataProviderDep,
) -> ConversationPublic:
    company = await get_or_create_company(session, sec_provider, symbol)
    if company.id is None:
        raise DomainError("COMPANY_NOT_FOUND", 404)
    now = datetime.now(UTC)
    title = command.title or _default_title(company.symbol, command.locale)
    if principal.principal_type == "guest":
        conversation = repository.create_or_get_guest(
            company_id=company.id,
            principal=principal,
            locale=command.locale,
            title=title,
            now=now,
            retention_days=settings.CHAT_GUEST_RETENTION_DAYS,
        )
    else:
        conversation = repository.create_user(
            company_id=company.id,
            principal=principal,
            locale=command.locale,
            title=title,
            now=now,
        )
    session.commit()
    session.refresh(conversation)
    return ConversationPublic.model_validate(conversation)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationPublic,
)
def get_conversation(
    conversation_id: UUID,
    principal: AgentPrincipal,
    repository: ChatRepositoryDep,
) -> ConversationPublic:
    conversation = _owned(repository, conversation_id, principal)
    return ConversationPublic.model_validate(conversation)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationPublic,
)
def rename_conversation(
    conversation_id: UUID,
    command: ConversationPatch,
    session: SessionDep,
    principal: AgentPrincipal,
    repository: ChatRepositoryDep,
) -> ConversationPublic:
    _owned(repository, conversation_id, principal)
    if principal.principal_type == "guest":
        raise DomainError("CHAT_CONVERSATION_RENAME_FORBIDDEN", 403)
    conversation = repository.rename_owned(
        conversation_id,
        principal,
        title=command.title,
        now=datetime.now(UTC),
    )
    if conversation is None:
        raise DomainError("CHAT_CONVERSATION_NOT_FOUND", 404)
    session.commit()
    session.refresh(conversation)
    return ConversationPublic.model_validate(conversation)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def archive_conversation(
    conversation_id: UUID,
    session: SessionDep,
    principal: AgentPrincipal,
    repository: ChatRepositoryDep,
) -> Response:
    conversation = repository.archive_owned(
        conversation_id,
        principal,
        now=datetime.now(UTC),
    )
    if conversation is None:
        raise DomainError("CHAT_CONVERSATION_NOT_FOUND", 404)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessagePage,
)
def list_messages(
    conversation_id: UUID,
    principal: AgentPrincipal,
    repository: ChatRepositoryDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> MessagePage:
    _owned(repository, conversation_id, principal)
    try:
        messages, next_cursor = repository.list_messages(
            conversation_id,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as error:
        raise DomainError("CHAT_MESSAGE_CURSOR_INVALID", 422) from error
    return MessagePage(
        items=[_public_message(repository, item) for item in messages],
        next_cursor=next_cursor,
    )


@router.post("/conversations/{conversation_id}/messages")
async def create_message(
    conversation_id: UUID,
    command: MessageCreate,
    principal: AgentPrincipal,
    repository: ChatRepositoryDep,
    session: SessionDep,
    service: ChatServiceDep,
) -> StreamingResponse:
    conversation = _owned(repository, conversation_id, principal)
    company = session.get(Company, conversation.company_id)
    if company is None:
        raise DomainError("COMPANY_NOT_FOUND", 404)
    events = service.stream_message(
        MessageCommand(
            company=company,
            conversation_id=conversation_id,
            principal=principal,
            message=command,
        )
    )
    return await _stream_response(events)


@router.post("/conversations/{conversation_id}/messages/{assistant_message_id}/retry")
async def retry_message(
    conversation_id: UUID,
    assistant_message_id: UUID,
    command: RetryCreate,
    principal: AgentPrincipal,
    repository: ChatRepositoryDep,
    service: ChatServiceDep,
) -> StreamingResponse:
    _owned(repository, conversation_id, principal)
    events = service.stream_retry(
        RetryCommand(
            conversation_id=conversation_id,
            assistant_message_id=assistant_message_id,
            client_request_id=command.client_request_id,
            principal=principal,
        )
    )
    return await _stream_response(events)


@router.get("/chat-quota", response_model=ChatQuotaStatus)
def get_chat_quota(
    principal: AgentPrincipal,
    quota: ChatQuotaServiceDep,
) -> ChatQuotaStatus:
    return quota.status(principal, now=datetime.now(UTC))


async def _stream_response(
    events: AsyncIterator[ChatStreamEvent],
) -> StreamingResponse:
    try:
        first = await anext(events)
    except StopAsyncIteration as error:
        raise DomainError("CHAT_STREAM_EMPTY", 500) from error

    async def prefetched() -> AsyncIterator[ChatStreamEvent]:
        try:
            yield first
            async for event in events:
                yield event
        finally:
            await events.aclose()

    return StreamingResponse(
        encode_sse_stream(prefetched()),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


def _owned(repository, conversation_id: UUID, principal):
    conversation = repository.get_owned(
        conversation_id,
        principal,
        now=datetime.now(UTC),
    )
    if conversation is None:
        raise DomainError("CHAT_CONVERSATION_NOT_FOUND", 404)
    return conversation


def _public_message(repository, message) -> MessagePublic:
    citations = [
        CitationPublic.model_validate(item)
        for item in repository.list_citations(message.id)
    ]
    return MessagePublic(
        id=message.id,
        conversation_id=message.conversation_id,
        reply_to_message_id=message.reply_to_message_id,
        role=message.role,
        state=message.state,
        content=message.content,
        locale=message.locale,
        response_kind=(
            stored_response_kind(message.answer_plan)
            if message.role == "assistant"
            else None
        ),
        evidence_coverage=message.evidence_coverage,
        error_code=message.error_code,
        attempt_count=message.attempt_count,
        created_at=message.created_at,
        completed_at=message.completed_at,
        citations=citations,
    )


def _default_title(symbol: str, locale: str) -> str:
    return f"{symbol} 投研" if locale == "zh-CN" else f"{symbol} Research"
