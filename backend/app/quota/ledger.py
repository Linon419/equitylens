from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal, Protocol
from uuid import UUID

from sqlmodel import Session, select

from app.models.job_model import AgentDailyUsage
from app.models.supply_chain_model import AgentQuotaReservation


@dataclass(frozen=True)
class QuotaReservation:
    principal_type: str
    principal_hash: str
    usage_date: date
    daily_limit: int

    @property
    def key(self) -> tuple[str, str, date]:
        return self.principal_type, self.principal_hash, self.usage_date


@dataclass(frozen=True)
class JobQuotaReservation:
    job_id: UUID
    principal_type: Literal["guest", "user"]
    principal_hash: str
    ip_hash: str | None
    usage_date: date
    principal_daily_limit: int
    ip_daily_limit: int | None
    now: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class JobQuotaLease:
    job_id: UUID
    principal_type: Literal["guest", "user"]
    principal_hash: str
    ip_hash: str | None
    usage_date: date
    principal_daily_limit: int
    ip_daily_limit: int | None
    state: Literal["reserved", "consumed", "refunded"]
    created_at: datetime
    updated_at: datetime
    consumed_at: datetime | None = None
    refunded_at: datetime | None = None


class AggregateReservationRepository(Protocol):
    _session: Session

    def reserve_many(
        self,
        reservations: list[QuotaReservation],
    ) -> dict[tuple[str, str, date], int]: ...


class SqlJobQuotaLedgerMixin:
    _session: Session

    def reserve_for_job(
        self: AggregateReservationRepository,
        reservation: JobQuotaReservation,
    ) -> JobQuotaLease:
        existing = self.lease_for_job(reservation.job_id)
        if existing is not None:
            return existing
        self.reserve_many(job_aggregates(reservation))
        row = AgentQuotaReservation(
            job_id=reservation.job_id,
            principal_type=reservation.principal_type,
            principal_hash=reservation.principal_hash,
            ip_hash=reservation.ip_hash,
            usage_date=reservation.usage_date,
            principal_daily_limit=reservation.principal_daily_limit,
            ip_daily_limit=reservation.ip_daily_limit,
            state="reserved",
            created_at=reservation.now,
            updated_at=reservation.now,
        )
        self._session.add(row)
        self._session.flush()
        return _lease(row)

    def lease_for_job(
        self: AggregateReservationRepository,
        job_id: UUID,
    ) -> JobQuotaLease | None:
        row = self._ledger_row(job_id)
        return _lease(row) if row is not None else None

    def consume_for_job(
        self: AggregateReservationRepository,
        job_id: UUID,
        *,
        now: datetime,
    ) -> bool:
        row = self._ledger_row(job_id, lock=True)
        if row is None or row.state != "reserved":
            return False
        row.state = "consumed"
        row.updated_at = now
        row.consumed_at = now
        self._session.add(row)
        self._session.flush()
        return True

    def refund_for_job(
        self: AggregateReservationRepository,
        job_id: UUID,
        *,
        now: datetime,
    ) -> bool:
        row = self._ledger_row(job_id, lock=True)
        if row is None or row.state != "reserved":
            return False
        self._decrement(row.principal_type, row.principal_hash, row.usage_date)
        if row.ip_hash is not None:
            self._decrement("ip", row.ip_hash, row.usage_date)
        row.state = "refunded"
        row.updated_at = now
        row.refunded_at = now
        self._session.add(row)
        self._session.flush()
        return True

    def rereserve_for_job(
        self: AggregateReservationRepository,
        job_id: UUID,
        *,
        usage_date: date,
        principal_limit: int,
        ip_limit: int,
        now: datetime,
    ) -> bool:
        row = self._ledger_row(job_id, lock=True)
        if row is None or row.state != "refunded":
            return False
        reservation = JobQuotaReservation(
            job_id=job_id,
            principal_type=row.principal_type,
            principal_hash=row.principal_hash,
            ip_hash=row.ip_hash,
            usage_date=usage_date,
            principal_daily_limit=principal_limit,
            ip_daily_limit=ip_limit if row.ip_hash is not None else None,
            now=now,
        )
        self.reserve_many(job_aggregates(reservation))
        row.usage_date = usage_date
        row.principal_daily_limit = principal_limit
        row.ip_daily_limit = reservation.ip_daily_limit
        row.state = "reserved"
        row.updated_at = now
        row.consumed_at = None
        row.refunded_at = None
        self._session.add(row)
        self._session.flush()
        return True

    def _ledger_row(
        self: AggregateReservationRepository,
        job_id: UUID,
        *,
        lock: bool = False,
    ) -> AgentQuotaReservation | None:
        statement = select(AgentQuotaReservation).where(
            AgentQuotaReservation.job_id == job_id
        )
        if lock:
            statement = statement.with_for_update()
        return self._session.exec(statement).first()

    def _decrement(
        self: AggregateReservationRepository,
        principal_type: str,
        principal_hash: str,
        usage_date: date,
    ) -> None:
        statement = select(AgentDailyUsage).where(
            AgentDailyUsage.principal_type == principal_type,
            AgentDailyUsage.principal_hash == principal_hash,
            AgentDailyUsage.usage_date == usage_date,
        )
        row = self._session.exec(statement.with_for_update()).first()
        if row is None:
            return
        row.accepted_count = max(0, row.accepted_count - 1)
        self._session.add(row)


def job_aggregates(
    reservation: JobQuotaReservation,
) -> list[QuotaReservation]:
    aggregates = [
        QuotaReservation(
            reservation.principal_type,
            reservation.principal_hash,
            reservation.usage_date,
            reservation.principal_daily_limit,
        )
    ]
    if reservation.ip_hash is not None and reservation.ip_daily_limit is not None:
        aggregates.append(
            QuotaReservation(
                "ip",
                reservation.ip_hash,
                reservation.usage_date,
                reservation.ip_daily_limit,
            )
        )
    return aggregates


def _lease(row: AgentQuotaReservation) -> JobQuotaLease:
    return JobQuotaLease(
        job_id=row.job_id,
        principal_type=row.principal_type,
        principal_hash=row.principal_hash,
        ip_hash=row.ip_hash,
        usage_date=row.usage_date,
        principal_daily_limit=row.principal_daily_limit,
        ip_daily_limit=row.ip_daily_limit,
        state=row.state,
        created_at=row.created_at,
        updated_at=row.updated_at,
        consumed_at=row.consumed_at,
        refunded_at=row.refunded_at,
    )
