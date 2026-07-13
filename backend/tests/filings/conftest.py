import json
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.company_model import Company

FIXTURES = Path(__file__).parents[1] / "fixtures" / "sec"


@pytest.fixture
def submissions() -> dict:
    return json.loads((FIXTURES / "aapl_submissions.json").read_text())


@pytest.fixture
def filing_html() -> bytes:
    return (FIXTURES / "aapl_10k_excerpt.html").read_bytes()


@pytest.fixture
def filing_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def filing_company(filing_session: Session) -> Company:
    company = Company(
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        exchange="Nasdaq",
    )
    filing_session.add(company)
    filing_session.commit()
    filing_session.refresh(company)
    return company
