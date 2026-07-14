import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier
from uuid import UUID

import pytest
from sqlalchemy import delete
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine, select

import app.models  # noqa: F401
from app.models.company_model import Company
from app.models.job_model import AgentDailyUsage, IngestionJob
from app.models.supply_chain_model import AgentQuotaReservation
from app.quota.errors import QuotaExceeded
from app.quota.identity import RequestPrincipal
from app.quota.repository import (
    PostgresQuotaRepository,
    build_postgres_reservation_statement,
)
from app.quota.service import (
    refund_job_analysis,
    reserve_analysis,
    reserve_job_analysis,
)

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
JOB_ID = UUID("00000000-0000-0000-0000-000000000301")
NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)


def test_postgres_reservation_uses_conditional_upsert_and_returning() -> None:
    statement = build_postgres_reservation_statement(
        principal_type="guest",
        principal_hash="guest-hash",
        usage_date=date(2026, 7, 13),
        daily_limit=2,
    )

    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "ON CONFLICT" in sql
    assert "accepted_count <" in sql
    assert "RETURNING" in sql


@pytest.mark.postgres
@pytest.mark.skipif(POSTGRES_URL is None, reason="TEST_POSTGRES_URL is unset")
def test_concurrent_reservations_stop_at_limit() -> None:
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL)
    AgentDailyUsage.__table__.create(engine, checkfirst=True)
    session_factory = sessionmaker(bind=engine, class_=Session)
    usage_date = date(2026, 7, 13)
    principal = RequestPrincipal.guest("concurrent-guest", "concurrent-ip")
    _delete_test_rows(session_factory, usage_date)
    barrier = Barrier(4)

    def reserve() -> str:
        with session_factory() as session:
            barrier.wait()
            try:
                reserve_analysis(
                    PostgresQuotaRepository(session),
                    principal,
                    usage_date=usage_date,
                )
                session.commit()
            except QuotaExceeded:
                return "exceeded"
            return "accepted"

    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: reserve(), range(4)))

        assert results.count("accepted") == 2
        assert results.count("exceeded") == 2
        with session_factory() as session:
            stored = session.exec(
                select(AgentDailyUsage).where(
                    AgentDailyUsage.principal_type == "guest",
                    AgentDailyUsage.principal_hash == "concurrent-guest",
                    AgentDailyUsage.usage_date == usage_date,
                )
            ).one()
        assert stored.accepted_count == 2
    finally:
        _delete_test_rows(session_factory, usage_date)
        engine.dispose()


@pytest.mark.postgres
@pytest.mark.skipif(POSTGRES_URL is None, reason="TEST_POSTGRES_URL is unset")
def test_concurrent_job_refunds_decrement_aggregate_once() -> None:
    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL)
    SQLModel.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, class_=Session)
    guest = RequestPrincipal.guest("refund-guest", "refund-ip")
    _delete_job_rows(session_factory)
    with session_factory() as session:
        company = Company(
            symbol="QRFD",
            cik="0000000301",
            name="Quota Refund Test",
        )
        session.add(company)
        session.commit()
        session.refresh(company)
        job = IngestionJob(
            id=JOB_ID,
            job_type="supply_chain_graph",
            company_id=company.id,
            requested_by_type="guest",
            requested_by_hash=guest.principal_hash,
            deduplication_key="supply-chain-graph:refund-concurrency",
            state="queued",
            current_step="queued",
            created_at=NOW,
            updated_at=NOW,
        )
        session.add(job)
        session.commit()
        reserve_job_analysis(
            PostgresQuotaRepository(session),
            guest,
            JOB_ID,
            NOW.date(),
        )
        session.commit()
    barrier = Barrier(2)

    def refund() -> bool:
        with session_factory() as session:
            barrier.wait()
            changed = refund_job_analysis(
                PostgresQuotaRepository(session),
                JOB_ID,
                now=NOW,
            )
            session.commit()
            return changed

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: refund(), range(2)))

        assert sorted(results) == [False, True]
        with session_factory() as session:
            ledger = session.exec(
                select(AgentQuotaReservation).where(
                    AgentQuotaReservation.job_id == JOB_ID
                )
            ).one()
            usage = session.exec(
                select(AgentDailyUsage).where(
                    AgentDailyUsage.principal_type == "guest",
                    AgentDailyUsage.principal_hash == guest.principal_hash,
                    AgentDailyUsage.usage_date == NOW.date(),
                )
            ).one()
        assert ledger.state == "refunded"
        assert usage.accepted_count == 0
    finally:
        _delete_job_rows(session_factory)
        engine.dispose()


def _delete_test_rows(session_factory, usage_date: date) -> None:
    with session_factory() as session:
        session.execute(
            delete(AgentDailyUsage).where(
                AgentDailyUsage.usage_date == usage_date,
                AgentDailyUsage.principal_hash.in_(
                    ["concurrent-guest", "concurrent-ip"]
                ),
            )
        )
        session.commit()


def _delete_job_rows(session_factory) -> None:
    with session_factory() as session:
        session.execute(
            delete(AgentQuotaReservation).where(AgentQuotaReservation.job_id == JOB_ID)
        )
        session.execute(delete(IngestionJob).where(IngestionJob.id == JOB_ID))
        session.execute(
            delete(AgentDailyUsage).where(
                AgentDailyUsage.principal_hash.in_(["refund-guest", "refund-ip"])
            )
        )
        session.execute(delete(Company).where(Company.symbol == "QRFD"))
        session.commit()
