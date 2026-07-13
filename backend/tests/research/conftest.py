import json
from collections.abc import Generator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.company_model import Company
from app.models.research_model import Filing, FilingSection
from app.research.schemas import EvidenceBundle, EvidenceSection

FIXTURES = Path(__file__).parents[1] / "fixtures" / "research"


@pytest.fixture
def draft_payload() -> dict:
    return json.loads((FIXTURES / "aapl_draft.json").read_text())


@pytest.fixture
def verification_payload() -> dict:
    return json.loads((FIXTURES / "aapl_verification.json").read_text())


@pytest.fixture
def evidence_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        symbol="AAPL",
        company_name="Apple Inc.",
        sections=[
            EvidenceSection(
                section_id="section-business",
                heading="Item 1. Business",
                source_anchor="item-1-business",
                source_url="https://www.sec.gov/example#item-1-business",
                text=(
                    "The Company designs, manufactures and markets smartphones "
                    "and personal computers."
                ),
            ),
            EvidenceSection(
                section_id="section-risk",
                heading="Item 1A. Risk Factors",
                source_anchor="item-1a-risk-factors",
                source_url="https://www.sec.gov/example#item-1a-risk-factors",
                text=(
                    "Manufacturing and supply concentration may disrupt "
                    "product availability."
                ),
            ),
        ],
    )


@pytest.fixture
def research_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def research_records(research_session: Session) -> tuple[Company, Filing]:
    company = Company(
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        exchange="Nasdaq",
    )
    research_session.add(company)
    research_session.commit()
    research_session.refresh(company)
    filing = Filing(
        company_id=company.id,
        accession_number="0000320193-25-000079",
        form="10-K",
        fiscal_period="FY2025",
        filed_at=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        primary_document="aapl-20250927.htm",
        source_url="https://www.sec.gov/example/aapl-20250927.htm",
        content_hash="a" * 64,
    )
    research_session.add(filing)
    research_session.commit()
    research_session.refresh(filing)
    research_session.add(
        FilingSection(
            filing_id=filing.id,
            heading="Item 1. Business",
            source_anchor="item-1-business",
            ordinal=0,
            text=(
                "The Company designs, manufactures and markets smartphones "
                "and personal computers."
            ),
        )
    )
    research_session.commit()
    return company, filing
