from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.chat.contracts import (
    ChatQuotaRecord,
    ChatQuotaRepository,
    ChatQuotaReservation,
)
from app.chat.schemas import ChatQuotaStatus
from app.core.errors import DomainError
from app.models.chat_model import ChatQuotaLedger
from app.quota.identity import RequestPrincipal

TERMINAL_COVERAGE = {"complete", "partial", "insufficient"}


class ChatQuotaExceeded(DomainError):
    def __init__(self) -> None:
        super().__init__("CHAT_DAILY_QUOTA_EXCEEDED", 429)


class ChatQuotaRequestConflict(DomainError):
    def __init__(self) -> None:
        super().__init__("CHAT_REQUEST_CONFLICT", 409)


@dataclass(frozen=True)
class ChatQuotaLease:
    ledger_id: UUID
    request_id: UUID
    state: Literal["reserved", "consumed", "refunded"]
    attempt_number: int
    status: ChatQuotaStatus


class SqlChatQuotaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_scope(
        self,
        principal_type: str,
        principal_key: str,
        usage_date: date,
    ) -> None:
        if self._session.bind is None:
            return
        if self._session.bind.dialect.name != "postgresql":
            return
        lock_key = f"chat:{principal_type}:{principal_key}:{usage_date.isoformat()}"
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            params={"key": lock_key},
        )

    def find_by_request(self, request_id: UUID) -> ChatQuotaRecord | None:
        row = self._session.exec(
            select(ChatQuotaLedger).where(
                ChatQuotaLedger.request_id == request_id
            )
        ).first()
        return _record(row) if row is not None else None

    def count_active(
        self,
        principal_type: str,
        principal_key: str,
        usage_date: date,
    ) -> int:
        count = self._session.exec(
            select(func.count(ChatQuotaLedger.id)).where(
                ChatQuotaLedger.principal_type == principal_type,
                ChatQuotaLedger.principal_key == principal_key,
                ChatQuotaLedger.usage_date == usage_date,
                ChatQuotaLedger.state.in_(("reserved", "consumed")),
            )
        ).one()
        return int(count)

    def add(self, reservation: ChatQuotaReservation) -> ChatQuotaRecord:
        row = ChatQuotaLedger(
            request_id=reservation.request_id,
            principal_type=reservation.principal_type,
            principal_key=reservation.principal_key,
            usage_date=reservation.usage_date,
            conversation_id=reservation.conversation_id,
            attempt_number=reservation.attempt_number,
            state="reserved",
            created_at=reservation.now,
            updated_at=reservation.now,
        )
        self._session.add(row)
        self._session.flush()
        return _record(row)

    def get(
        self,
        ledger_id: UUID,
        *,
        lock: bool = False,
    ) -> ChatQuotaRecord | None:
        statement = select(ChatQuotaLedger).where(
            ChatQuotaLedger.id == ledger_id
        )
        if lock:
            statement = statement.with_for_update()
        row = self._session.exec(statement).first()
        return _record(row) if row is not None else None

    def attach_messages(
        self,
        ledger_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
    ) -> ChatQuotaRecord:
        row = self._ledger_row(ledger_id, lock=True)
        if row is None:
            raise LookupError("CHAT_QUOTA_LEDGER_NOT_FOUND")
        current = row.user_message_id, row.assistant_message_id
        desired = user_message_id, assistant_message_id
        if current != (None, None) and current != desired:
            raise ChatQuotaRequestConflict()
        row.user_message_id = user_message_id
        row.assistant_message_id = assistant_message_id
        self._session.add(row)
        self._session.flush()
        return _record(row)

    def transition(
        self,
        ledger_id: UUID,
        *,
        target: Literal["consumed", "refunded"],
        now: datetime,
        refund_reason: str | None = None,
    ) -> bool:
        row = self._ledger_row(ledger_id, lock=True)
        if row is None or row.state != "reserved":
            return False
        row.state = target
        row.updated_at = now
        if target == "consumed":
            row.consumed_at = now
        else:
            row.refunded_at = now
            row.refund_reason = refund_reason
        self._session.add(row)
        self._session.flush()
        return True

    def _ledger_row(
        self,
        ledger_id: UUID,
        *,
        lock: bool,
    ) -> ChatQuotaLedger | None:
        statement = select(ChatQuotaLedger).where(
            ChatQuotaLedger.id == ledger_id
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.exec(statement).first()


class ChatQuotaService:
    def __init__(
        self,
        repository: ChatQuotaRepository,
        *,
        guest_limit: int = 2,
        user_limit: int = 10,
    ) -> None:
        self._repository = repository
        self._guest_limit = guest_limit
        self._user_limit = user_limit

    def status(
        self,
        principal: RequestPrincipal,
        *,
        now: datetime,
    ) -> ChatQuotaStatus:
        current = _as_utc(now)
        principal_key = _principal_key(principal)
        used = self._repository.count_active(
            principal.principal_type,
            principal_key,
            current.date(),
        )
        return _status(self._limit(principal), used, current.date())

    def reserve(
        self,
        request_id: UUID,
        principal: RequestPrincipal,
        conversation_id: UUID,
        *,
        now: datetime,
        attempt_number: int = 0,
    ) -> ChatQuotaLease:
        current = _as_utc(now)
        principal_key = _principal_key(principal)
        self._repository.lock_scope(
            principal.principal_type,
            principal_key,
            current.date(),
        )
        existing = self._repository.find_by_request(request_id)
        if existing is not None:
            self._validate_replay(existing, principal, principal_key, conversation_id)
            return self._lease(existing, principal, current)
        limit = self._limit(principal)
        used = self._repository.count_active(
            principal.principal_type,
            principal_key,
            current.date(),
        )
        if used >= limit:
            raise ChatQuotaExceeded()
        record = self._repository.add(
            ChatQuotaReservation(
                request_id=request_id,
                principal_type=principal.principal_type,
                principal_key=principal_key,
                usage_date=current.date(),
                conversation_id=conversation_id,
                attempt_number=attempt_number,
                now=current,
            )
        )
        return ChatQuotaLease(
            ledger_id=record.id,
            request_id=record.request_id,
            state=record.state,
            attempt_number=record.attempt_number,
            status=_status(limit, used + 1, current.date()),
        )

    def attach_messages(
        self,
        ledger_id: UUID,
        *,
        user_message_id: UUID,
        assistant_message_id: UUID,
    ) -> None:
        self._repository.attach_messages(
            ledger_id,
            user_message_id,
            assistant_message_id,
        )

    def consume(
        self,
        ledger_id: UUID,
        coverage: str,
        *,
        now: datetime,
    ) -> bool:
        if coverage not in TERMINAL_COVERAGE:
            raise ValueError("terminal evidence coverage required")
        return self._repository.transition(
            ledger_id,
            target="consumed",
            now=_as_utc(now),
        )

    def refund(
        self,
        ledger_id: UUID,
        reason: str,
        *,
        now: datetime,
    ) -> bool:
        return self._repository.transition(
            ledger_id,
            target="refunded",
            now=_as_utc(now),
            refund_reason=reason,
        )

    def _lease(
        self,
        record: ChatQuotaRecord,
        principal: RequestPrincipal,
        now: datetime,
    ) -> ChatQuotaLease:
        return ChatQuotaLease(
            ledger_id=record.id,
            request_id=record.request_id,
            state=record.state,
            attempt_number=record.attempt_number,
            status=self.status(principal, now=now),
        )

    def _limit(self, principal: RequestPrincipal) -> int:
        return (
            self._guest_limit
            if principal.principal_type == "guest"
            else self._user_limit
        )

    @staticmethod
    def _validate_replay(
        record: ChatQuotaRecord,
        principal: RequestPrincipal,
        principal_key: str,
        conversation_id: UUID,
    ) -> None:
        if (
            record.principal_type != principal.principal_type
            or record.principal_key != principal_key
            or record.conversation_id != conversation_id
        ):
            raise ChatQuotaRequestConflict()


def _record(row: ChatQuotaLedger) -> ChatQuotaRecord:
    return ChatQuotaRecord(
        id=row.id,
        request_id=row.request_id,
        principal_type=row.principal_type,
        principal_key=row.principal_key,
        usage_date=row.usage_date,
        conversation_id=row.conversation_id,
        user_message_id=row.user_message_id,
        assistant_message_id=row.assistant_message_id,
        attempt_number=row.attempt_number,
        state=row.state,
    )


def _principal_key(principal: RequestPrincipal) -> str:
    if principal.principal_type == "user":
        if principal.user_id is None:
            raise ValueError("user principal requires user_id")
        return str(principal.user_id)
    return principal.principal_hash


def _status(limit: int, used: int, usage_date: date) -> ChatQuotaStatus:
    resets_at = datetime.combine(
        usage_date + timedelta(days=1),
        time.min,
        tzinfo=UTC,
    )
    return ChatQuotaStatus(
        limit=limit,
        used=used,
        remaining=max(0, limit - used),
        resets_at=resets_at,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
