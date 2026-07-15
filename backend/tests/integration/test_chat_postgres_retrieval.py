import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app.chat.retrieval import SqlFilingChunkRepository
from app.models.chat_model import FilingChunk
from app.models.company_model import Company
from app.models.research_model import Filing, FilingSection


@pytest.mark.postgres
def test_postgres_retrieval_filters_company_and_filing() -> None:
    database_url = os.getenv("TEST_POSTGRES_URL")
    if database_url is None:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    sync_url = make_url(database_url).set(drivername="postgresql+psycopg2")
    admin_engine = create_engine(sync_url)
    schema = f"chat_retrieval_{uuid4().hex}"
    schema_engine = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_engine = create_engine(
            sync_url,
            connect_args={"options": f"-csearch_path={schema},public"},
        )
        SQLModel.metadata.create_all(schema_engine)
        with Session(schema_engine) as session:
            company = Company(
                id=1,
                symbol="AAPL",
                cik="0000320193",
                name="Apple Inc.",
            )
            other = Company(
                id=2,
                symbol="MSFT",
                cik="0000789019",
                name="Microsoft Corp.",
            )
            session.add_all([company, other])
            session.flush()
            filing = _filing(session, 1, "aapl")
            other_filing = _filing(session, 2, "msft")
            _chunk(session, filing, "Services revenue increased", [0.1] * 1_536)
            _chunk(session, other_filing, "Services revenue increased", [0.1] * 1_536)
            session.commit()
            repository = SqlFilingChunkRepository(session)

            fts = repository.full_text_candidates(
                company_id=1,
                filing_id=filing.id,
                query="services revenue",
                limit=20,
            )
            vector = repository.vector_candidates(
                company_id=1,
                filing_id=filing.id,
                embedding=[0.1] * 1_536,
                limit=20,
            )

            assert len(fts) == 1
            assert len(vector) == 1
            assert fts[0].id == vector[0].id
    finally:
        if schema_engine is not None:
            schema_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def _filing(session: Session, company_id: int, key: str) -> Filing:
    filing = Filing(
        company_id=company_id,
        accession_number=f"0000000000-25-{company_id:06d}",
        form="10-K",
        filed_at=date(2025, 1, company_id),
        report_date=date(2024, 12, 31),
        primary_document=f"{key}.htm",
        source_url=f"https://www.sec.gov/{key}.htm",
    )
    session.add(filing)
    session.flush()
    return filing


def _chunk(
    session: Session,
    filing: Filing,
    body: str,
    embedding: list[float],
) -> FilingChunk:
    section = FilingSection(
        filing_id=filing.id,
        heading="Business",
        source_anchor="item-1",
        ordinal=0,
        text=body,
    )
    session.add(section)
    session.flush()
    chunk = FilingChunk(
        company_id=filing.company_id,
        filing_id=filing.id,
        section_id=section.id,
        ordinal=0,
        text=body,
        token_count=3,
        content_hash="a" * 64,
        chunk_schema_version="filing-chunk.v1",
        embedding_model="text-embedding-3-small",
        embedding=embedding,
    )
    session.add(chunk)
    return chunk
