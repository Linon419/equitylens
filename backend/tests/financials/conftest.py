import json
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.company_model import Company

FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "sec" / "aapl_companyfacts.json"
)


@pytest.fixture
def company_facts() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture
def financial_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def apple(financial_session: Session) -> Company:
    company = Company(
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        exchange="Nasdaq",
    )
    financial_session.add(company)
    financial_session.commit()
    financial_session.refresh(company)
    return company
