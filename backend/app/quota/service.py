from datetime import UTC, date, datetime, time, timedelta

from app.quota.errors import QuotaExceeded, QuotaRowLimitReached
from app.quota.identity import RequestPrincipal
from app.quota.repository import QuotaRepository, QuotaReservation
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
