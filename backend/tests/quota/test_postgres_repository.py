import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from sqlalchemy import delete
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine, select

from app.models.job_model import AgentDailyUsage
from app.quota.errors import QuotaExceeded
from app.quota.identity import RequestPrincipal
from app.quota.repository import (
    PostgresQuotaRepository,
    build_postgres_reservation_statement,
)
from app.quota.service import reserve_analysis

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


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
