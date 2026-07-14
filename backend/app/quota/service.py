from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from app.quota.errors import QuotaExceeded, QuotaRowLimitReached
from app.quota.identity import RequestPrincipal
from app.quota.repository import (
    JobQuotaLease,
    JobQuotaReservation,
    QuotaRepository,
    QuotaReservation,
)
from app.quota.schemas import QuotaStatus

GUEST_DAILY_LIMIT = 2
USER_DAILY_LIMIT = 10
IP_DAILY_LIMIT = 10


def reserve_analysis(
    repository: QuotaRepository,
    principal: RequestPrincipal,
    *,
    usage_date: date,
    guest_limit: int = GUEST_DAILY_LIMIT,
    user_limit: int = USER_DAILY_LIMIT,
    ip_limit: int = IP_DAILY_LIMIT,
) -> QuotaStatus:
    limit = guest_limit if principal.principal_type == "guest" else user_limit
    primary = QuotaReservation(
        principal.principal_type,
        principal.principal_hash,
        usage_date,
        limit,
    )
    reservations = [primary]
    if principal.principal_type == "guest" and principal.ip_hash is not None:
        reservations.append(
            QuotaReservation("ip", principal.ip_hash, usage_date, ip_limit)
        )
    try:
        counts = repository.reserve_many(reservations)
    except QuotaRowLimitReached as error:
        code = (
            "AGENT_IP_DAILY_QUOTA_EXCEEDED"
            if error.principal_type == "ip"
            else "AGENT_DAILY_QUOTA_EXCEEDED"
        )
        raise QuotaExceeded(code) from error
    return _status(limit, counts[primary.key], usage_date)


def get_quota(
    repository: QuotaRepository,
    principal: RequestPrincipal,
    usage_date: date,
    *,
    guest_limit: int = GUEST_DAILY_LIMIT,
    user_limit: int = USER_DAILY_LIMIT,
) -> QuotaStatus:
    limit = guest_limit if principal.principal_type == "guest" else user_limit
    used = repository.get_count(
        principal.principal_type,
        principal.principal_hash,
        usage_date,
    )
    return _status(limit, used, usage_date)


def reserve_job_analysis(
    repository: QuotaRepository,
    principal: RequestPrincipal,
    job_id: UUID,
    usage_date: date,
    *,
    guest_limit: int = GUEST_DAILY_LIMIT,
    user_limit: int = USER_DAILY_LIMIT,
    ip_limit: int = IP_DAILY_LIMIT,
) -> tuple[JobQuotaLease, QuotaStatus]:
    limit = guest_limit if principal.principal_type == "guest" else user_limit
    reservation = JobQuotaReservation(
        job_id=job_id,
        principal_type=principal.principal_type,
        principal_hash=principal.principal_hash,
        ip_hash=principal.ip_hash,
        usage_date=usage_date,
        principal_daily_limit=limit,
        ip_daily_limit=ip_limit if principal.ip_hash is not None else None,
    )
    try:
        lease = repository.reserve_for_job(reservation)
    except QuotaRowLimitReached as error:
        raise _quota_exceeded(error) from error
    return lease, get_quota(
        repository,
        principal,
        usage_date,
        guest_limit=guest_limit,
        user_limit=user_limit,
    )


def consume_job_analysis(
    repository: QuotaRepository,
    job_id: UUID,
    *,
    now: datetime,
) -> bool:
    return repository.consume_for_job(job_id, now=_as_utc(now))


def refund_job_analysis(
    repository: QuotaRepository,
    job_id: UUID,
    *,
    now: datetime,
) -> bool:
    return repository.refund_for_job(job_id, now=_as_utc(now))


def rereserve_job_analysis(
    repository: QuotaRepository,
    job_id: UUID,
    *,
    now: datetime,
    guest_limit: int = GUEST_DAILY_LIMIT,
    user_limit: int = USER_DAILY_LIMIT,
    ip_limit: int = IP_DAILY_LIMIT,
) -> bool:
    lease = repository.lease_for_job(job_id)
    if lease is None:
        return False
    limit = guest_limit if lease.principal_type == "guest" else user_limit
    current_time = _as_utc(now)
    try:
        return repository.rereserve_for_job(
            job_id,
            usage_date=current_time.date(),
            principal_limit=limit,
            ip_limit=ip_limit,
            now=current_time,
        )
    except QuotaRowLimitReached as error:
        raise _quota_exceeded(error) from error


def _status(limit: int, used: int, usage_date: date) -> QuotaStatus:
    resets_at = datetime.combine(
        usage_date + timedelta(days=1),
        time.min,
        tzinfo=UTC,
    )
    return QuotaStatus(
        limit=limit,
        used=used,
        remaining=max(0, limit - used),
        resets_at=resets_at,
    )


def _quota_exceeded(error: QuotaRowLimitReached) -> QuotaExceeded:
    code = (
        "AGENT_IP_DAILY_QUOTA_EXCEEDED"
        if error.principal_type == "ip"
        else "AGENT_DAILY_QUOTA_EXCEEDED"
    )
    return QuotaExceeded(code)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
