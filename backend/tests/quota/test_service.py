from datetime import date

import pytest

from app.quota.errors import QuotaExceeded
from app.quota.identity import RequestPrincipal
from app.quota.repository import InMemoryQuotaRepository
from app.quota.service import get_quota, reserve_analysis

USAGE_DATE = date(2026, 7, 13)


def test_guest_receives_two_daily_analyses() -> None:
    repository = InMemoryQuotaRepository()
    guest = RequestPrincipal.guest("guest-hash", "ip-hash")

    first = reserve_analysis(repository, guest, usage_date=USAGE_DATE)
    second = reserve_analysis(repository, guest, usage_date=USAGE_DATE)

    assert (first.remaining, second.remaining) == (1, 0)
    with pytest.raises(QuotaExceeded) as error:
        reserve_analysis(repository, guest, usage_date=USAGE_DATE)
    assert error.value.code == "AGENT_DAILY_QUOTA_EXCEEDED"


def test_user_quota_resets_on_the_next_utc_day() -> None:
    repository = InMemoryQuotaRepository()
    user = RequestPrincipal.user(42, "q" * 32)

    for _ in range(10):
        reserve_analysis(repository, user, usage_date=USAGE_DATE)

    assert get_quota(repository, user, date(2026, 7, 14)).remaining == 10


def test_ip_guardrail_is_atomic_across_guest_ids() -> None:
    repository = InMemoryQuotaRepository()
    for index in range(10):
        reserve_analysis(
            repository,
            RequestPrincipal.guest(f"guest-{index}", "shared-ip"),
            usage_date=USAGE_DATE,
        )

    final_guest = RequestPrincipal.guest("guest-10", "shared-ip")
    with pytest.raises(QuotaExceeded) as error:
        reserve_analysis(repository, final_guest, usage_date=USAGE_DATE)

    assert error.value.code == "AGENT_IP_DAILY_QUOTA_EXCEEDED"
    assert get_quota(repository, final_guest, USAGE_DATE).remaining == 2
