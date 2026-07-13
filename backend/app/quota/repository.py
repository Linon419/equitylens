from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlmodel import Session, select

from app.models.job_model import AgentDailyUsage
from app.quota.errors import QuotaRowLimitReached


@dataclass(frozen=True)
class QuotaReservation:
    principal_type: str
    principal_hash: str
    usage_date: date
    daily_limit: int

    @property
    def key(self) -> tuple[str, str, date]:
        return self.principal_type, self.principal_hash, self.usage_date


class QuotaRepository(Protocol):
    def reserve_many(
        self,
        reservations: list[QuotaReservation],
    ) -> dict[tuple[str, str, date], int]: ...

    def get_count(
        self,
        principal_type: str,
        principal_hash: str,
        usage_date: date,
    ) -> int: ...


class InMemoryQuotaRepository:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str, date], int] = {}

    def reserve_many(
        self,
        reservations: list[QuotaReservation],
    ) -> dict[tuple[str, str, date], int]:
        for reservation in reservations:
            if self._counts.get(reservation.key, 0) >= reservation.daily_limit:
                raise QuotaRowLimitReached(reservation.principal_type)
        result = {}
        for reservation in reservations:
            used = self._counts.get(reservation.key, 0) + 1
            self._counts[reservation.key] = used
            result[reservation.key] = used
        return result

    def get_count(
        self,
        principal_type: str,
        principal_hash: str,
        usage_date: date,
    ) -> int:
        return self._counts.get((principal_type, principal_hash, usage_date), 0)


class SQLiteQuotaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def reserve_many(
        self,
        reservations: list[QuotaReservation],
    ) -> dict[tuple[str, str, date], int]:
        rows = {
            reservation.key: self._find(reservation)
            for reservation in reservations
        }
        for reservation in reservations:
            row = rows[reservation.key]
            if row is not None and row.accepted_count >= reservation.daily_limit:
                raise QuotaRowLimitReached(reservation.principal_type)
        result = {}
        current_time = datetime.now(UTC)
        for reservation in reservations:
            row = rows[reservation.key]
            if row is None:
                row = AgentDailyUsage(
                    principal_type=reservation.principal_type,
                    principal_hash=reservation.principal_hash,
                    usage_date=reservation.usage_date,
                    accepted_count=1,
                    daily_limit=reservation.daily_limit,
                    created_at=current_time,
                    updated_at=current_time,
                )
            else:
                row.accepted_count += 1
                row.daily_limit = reservation.daily_limit
                row.updated_at = current_time
            self._session.add(row)
            result[reservation.key] = row.accepted_count
        self._session.flush()
        return result

    def get_count(
        self,
        principal_type: str,
        principal_hash: str,
        usage_date: date,
    ) -> int:
        row = self._session.exec(
            select(AgentDailyUsage).where(
                AgentDailyUsage.principal_type == principal_type,
                AgentDailyUsage.principal_hash == principal_hash,
                AgentDailyUsage.usage_date == usage_date,
            )
        ).first()
        return 0 if row is None else row.accepted_count

    def _find(self, reservation: QuotaReservation) -> AgentDailyUsage | None:
        return self._session.exec(
            select(AgentDailyUsage).where(
                AgentDailyUsage.principal_type == reservation.principal_type,
                AgentDailyUsage.principal_hash == reservation.principal_hash,
                AgentDailyUsage.usage_date == reservation.usage_date,
            )
        ).first()


class PostgresQuotaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def reserve_many(
        self,
        reservations: list[QuotaReservation],
    ) -> dict[tuple[str, str, date], int]:
        result = {}
        for reservation in reservations:
            statement = build_postgres_reservation_statement(
                principal_type=reservation.principal_type,
                principal_hash=reservation.principal_hash,
                usage_date=reservation.usage_date,
                daily_limit=reservation.daily_limit,
            )
            used = self._session.execute(statement).scalar_one_or_none()
            if used is None:
                self._session.rollback()
                raise QuotaRowLimitReached(reservation.principal_type)
            result[reservation.key] = used
        return result

    def get_count(
        self,
        principal_type: str,
        principal_hash: str,
        usage_date: date,
    ) -> int:
        row = self._session.exec(
            select(AgentDailyUsage).where(
                AgentDailyUsage.principal_type == principal_type,
                AgentDailyUsage.principal_hash == principal_hash,
                AgentDailyUsage.usage_date == usage_date,
            )
        ).first()
        return 0 if row is None else row.accepted_count


def build_postgres_reservation_statement(
    *,
    principal_type: str,
    principal_hash: str,
    usage_date: date,
    daily_limit: int,
):
    current_time = datetime.now(UTC)
    statement = postgres_insert(AgentDailyUsage).values(
        principal_type=principal_type,
        principal_hash=principal_hash,
        usage_date=usage_date,
        accepted_count=1,
        daily_limit=daily_limit,
        created_at=current_time,
        updated_at=current_time,
    )
    return statement.on_conflict_do_update(
        index_elements=["principal_type", "principal_hash", "usage_date"],
        set_={
            "accepted_count": AgentDailyUsage.accepted_count + 1,
            "daily_limit": statement.excluded.daily_limit,
            "updated_at": current_time,
        },
        where=AgentDailyUsage.accepted_count < daily_limit,
    ).returning(AgentDailyUsage.accepted_count)
