from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.company_model import Company
from app.models.job_model import AgentDailyUsage, IngestionJob
from app.models.supply_chain_model import AgentQuotaReservation
from app.quota.errors import QuotaExceeded
from app.quota.identity import RequestPrincipal
from app.quota.repository import SQLiteQuotaRepository
from app.quota.service import (
    consume_job_analysis,
    get_quota,
    refund_job_analysis,
    rereserve_job_analysis,
    reserve_analysis,
    reserve_job_analysis,
)

TODAY = date(2026, 7, 13)
NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)
TOMORROW = datetime(2026, 7, 14, 12, tzinfo=UTC)
JOB_ID = UUID("00000000-0000-0000-0000-000000000201")
GUEST = RequestPrincipal.guest("sqlite-guest", "sqlite-ip")


def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_foreign_keys)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as current:
        company = Company(symbol="AAPL", cik="0000320193", name="Apple Inc.")
        current.add(company)
        current.commit()
        yield current


def add_job(session: Session, job_id: UUID = JOB_ID) -> IngestionJob:
    job = IngestionJob(
        id=job_id,
        job_type="supply_chain_graph",
        company_id=1,
        requested_by_type="guest",
        requested_by_hash=GUEST.principal_hash,
        deduplication_key=f"supply-chain-graph:{job_id}",
        state="queued",
        current_step="queued",
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(job)
    session.commit()
    return job


def test_sqlite_repository_preserves_atomic_guest_and_ip_counts(
    session: Session,
) -> None:
    repository = SQLiteQuotaRepository(session)
    for index in range(10):
        reserve_analysis(
            repository,
            RequestPrincipal.guest(f"guest-{index}", "shared-ip"),
            usage_date=TODAY,
        )

    blocked = RequestPrincipal.guest("blocked-guest", "shared-ip")
    with pytest.raises(QuotaExceeded):
        reserve_analysis(repository, blocked, usage_date=TODAY)

    assert get_quota(repository, blocked, TODAY).used == 0


def test_sqlite_job_refund_updates_ledger_and_aggregates_once(
    session: Session,
) -> None:
    add_job(session)
    repository = SQLiteQuotaRepository(session)
    reserve_job_analysis(repository, GUEST, JOB_ID, TODAY)
    session.commit()

    assert refund_job_analysis(repository, JOB_ID, now=NOW) is True
    assert refund_job_analysis(repository, JOB_ID, now=NOW) is False
    session.commit()

    ledger = session.exec(
        select(AgentQuotaReservation).where(AgentQuotaReservation.job_id == JOB_ID)
    ).one()
    assert ledger.state == "refunded"
    assert ledger.refunded_at is not None
    assert get_quota(repository, GUEST, TODAY).used == 0
    ip_count = repository.get_count("ip", GUEST.ip_hash, TODAY)
    assert ip_count == 0


def test_sqlite_consumed_job_keeps_reserved_usage(
    session: Session,
) -> None:
    add_job(session)
    repository = SQLiteQuotaRepository(session)
    reserve_job_analysis(repository, GUEST, JOB_ID, TODAY)

    assert consume_job_analysis(repository, JOB_ID, now=NOW) is True
    assert consume_job_analysis(repository, JOB_ID, now=NOW) is False
    assert refund_job_analysis(repository, JOB_ID, now=NOW) is False
    session.commit()

    assert repository.lease_for_job(JOB_ID).state == "consumed"
    assert get_quota(repository, GUEST, TODAY).used == 1


def test_sqlite_rereservation_can_move_to_next_utc_day(
    session: Session,
) -> None:
    add_job(session)
    repository = SQLiteQuotaRepository(session)
    reserve_job_analysis(repository, GUEST, JOB_ID, TODAY)
    refund_job_analysis(repository, JOB_ID, now=NOW)

    assert rereserve_job_analysis(repository, JOB_ID, now=TOMORROW) is True
    session.commit()

    lease = repository.lease_for_job(JOB_ID)
    assert lease is not None
    assert lease.state == "reserved"
    assert lease.usage_date == TOMORROW.date()
    assert get_quota(repository, GUEST, TODAY).used == 0
    assert get_quota(repository, GUEST, TOMORROW.date()).used == 1


def test_sqlite_caller_rollback_removes_lease_and_usage(
    session: Session,
) -> None:
    add_job(session)
    repository = SQLiteQuotaRepository(session)
    reserve_job_analysis(repository, GUEST, JOB_ID, TODAY)

    assert session.exec(select(AgentQuotaReservation)).one().state == "reserved"
    session.rollback()

    assert repository.lease_for_job(JOB_ID) is None
    assert session.exec(select(AgentDailyUsage)).all() == []


def test_sqlite_unknown_job_transitions_are_noops(session: Session) -> None:
    repository = SQLiteQuotaRepository(session)

    assert consume_job_analysis(repository, JOB_ID, now=NOW) is False
    assert refund_job_analysis(repository, JOB_ID, now=NOW) is False
    assert rereserve_job_analysis(repository, JOB_ID, now=NOW) is False
