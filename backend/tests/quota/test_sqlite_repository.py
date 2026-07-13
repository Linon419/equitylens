from datetime import date

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.quota.errors import QuotaExceeded
from app.quota.identity import RequestPrincipal
from app.quota.repository import SQLiteQuotaRepository
from app.quota.service import get_quota, reserve_analysis


def test_sqlite_repository_preserves_atomic_guest_and_ip_counts() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    usage_date = date(2026, 7, 13)
    with Session(engine) as session:
        repository = SQLiteQuotaRepository(session)
        for index in range(10):
            reserve_analysis(
                repository,
                RequestPrincipal.guest(f"guest-{index}", "shared-ip"),
                usage_date=usage_date,
            )

        blocked = RequestPrincipal.guest("blocked-guest", "shared-ip")
        with pytest.raises(QuotaExceeded):
            reserve_analysis(repository, blocked, usage_date=usage_date)

        assert get_quota(repository, blocked, usage_date).used == 0
