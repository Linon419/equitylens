from collections.abc import Generator
from dataclasses import dataclass, field

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.jobs.errors import JobDispatchError
from app.jobs.schemas import JobSubmission
from app.models.company_model import Company


@dataclass
class FakeJobBackend:
    calls: list[str] = field(default_factory=list)
    fail: bool = False

    async def enqueue(self, *, job_type: str, payload: dict) -> JobSubmission:
        job_id = str(payload["job_id"])
        self.calls.append(job_id)
        if self.fail:
            raise JobDispatchError("fake dispatch timeout", retryable=True)
        return JobSubmission(job_id=f"fake:{job_id}")


@pytest.fixture
def job_backend() -> FakeJobBackend:
    return FakeJobBackend()


@pytest.fixture
def job_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def job_company(job_session: Session) -> Company:
    company = Company(
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        exchange="Nasdaq",
    )
    job_session.add(company)
    job_session.commit()
    job_session.refresh(company)
    return company
