import base64
import json
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, delete, false, or_
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, select

from app.chat.schemas import CitationSnapshot
from app.chat.web_trace import WebSearchTraceRecord
from app.models.chat_model import (
    ChatQuotaLedger,
    CompanyConversation,
    ConversationMessage,
    MessageCitation,
    WebSearchTrace,
)
from app.quota.identity import RequestPrincipal


class ConversationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_or_get_guest(
        self,
        *,
        company_id: int,
        principal: RequestPrincipal,
        locale: str,
        title: str,
        now: datetime,
        retention_days: int,
    ) -> CompanyConversation:
        if principal.principal_type != "guest":
            raise ValueError("guest principal required")
        existing = self._session.exec(
            select(CompanyConversation)
            .where(
                CompanyConversation.company_id == company_id,
                CompanyConversation.guest_principal_hash == principal.principal_hash,
                CompanyConversation.archived_at.is_(None),
            )
            .with_for_update()
        ).first()
        if existing is not None and existing.expires_at is not None:
            if existing.expires_at > now:
                return existing
            existing.archived_at = now
            existing.updated_at = now
            self._session.add(existing)
            self._session.flush()
        conversation = CompanyConversation(
            company_id=company_id,
            guest_principal_hash=principal.principal_hash,
            title=title,
            locale=locale,
            expires_at=now + timedelta(days=retention_days),
            created_at=now,
            updated_at=now,
        )
        self._session.add(conversation)
        self._session.flush()
        return conversation

    def create_user(
        self,
        *,
        company_id: int,
        principal: RequestPrincipal,
        locale: str,
        title: str,
        now: datetime,
    ) -> CompanyConversation:
        if principal.principal_type != "user" or principal.user_id is None:
            raise ValueError("user principal required")
        conversation = CompanyConversation(
            company_id=company_id,
            user_id=principal.user_id,
            title=title,
            locale=locale,
            created_at=now,
            updated_at=now,
        )
        self._session.add(conversation)
        self._session.flush()
        return conversation

    def list_for_company(
        self,
        company_id: int,
        principal: RequestPrincipal,
        *,
        now: datetime,
    ) -> list[CompanyConversation]:
        return list(
            self._session.exec(
                select(CompanyConversation)
                .where(
                    CompanyConversation.company_id == company_id,
                    self._owner_predicate(principal),
                    self._active_predicate(now),
                )
                .order_by(
                    CompanyConversation.created_at.desc(),
                    CompanyConversation.id.desc(),
                )
            ).all()
        )

    def get_owned(
        self,
        conversation_id: UUID,
        principal: RequestPrincipal,
        *,
        now: datetime,
        company_id: int | None = None,
        lock: bool = False,
    ) -> CompanyConversation | None:
        conditions: list[ColumnElement[bool]] = [
            CompanyConversation.id == conversation_id,
            self._owner_predicate(principal),
            self._active_predicate(now),
        ]
        if company_id is not None:
            conditions.append(CompanyConversation.company_id == company_id)
        statement = select(CompanyConversation).where(*conditions)
        if lock:
            statement = statement.with_for_update()
        return self._session.exec(statement).first()

    def rename_owned(
        self,
        conversation_id: UUID,
        principal: RequestPrincipal,
        *,
        title: str,
        now: datetime,
    ) -> CompanyConversation | None:
        if principal.principal_type != "user":
            return None
        conversation = self.get_owned(
            conversation_id,
            principal,
            now=now,
            lock=True,
        )
        if conversation is None:
            return None
        conversation.title = title
        conversation.updated_at = now
        self._session.add(conversation)
        self._session.flush()
        return conversation

    def archive_owned(
        self,
        conversation_id: UUID,
        principal: RequestPrincipal,
        *,
        now: datetime,
    ) -> CompanyConversation | None:
        conversation = self.get_owned(
            conversation_id,
            principal,
            now=now,
            lock=True,
        )
        if conversation is None:
            return None
        conversation.archived_at = now
        conversation.updated_at = now
        self._session.add(conversation)
        self._session.flush()
        return conversation

    def add_user_message(
        self,
        *,
        conversation_id: UUID,
        request_id: UUID,
        content: str,
        locale: str,
        context_selection: list[dict],
        created_at: datetime,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            state="completed",
            content=content,
            locale=locale,
            client_request_id=request_id,
            context_selection=context_selection,
            created_at=created_at,
            completed_at=created_at,
        )
        self._session.add(message)
        self._session.flush()
        return message

    def message_by_request(
        self,
        conversation_id: UUID,
        request_id: UUID,
    ) -> ConversationMessage | None:
        return self._session.exec(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.client_request_id == request_id,
            )
        ).first()

    def add_assistant_message(
        self,
        *,
        conversation_id: UUID,
        user_message_id: UUID,
        locale: str,
        created_at: datetime,
    ) -> ConversationMessage:
        message = ConversationMessage(
            conversation_id=conversation_id,
            reply_to_message_id=user_message_id,
            role="assistant",
            state="pending",
            content="",
            locale=locale,
            created_at=created_at,
        )
        self._session.add(message)
        self._session.flush()
        return message

    def assistant_for_user(
        self,
        user_message_id: UUID,
    ) -> ConversationMessage | None:
        return self._session.exec(
            select(ConversationMessage)
            .where(
                ConversationMessage.reply_to_message_id == user_message_id,
                ConversationMessage.role == "assistant",
            )
            .order_by(ConversationMessage.created_at.desc())
        ).first()

    def get_message(
        self,
        message_id: UUID,
        *,
        lock: bool = False,
    ) -> ConversationMessage | None:
        statement = select(ConversationMessage).where(
            ConversationMessage.id == message_id
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.exec(statement).first()

    def attempt_by_quota_request(
        self,
        conversation_id: UUID,
        request_id: UUID,
    ) -> tuple[ConversationMessage, ConversationMessage] | None:
        ledger = self._session.exec(
            select(ChatQuotaLedger).where(
                ChatQuotaLedger.request_id == request_id,
                ChatQuotaLedger.conversation_id == conversation_id,
            )
        ).first()
        if (
            ledger is None
            or ledger.user_message_id is None
            or ledger.assistant_message_id is None
        ):
            return None
        user_message = self.get_message(ledger.user_message_id)
        assistant_message = self.get_message(ledger.assistant_message_id)
        if user_message is None or assistant_message is None:
            return None
        return user_message, assistant_message

    def set_planning(self, message_id: UUID) -> ConversationMessage:
        message = self._required_message(message_id, lock=True)
        message.state = "planning"
        message.error_code = None
        self._session.add(message)
        self._session.flush()
        return message

    def complete_assistant(
        self,
        message_id: UUID,
        *,
        content: str,
        answer_plan: dict,
        model_id: str,
        evidence_coverage: str,
        citations: tuple[CitationSnapshot, ...],
        web_traces: list[WebSearchTraceRecord],
        completed_at: datetime,
    ) -> ConversationMessage:
        message = self._required_message(message_id, lock=True)
        self._clear_attempt_evidence(message_id)
        message.state = "completed"
        message.content = content
        message.answer_plan = answer_plan
        message.model_id = model_id
        message.evidence_coverage = evidence_coverage
        message.error_code = None
        message.completed_at = completed_at
        self._session.add(message)
        for citation in citations:
            values = citation.model_dump(exclude={"evidence_id"})
            self._session.add(MessageCitation(message_id=message_id, **values))
        for trace in web_traces:
            self._session.add(
                WebSearchTrace(
                    assistant_message_id=message_id,
                    normalized_query=trace.normalized_query,
                    search_decision=trace.search_decision,
                    search_reason=trace.search_reason,
                    candidate_results=trace.candidate_results,
                    selected_result_ids=trace.selected_result_ids,
                    artifact_key=trace.artifact_key,
                    artifact_sha256=trace.artifact_sha256,
                    provider_request_id=trace.provider_request_id,
                    duration_ms=trace.duration_ms,
                    tool_ordinal=trace.tool_ordinal,
                    created_at=completed_at,
                )
            )
        self._session.flush()
        return message

    def fail_assistant(
        self,
        message_id: UUID,
        *,
        error_code: str,
        completed_at: datetime,
    ) -> ConversationMessage:
        message = self._required_message(message_id, lock=True)
        if message.state == "completed":
            return message
        message.state = "failed"
        message.error_code = error_code
        message.completed_at = completed_at
        self._session.add(message)
        self._session.flush()
        return message

    def prepare_retry(
        self,
        message_id: UUID,
    ) -> ConversationMessage:
        message = self._required_message(message_id, lock=True)
        if message.role != "assistant" or message.state != "failed":
            raise ValueError("CHAT_MESSAGE_RETRY_INVALID")
        message.state = "pending"
        message.content = ""
        message.answer_plan = None
        message.model_id = None
        message.evidence_coverage = None
        message.error_code = None
        message.completed_at = None
        message.attempt_count += 1
        self._session.add(message)
        self._session.flush()
        return message

    def list_citations(self, message_id: UUID) -> list[MessageCitation]:
        return list(
            self._session.exec(
                select(MessageCitation)
                .where(MessageCitation.message_id == message_id)
                .order_by(MessageCitation.ordinal)
            ).all()
        )

    def completed_unsummarized(
        self,
        conversation: CompanyConversation,
    ) -> list[ConversationMessage]:
        messages = list(
            self._session.exec(
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.state == "completed",
                )
                .order_by(
                    ConversationMessage.created_at,
                    ConversationMessage.id,
                )
            ).all()
        )
        checkpoint = conversation.summary_through_message_id
        if checkpoint is None:
            return messages
        for index, message in enumerate(messages):
            if message.id == checkpoint:
                return messages[index + 1 :]
        return messages

    def update_summary(
        self,
        conversation: CompanyConversation,
        *,
        summary: str,
        through_message_id: UUID,
        updated_at: datetime,
    ) -> None:
        conversation.summary = summary
        conversation.summary_through_message_id = through_message_id
        conversation.updated_at = updated_at
        self._session.add(conversation)
        self._session.flush()

    def _required_message(
        self,
        message_id: UUID,
        *,
        lock: bool,
    ) -> ConversationMessage:
        message = self.get_message(message_id, lock=lock)
        if message is None:
            raise LookupError("CHAT_MESSAGE_NOT_FOUND")
        return message

    def _clear_attempt_evidence(self, message_id: UUID) -> None:
        self._session.exec(
            delete(MessageCitation).where(MessageCitation.message_id == message_id)
        )
        self._session.exec(
            delete(WebSearchTrace).where(
                WebSearchTrace.assistant_message_id == message_id
            )
        )

    def list_messages(
        self,
        conversation_id: UUID,
        *,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[ConversationMessage], str | None]:
        statement = select(ConversationMessage).where(
            ConversationMessage.conversation_id == conversation_id
        )
        if cursor is not None:
            created_at, message_id = decode_message_cursor(cursor)
            statement = statement.where(
                or_(
                    ConversationMessage.created_at > created_at,
                    and_(
                        ConversationMessage.created_at == created_at,
                        ConversationMessage.id > message_id,
                    ),
                )
            )
        rows = list(
            self._session.exec(
                statement.order_by(
                    ConversationMessage.created_at,
                    ConversationMessage.id,
                ).limit(limit + 1)
            ).all()
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            encode_message_cursor(items[-1].created_at, items[-1].id)
            if has_more and items
            else None
        )
        return items, next_cursor

    def cleanup_expired_guests(self, *, now: datetime) -> list[str]:
        expired = list(
            self._session.exec(
                select(CompanyConversation).where(
                    CompanyConversation.guest_principal_hash.is_not(None),
                    CompanyConversation.expires_at <= now,
                )
            ).all()
        )
        if not expired:
            return []
        conversation_ids = [conversation.id for conversation in expired]
        artifact_keys = list(
            self._session.exec(
                select(WebSearchTrace.artifact_key)
                .join(
                    ConversationMessage,
                    ConversationMessage.id == WebSearchTrace.assistant_message_id,
                )
                .where(
                    ConversationMessage.conversation_id.in_(conversation_ids),
                    WebSearchTrace.artifact_key.is_not(None),
                )
                .order_by(WebSearchTrace.artifact_key)
            ).all()
        )
        for conversation in expired:
            self._session.delete(conversation)
        self._session.flush()
        return [key for key in artifact_keys if key is not None]

    @staticmethod
    def _active_predicate(now: datetime) -> ColumnElement[bool]:
        return and_(
            CompanyConversation.archived_at.is_(None),
            or_(
                CompanyConversation.expires_at.is_(None),
                CompanyConversation.expires_at > now,
            ),
        )

    @staticmethod
    def _owner_predicate(
        principal: RequestPrincipal,
    ) -> ColumnElement[bool]:
        if principal.principal_type == "guest":
            return CompanyConversation.guest_principal_hash == principal.principal_hash
        if principal.user_id is None:
            return false()
        return CompanyConversation.user_id == principal.user_id


def encode_message_cursor(created_at: datetime, message_id: UUID) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": str(message_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode()


def decode_message_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(value + padding))
        if set(payload) != {"created_at", "id"}:
            raise ValueError
        return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
    except (TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("CHAT_MESSAGE_CURSOR_INVALID") from error
