from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pytest
from sqlmodel import select

from app.chat.indexing import FilingIndexService
from app.core.errors import DomainError
from app.models.chat_model import FilingChunk
from app.models.research_model import Filing, FilingSection
from tests.chat.test_chunker import WhitespaceCodec, token_text

NOW = datetime(2026, 7, 15, 10, tzinfo=UTC)


@dataclass
class FakeEmbeddingProvider:
    model_id: str = "text-embedding-3-small"
    dimensions: int = 1_536
    batches: list[list[str]] = field(default_factory=list)
    returned_dimensions: int | None = None

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(texts)
        dimensions = self.returned_dimensions or self.dimensions
        return [[float(index + 1)] * dimensions for index, _text in enumerate(texts)]

    async def embed_query(self, text: str) -> list[float]:
        return [1.0] * self.dimensions


def add_filing(
    session,
    *,
    accession: str,
    filed_at: date,
    sections: list[tuple[str, str]],
) -> Filing:
    filing = Filing(
        company_id=1,
        accession_number=accession,
        form="10-K",
        fiscal_period="FY2025",
        filed_at=filed_at,
        report_date=filed_at,
        primary_document="aapl.htm",
        source_url=f"https://www.sec.gov/{accession}",
    )
    session.add(filing)
    session.flush()
    for ordinal, (heading, text) in enumerate(sections):
        session.add(
            FilingSection(
                filing_id=filing.id,
                heading=heading,
                source_anchor=f"section-{ordinal}",
                ordinal=ordinal,
                text=text,
            )
        )
    session.commit()
    return filing


def service(session, embeddings: FakeEmbeddingProvider) -> FilingIndexService:
    return FilingIndexService(
        session,
        embeddings,
        token_codec=WhitespaceCodec(),
        chunk_schema_version="filing-chunk.v1",
        target_tokens=10,
        overlap_tokens=2,
        minimum_final_tokens=3,
        now=NOW,
    )


@pytest.mark.asyncio
async def test_indexing_is_idempotent_and_uses_latest_10k(chat_session) -> None:
    add_filing(
        chat_session,
        accession="0000320193-24-000001",
        filed_at=date(2024, 9, 28),
        sections=[("Old business", token_text(12))],
    )
    latest = add_filing(
        chat_session,
        accession="0000320193-25-000001",
        filed_at=date(2025, 9, 27),
        sections=[
            ("Business", token_text(18)),
            ("Risk factors", token_text(7)),
        ],
    )
    embeddings = FakeEmbeddingProvider()
    indexer = service(chat_session, embeddings)

    first = await indexer.index_latest(company_id=1)
    first_rows = list(
        chat_session.exec(
            select(FilingChunk)
            .where(FilingChunk.filing_id == latest.id)
            .order_by(FilingChunk.section_id, FilingChunk.ordinal)
        ).all()
    )
    first_ids = [row.id for row in first_rows]
    second = await indexer.index_latest(company_id=1)
    second_ids = [
        row.id
        for row in chat_session.exec(
            select(FilingChunk)
            .where(FilingChunk.filing_id == latest.id)
            .order_by(FilingChunk.section_id, FilingChunk.ordinal)
        ).all()
    ]

    assert first.filing_id == latest.id
    assert first.indexed_sections == 2
    assert first.reused_sections == 0
    assert first.chunk_count == 3
    assert second.indexed_sections == 0
    assert second.reused_sections == 2
    assert second_ids == first_ids
    assert len(embeddings.batches) == 1
    assert all(row.embedding_model == embeddings.model_id for row in first_rows)


@pytest.mark.asyncio
async def test_changed_section_replaces_only_its_versioned_chunks(chat_session) -> None:
    filing = add_filing(
        chat_session,
        accession="0000320193-25-000001",
        filed_at=date(2025, 9, 27),
        sections=[("Business", token_text(18)), ("Risk factors", token_text(7))],
    )
    embeddings = FakeEmbeddingProvider()
    indexer = service(chat_session, embeddings)
    await indexer.index_latest(company_id=1)
    rows = list(
        chat_session.exec(
            select(FilingChunk)
            .where(FilingChunk.filing_id == filing.id)
            .order_by(FilingChunk.section_id, FilingChunk.ordinal)
        ).all()
    )
    stable_section_id = chat_session.exec(
        select(FilingSection.id).where(FilingSection.heading == "Risk factors")
    ).one()
    stable_ids = [row.id for row in rows if row.section_id == stable_section_id]
    changed_section = chat_session.exec(
        select(FilingSection).where(FilingSection.heading == "Business")
    ).one()
    changed_section.text = token_text(25)
    chat_session.add(changed_section)
    chat_session.commit()

    result = await indexer.index_latest(company_id=1)
    current = list(
        chat_session.exec(
            select(FilingChunk).where(FilingChunk.filing_id == filing.id)
        ).all()
    )

    assert result.indexed_sections == 1
    assert result.reused_sections == 1
    current_stable_ids = [
        row.id for row in current if row.section_id == stable_section_id
    ]
    assert current_stable_ids == stable_ids
    assert len(embeddings.batches) == 2


@pytest.mark.asyncio
async def test_invalid_embedding_batch_keeps_previous_chunks(chat_session) -> None:
    filing = add_filing(
        chat_session,
        accession="0000320193-25-000001",
        filed_at=date(2025, 9, 27),
        sections=[("Business", token_text(18))],
    )
    embeddings = FakeEmbeddingProvider()
    indexer = service(chat_session, embeddings)
    await indexer.index_latest(company_id=1)
    original_ids = [
        row.id
        for row in chat_session.exec(
            select(FilingChunk).where(FilingChunk.filing_id == filing.id)
        ).all()
    ]
    section = chat_session.exec(select(FilingSection)).one()
    section.text = token_text(25)
    chat_session.add(section)
    chat_session.commit()
    embeddings.returned_dimensions = 10

    with pytest.raises(ValueError, match="embedding dimensions"):
        await indexer.index_latest(company_id=1)
    current_ids = [
        row.id
        for row in chat_session.exec(
            select(FilingChunk).where(FilingChunk.filing_id == filing.id)
        ).all()
    ]

    assert current_ids == original_ids


@pytest.mark.asyncio
async def test_indexing_requires_latest_filing_sections(chat_session) -> None:
    embeddings = FakeEmbeddingProvider()
    indexer = service(chat_session, embeddings)

    with pytest.raises(DomainError) as missing_filing:
        await indexer.index_latest(company_id=1)
    assert missing_filing.value.code == "FILING_NOT_FOUND"

    add_filing(
        chat_session,
        accession="0000320193-25-000001",
        filed_at=date(2025, 9, 27),
        sections=[],
    )
    with pytest.raises(DomainError) as missing_sections:
        await indexer.index_latest(company_id=1)
    assert missing_sections.value.code == "CHAT_FILING_SECTIONS_MISSING"
