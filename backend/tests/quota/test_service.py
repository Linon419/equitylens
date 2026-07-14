from datetime import UTC, date, datetime
from uuid import UUID

import pytest

from app.quota.errors import QuotaExceeded
from app.quota.identity import RequestPrincipal
from app.quota.repository import InMemoryQuotaRepository
from app.quota.service import (
    consume_job_analysis,
    get_quota,
    refund_job_analysis,
    rereserve_job_analysis,
    reserve_analysis,
    reserve_job_analysis,
)

USAGE_DATE = date(2026, 7, 13)
NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)
NEXT_DAY = datetime(2026, 7, 14, 12, tzinfo=UTC)
JOB_ID = UUID("00000000-0000-0000-0000-000000000101")


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


def test_job_refund_is_idempotent_and_restores_guest_quota() -> None:
    repository = InMemoryQuotaRepository()
    guest = RequestPrincipal.guest("guest-hash", "ip-hash")

    lease, status = reserve_job_analysis(
        repository,
        guest,
        JOB_ID,
        USAGE_DATE,
    )

    assert lease.job_id == JOB_ID
    assert status.used == 1
    assert refund_job_analysis(repository, JOB_ID, now=NOW) is True
    assert refund_job_analysis(repository, JOB_ID, now=NOW) is False
    assert get_quota(repository, guest, USAGE_DATE).used == 0


def test_consumed_job_cannot_be_refunded() -> None:
    repository = InMemoryQuotaRepository()
    guest = RequestPrincipal.guest("guest-hash", "ip-hash")
    reserve_job_analysis(repository, guest, JOB_ID, USAGE_DATE)

    assert consume_job_analysis(repository, JOB_ID, now=NOW) is True
    assert consume_job_analysis(repository, JOB_ID, now=NOW) is False
    assert refund_job_analysis(repository, JOB_ID, now=NOW) is False
    assert get_quota(repository, guest, USAGE_DATE).used == 1


def test_refunded_job_can_be_rereserved_once() -> None:
    repository = InMemoryQuotaRepository()
    guest = RequestPrincipal.guest("guest-hash", "ip-hash")
    reserve_job_analysis(repository, guest, JOB_ID, USAGE_DATE)
    refund_job_analysis(repository, JOB_ID, now=NOW)

    assert rereserve_job_analysis(repository, JOB_ID, now=NOW) is True
    assert rereserve_job_analysis(repository, JOB_ID, now=NOW) is False
    assert get_quota(repository, guest, USAGE_DATE).used == 1


def test_user_job_reservation_has_no_ip_aggregate() -> None:
    repository = InMemoryQuotaRepository()
    user = RequestPrincipal.user(42, "q" * 32)

    lease, status = reserve_job_analysis(
        repository,
        user,
        JOB_ID,
        USAGE_DATE,
    )

    assert lease.ip_hash is None
    assert lease.principal_daily_limit == 10
    assert status.remaining == 9


def test_job_ip_guardrail_does_not_charge_blocked_guest() -> None:
    repository = InMemoryQuotaRepository()
    for index in range(10):
        reserve_job_analysis(
            repository,
            RequestPrincipal.guest(f"guest-{index}", "shared-ip"),
            UUID(int=index + 1000),
            USAGE_DATE,
        )
    blocked = RequestPrincipal.guest("blocked-guest", "shared-ip")

    with pytest.raises(QuotaExceeded) as error:
        reserve_job_analysis(
            repository,
            blocked,
            UUID(int=2000),
            USAGE_DATE,
        )

    assert error.value.code == "AGENT_IP_DAILY_QUOTA_EXCEEDED"
    assert get_quota(repository, blocked, USAGE_DATE).used == 0


def test_refunded_job_can_move_to_a_new_usage_date() -> None:
    repository = InMemoryQuotaRepository()
    guest = RequestPrincipal.guest("guest-hash", "ip-hash")
    reserve_job_analysis(repository, guest, JOB_ID, USAGE_DATE)
    refund_job_analysis(repository, JOB_ID, now=NOW)

    assert rereserve_job_analysis(repository, JOB_ID, now=NEXT_DAY) is True
    assert get_quota(repository, guest, USAGE_DATE).used == 0
    assert get_quota(repository, guest, NEXT_DAY.date()).used == 1


def test_unknown_job_transitions_are_noops() -> None:
    repository = InMemoryQuotaRepository()

    assert consume_job_analysis(repository, JOB_ID, now=NOW) is False
    assert refund_job_analysis(repository, JOB_ID, now=NOW) is False
    assert rereserve_job_analysis(repository, JOB_ID, now=NOW) is False


def test_duplicate_job_reservation_counts_once() -> None:
    repository = InMemoryQuotaRepository()
    guest = RequestPrincipal.guest("guest-hash", "ip-hash")

    first, _ = reserve_job_analysis(repository, guest, JOB_ID, USAGE_DATE)
    second, status = reserve_job_analysis(repository, guest, JOB_ID, USAGE_DATE)

    assert first == second
    assert status.used == 1


def test_rereservation_at_new_limit_keeps_refunded_state() -> None:
    repository = InMemoryQuotaRepository()
    guest = RequestPrincipal.guest("guest-hash", "ip-hash")
    reserve_job_analysis(repository, guest, JOB_ID, USAGE_DATE)
    refund_job_analysis(repository, JOB_ID, now=NOW)
    for value in (102, 103):
        reserve_job_analysis(
            repository,
            guest,
            UUID(int=value),
            USAGE_DATE,
        )

    with pytest.raises(QuotaExceeded) as error:
        rereserve_job_analysis(repository, JOB_ID, now=NOW)

    assert error.value.code == "AGENT_DAILY_QUOTA_EXCEEDED"
    assert repository.lease_for_job(JOB_ID).state == "refunded"
    assert get_quota(repository, guest, USAGE_DATE).used == 2
