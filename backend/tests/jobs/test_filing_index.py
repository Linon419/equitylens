from datetime import UTC, date, datetime

import pytest
from sqlmodel import select

from app.chat.indexing import FilingIndexResult
from app.jobs._filing_index import (
    FilingIndexJobPipeline,
    FilingIndexSynchronizationServices,
    synchronize_filing_index,
)
from app.models.chat_model import FilingChunk
from app.models.job_model import AgentDailyUsage, IngestionJob
from app.models.research_model import Filing, FilingSection
from app.quota.identity import RequestPrincipal

NOW = datetime(2026, 7, 15, 10, tzinfo=UTC)
ACCESSION = "0000320193-25-000079"


class FakeIndexer:
    def __init__(self, filing_id=None, failure: Exception | None = None) -> None:
        self.filing_id = filing_id
        self.failure = failure
        self.company_ids: list[int] = []

    async def index_latest(self, *, company_id: int) -> FilingIndexResult:
        self.company_ids.append(company_id)
        if self.failure is not None:
            raise self.failure
        return FilingIndexResult(
            filing_id=self.filing_id,
            chunk_count=1,
            indexed_sections=1,
            reused_sections=0,
        )


def add_filing(job_session, company_id: int):
    filing = Filing(
        company_id=company_id,
        accession_number=ACCESSION,
        form="10-K",
        fiscal_period="FY2025",
        filed_at=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        primary_document="aapl.htm",
        source_url="https://www.sec.gov/aapl.htm",
    )
    job_session.add(filing)
    job_session.flush()
    section = FilingSection(
        filing_id=filing.id,
        heading="Business",
        source_anchor="item-1",
        ordinal=0,
        text="Business evidence.",
    )
    job_session.add(section)
    job_session.commit()
    return filing, section


@pytest.mark.asyncio
async def test_sync_accepts_and_deduplicates_without_agent_quota(
    job_session,
    job_company,
    job_backend,
) -> None:
    filing, _section = add_filing(job_session, job_company.id)
    principal = RequestPrincipal.guest("index-guest", "index-ip")
    services = FilingIndexSynchronizationServices(
        job_backend=job_backend,
        schema_version="filing-chunk.v1",
        embedding_model="text-embedding-3-small",
        now=NOW,
    )

    first = await synchronize_filing_index(
        job_session,
        company=job_company,
        principal=principal,
        filing=filing,
        services=services,
    )
    duplicate = await synchronize_filing_index(
        job_session,
        company=job_company,
        principal=principal,
        filing=filing,
        services=services,
    )

    assert first.status == "accepted"
    assert first.job is not None and first.job.result_kind == "filing_index"
    assert duplicate.status == "active_job"
    assert duplicate.job is not None and duplicate.job.id == first.job.id
    assert job_session.exec(select(AgentDailyUsage)).all() == []


@pytest.mark.asyncio
async def test_sync_reuses_complete_index_without_dispatch(
    job_session,
    job_company,
    job_backend,
) -> None:
    filing, section = add_filing(job_session, job_company.id)
    job_session.add(
        FilingChunk(
            company_id=job_company.id,
            filing_id=filing.id,
            section_id=section.id,
            ordinal=0,
            text="Business evidence.",
            token_count=2,
            content_hash="a" * 64,
            chunk_schema_version="filing-chunk.v1",
            embedding_model="text-embedding-3-small",
            embedding=[0.0] * 1_536,
        )
    )
    job_session.commit()

    response = await synchronize_filing_index(
        job_session,
        company=job_company,
        principal=RequestPrincipal.guest("index-guest", "index-ip"),
        filing=filing,
        services=FilingIndexSynchronizationServices(
            job_backend=job_backend,
            schema_version="filing-chunk.v1",
            embedding_model="text-embedding-3-small",
            now=NOW,
        ),
    )

    assert response.status == "ready"
    assert response.filing_id == filing.id
    assert job_backend.calls == []


@pytest.mark.asyncio
async def test_filing_index_pipeline_completes_all_states(
    job_session,
    job_company,
) -> None:
    filing, _section = add_filing(job_session, job_company.id)
    job = IngestionJob(
        job_type="filing_index",
        company_id=job_company.id,
        requested_by_type="guest",
        requested_by_hash="index-guest",
        deduplication_key="filing-index:test",
        state="queued",
        current_step="queued",
        created_at=NOW,
        updated_at=NOW,
    )
    job_session.add(job)
    job_session.commit()
    indexer = FakeIndexer(filing.id)

    await FilingIndexJobPipeline(job_session, indexer).run(job.id)
    job_session.refresh(job)

    assert job.state == "completed"
    assert job.current_step == "completed"
    assert indexer.company_ids == [job_company.id]
