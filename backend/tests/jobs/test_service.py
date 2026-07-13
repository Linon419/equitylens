from datetime import UTC, date, datetime

import pytest
from sqlmodel import Session, select

from app.jobs.service import (
    SynchronizationServices,
    get_requester_job,
    retry_job,
    synchronize_company,
)
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.research_model import CompanyIntelligenceSnapshot, Filing
from app.quota.identity import RequestPrincipal
from app.quota.repository import SQLiteQuotaRepository
from app.quota.service import get_quota

ACCESSION = "0000320193-25-000079"
NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)


def services(session: Session, backend, **changes) -> SynchronizationServices:
    values = {
        "quota_repository": SQLiteQuotaRepository(session),
        "job_backend": backend,
        "schema_version": "v1",
        "prompt_version": "p1",
        "model_id": "model-1",
        "now": NOW,
    }
    values.update(changes)
    return SynchronizationServices(**values)


@pytest.mark.asyncio
async def test_sync_accepts_then_reuses_active_job_and_snapshot(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    principal = RequestPrincipal.guest("guest-hash", "ip-hash")
    configured = services(job_session, job_backend)

    first = await synchronize_company(
        job_session,
        job_company,
        principal,
        ACCESSION,
        configured,
    )
    duplicate = await synchronize_company(
        job_session,
        job_company,
        principal,
        ACCESSION,
        configured,
    )

    assert first.status == "accepted"
    assert first.job is not None and first.job.state == "queued"
    assert first.quota.remaining == 1
    assert duplicate.status == "active_job"
    assert duplicate.job is not None and duplicate.job.id == first.job.id
    assert duplicate.quota.remaining == 1

    filing = Filing(
        company_id=job_company.id,
        accession_number=ACCESSION,
        form="10-K",
        fiscal_period="FY2025",
        filed_at=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        primary_document="aapl.htm",
        source_url="https://www.sec.gov/aapl.htm",
    )
    job_session.add(filing)
    job_session.commit()
    job_session.refresh(filing)
    snapshot = CompanyIntelligenceSnapshot(
        company_id=job_company.id,
        filing_id=filing.id,
        status="completed",
        evidence_coverage="complete",
        schema_version="v1",
        prompt_version="p1",
        model_id="model-1",
        content_en={},
        content_zh={},
    )
    job_session.add(snapshot)
    job_session.commit()
    job_session.refresh(snapshot)

    completed = await synchronize_company(
        job_session,
        job_company,
        principal,
        ACCESSION,
        configured,
    )

    assert completed.status == "reused_snapshot"
    assert completed.snapshot_id == snapshot.id
    assert completed.quota.remaining == 1


@pytest.mark.asyncio
async def test_changed_prompt_accepts_new_job_and_consumes_allowance(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    principal = RequestPrincipal.guest("guest-hash", "ip-hash")
    await synchronize_company(
        job_session,
        job_company,
        principal,
        ACCESSION,
        services(job_session, job_backend),
    )

    result = await synchronize_company(
        job_session,
        job_company,
        principal,
        ACCESSION,
        services(job_session, job_backend, prompt_version="p2"),
    )

    assert result.status == "accepted"
    assert result.quota.remaining == 0


@pytest.mark.asyncio
async def test_failure_after_quota_reservation_rolls_back_counters_and_job(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    principal = RequestPrincipal.guest("guest-hash", "ip-hash")

    def fail() -> None:
        raise RuntimeError("injected insertion failure")

    with pytest.raises(RuntimeError, match="injected insertion failure"):
        await synchronize_company(
            job_session,
            job_company,
            principal,
            ACCESSION,
            services(job_session, job_backend, after_quota_reserved=fail),
        )

    quota = get_quota(
        SQLiteQuotaRepository(job_session),
        principal,
        NOW.date(),
    )
    assert quota.used == 0
    assert job_session.exec(select(IngestionJob)).all() == []


@pytest.mark.asyncio
async def test_dispatch_failure_keeps_committed_job_for_retry(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    principal = RequestPrincipal.guest("guest-hash", "ip-hash")
    job_backend.fail = True

    accepted = await synchronize_company(
        job_session,
        job_company,
        principal,
        ACCESSION,
        services(job_session, job_backend),
    )

    assert accepted.status == "accepted"
    assert accepted.job is not None
    assert accepted.job.state == "queued"
    assert accepted.job.error_code == "JOB_DISPATCH_FAILED"
    assert accepted.quota.used == 1

    job_backend.fail = False
    retried = await retry_job(
        job_session,
        accepted.job.id,
        principal,
        job_backend,
        now=NOW,
    )

    assert retried.attempt_count == 1
    assert retried.error_code is None
    assert retried.provider_run_id is not None
    assert get_requester_job(job_session, retried.id, principal).id == retried.id
