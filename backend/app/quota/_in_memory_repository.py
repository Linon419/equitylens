from dataclasses import replace
from datetime import date, datetime
from threading import RLock
from uuid import UUID

from app.quota.errors import QuotaRowLimitReached
from app.quota.ledger import (
    JobQuotaLease,
    JobQuotaReservation,
    QuotaReservation,
    job_aggregates,
)


class InMemoryQuotaRepository:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str, date], int] = {}
        self._leases: dict[UUID, JobQuotaLease] = {}
        self._lock = RLock()

    def reserve_many(
        self,
        reservations: list[QuotaReservation],
    ) -> dict[tuple[str, str, date], int]:
        with self._lock:
            return self._reserve_many(reservations)

    def reserve_for_job(
        self,
        reservation: JobQuotaReservation,
    ) -> JobQuotaLease:
        with self._lock:
            existing = self._leases.get(reservation.job_id)
            if existing is not None:
                return existing
            self._reserve_many(job_aggregates(reservation))
            lease = JobQuotaLease(
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
            self._leases[reservation.job_id] = lease
            return lease

    def lease_for_job(self, job_id: UUID) -> JobQuotaLease | None:
        with self._lock:
            return self._leases.get(job_id)

    def consume_for_job(self, job_id: UUID, *, now: datetime) -> bool:
        with self._lock:
            lease = self._leases.get(job_id)
            if lease is None or lease.state != "reserved":
                return False
            self._leases[job_id] = replace(
                lease,
                state="consumed",
                updated_at=now,
                consumed_at=now,
            )
            return True

    def refund_for_job(self, job_id: UUID, *, now: datetime) -> bool:
        with self._lock:
            lease = self._leases.get(job_id)
            if lease is None or lease.state != "reserved":
                return False
            self._decrement(
                lease.principal_type,
                lease.principal_hash,
                lease.usage_date,
            )
            if lease.ip_hash is not None:
                self._decrement("ip", lease.ip_hash, lease.usage_date)
            self._leases[job_id] = replace(
                lease,
                state="refunded",
                updated_at=now,
                refunded_at=now,
            )
            return True

    def rereserve_for_job(
        self,
        job_id: UUID,
        *,
        usage_date: date,
        principal_limit: int,
        ip_limit: int,
        now: datetime,
    ) -> bool:
        with self._lock:
            lease = self._leases.get(job_id)
            if lease is None or lease.state != "refunded":
                return False
            reservation = JobQuotaReservation(
                job_id=job_id,
                principal_type=lease.principal_type,
                principal_hash=lease.principal_hash,
                ip_hash=lease.ip_hash,
                usage_date=usage_date,
                principal_daily_limit=principal_limit,
                ip_daily_limit=ip_limit if lease.ip_hash is not None else None,
                now=now,
            )
            self._reserve_many(job_aggregates(reservation))
            self._leases[job_id] = replace(
                lease,
                usage_date=usage_date,
                principal_daily_limit=principal_limit,
                ip_daily_limit=reservation.ip_daily_limit,
                state="reserved",
                updated_at=now,
                consumed_at=None,
                refunded_at=None,
            )
            return True

    def get_count(
        self,
        principal_type: str,
        principal_hash: str,
        usage_date: date,
    ) -> int:
        with self._lock:
            return self._counts.get(
                (principal_type, principal_hash, usage_date),
                0,
            )

    def _reserve_many(
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

    def _decrement(
        self,
        principal_type: str,
        principal_hash: str,
        usage_date: date,
    ) -> None:
        key = principal_type, principal_hash, usage_date
        self._counts[key] = max(0, self._counts.get(key, 0) - 1)
