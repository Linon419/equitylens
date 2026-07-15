import base64
import json
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, false, or_
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, select

from app.models.chat_model import (
    CompanyConversation,
    ConversationMessage,
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
                CompanyConversation.guest_principal_hash
                == principal.principal_hash,
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
                    ConversationMessage.id
                    == WebSearchTrace.assistant_message_id,
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
            return (
                CompanyConversation.guest_principal_hash
                == principal.principal_hash
            )
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
