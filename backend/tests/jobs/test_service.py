from datetime import UTC, date, datetime

import pytest
from sqlmodel import Session, select

from app.jobs.service import (
    GraphSynchronizationServices,
    SynchronizationServices,
    get_requester_job,
    graph_deduplication_key,
    retry_job,
    synchronize_company,
    synchronize_supply_chain_graph,
)
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.research_model import CompanyIntelligenceSnapshot, Filing
from app.models.supply_chain_model import (
    AgentQuotaReservation,
    SupplyChainGraphSnapshot,
)
from app.quota.errors import QuotaExceeded
from app.quota.identity import RequestPrincipal
from app.quota.repository import SQLiteQuotaRepository
from app.quota.service import get_quota, refund_job_analysis, reserve_analysis

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


def graph_services(
    session: Session,
    backend,
    **changes,
) -> GraphSynchronizationServices:
    values = {
        "quota_repository": SQLiteQuotaRepository(session),
        "job_backend": backend,
        "schema_version": "graph-v1",
        "prompt_version": "graph-p1",
        "model_id": "gpt-5-mini",
        "now": NOW,
    }
    values.update(changes)
    return GraphSynchronizationServices(**values)


def add_completed_graph_job(
    session: Session,
    company: Company,
    accession: str = ACCESSION,
) -> tuple[IngestionJob, SupplyChainGraphSnapshot]:
    assert company.id is not None
    snapshot = SupplyChainGraphSnapshot(
        company_id=company.id,
        status="completed",
        schema_version="graph-v1",
        prompt_version="graph-p1",
        model_id="gpt-5-mini",
        source_fingerprint="a" * 64,
        content_en={"focus_node_key": "company:0000320193"},
        content_zh={"focus_node_key": "company:0000320193"},
        evidence_coverage="complete",
        node_count=25,
        edge_count=24,
        generated_at=NOW,
        verified_at=NOW,
        completed_at=NOW,
    )
    session.add(snapshot)
    session.flush()
    job = IngestionJob(
        job_type="supply_chain_graph",
        company_id=company.id,
        requested_by_type="guest",
        requested_by_hash="completed-owner",
        deduplication_key=graph_deduplication_key(
            company.id,
            accession,
            "graph-v1",
            "graph-p1",
            "gpt-5-mini",
        ),
        state="completed",
        current_step="completed",
        graph_snapshot_id=snapshot.id,
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(job)
    session.commit()
    return job, snapshot


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


@pytest.mark.asyncio
async def test_graph_sync_reuses_completed_snapshot_without_quota(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    _, snapshot = add_completed_graph_job(job_session, job_company)
    principal = RequestPrincipal.guest("graph-guest", "graph-ip")

    response = await synchronize_supply_chain_graph(
        job_session,
        company=job_company,
        principal=principal,
        latest_accession=ACCESSION,
        force_refresh=False,
        services=graph_services(job_session, job_backend),
    )

    assert response.status == "reused_snapshot"
    assert response.snapshot_id == snapshot.id
    assert response.quota.used == 0


@pytest.mark.asyncio
async def test_graph_sync_collapses_active_job_and_reserves_once(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    principal = RequestPrincipal.guest("graph-guest", "graph-ip")
    configured = graph_services(job_session, job_backend)

    first = await synchronize_supply_chain_graph(
        job_session,
        company=job_company,
        principal=principal,
        latest_accession=ACCESSION,
        force_refresh=False,
        services=configured,
    )
    duplicate = await synchronize_supply_chain_graph(
        job_session,
        company=job_company,
        principal=principal,
        latest_accession=ACCESSION,
        force_refresh=True,
        services=configured,
    )

    assert first.status == "accepted"
    assert first.job is not None
    assert first.job.result_kind == "supply_chain_graph"
    assert duplicate.status == "active_job"
    assert duplicate.job is not None and duplicate.job.id == first.job.id
    assert duplicate.quota.used == 1
    ledgers = job_session.exec(select(AgentQuotaReservation)).all()
    assert len(ledgers) == 1
    assert ledgers[0].job_id == first.job.id


@pytest.mark.asyncio
async def test_force_refresh_after_completed_job_accepts_new_job(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    completed, _ = add_completed_graph_job(job_session, job_company)
    principal = RequestPrincipal.guest("graph-guest", "graph-ip")

    response = await synchronize_supply_chain_graph(
        job_session,
        company=job_company,
        principal=principal,
        latest_accession=ACCESSION,
        force_refresh=True,
        services=graph_services(job_session, job_backend),
    )

    assert response.status == "accepted"
    assert response.job is not None and response.job.id != completed.id
    assert response.quota.used == 1


@pytest.mark.asyncio
async def test_newer_filing_accession_creates_new_graph_job(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    add_completed_graph_job(job_session, job_company)
    principal = RequestPrincipal.guest("graph-guest", "graph-ip")

    response = await synchronize_supply_chain_graph(
        job_session,
        company=job_company,
        principal=principal,
        latest_accession="0000320193-26-000001",
        force_refresh=False,
        services=graph_services(job_session, job_backend),
    )

    assert response.status == "accepted"
    assert response.quota.used == 1


@pytest.mark.asyncio
async def test_graph_dispatch_failure_refunds_and_retry_rereserves(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    principal = RequestPrincipal.guest("graph-guest", "graph-ip")
    configured = graph_services(job_session, job_backend)
    job_backend.fail = True

    response = await synchronize_supply_chain_graph(
        job_session,
        company=job_company,
        principal=principal,
        latest_accession=ACCESSION,
        force_refresh=False,
        services=configured,
    )

    assert response.status == "accepted"
    assert response.job is not None
    assert response.job.state == "failed"
    assert response.job.error_code == "JOB_DISPATCH_FAILED"
    assert response.quota.used == 0
    ledger = job_session.exec(select(AgentQuotaReservation)).one()
    assert ledger.state == "refunded"

    job_backend.fail = False
    retried = await retry_job(
        job_session,
        response.job.id,
        principal,
        job_backend,
        quota_repository=configured.quota_repository,
        now=NOW,
    )

    assert retried.state == "queued"
    assert retried.provider_run_id is not None
    assert get_quota(configured.quota_repository, principal, NOW.date()).used == 1
    assert job_session.exec(select(AgentQuotaReservation)).one().state == "reserved"


@pytest.mark.asyncio
async def test_graph_retry_resumes_before_failed_stage(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    principal = RequestPrincipal.guest("graph-guest", "graph-ip")
    configured = graph_services(job_session, job_backend)
    response = await synchronize_supply_chain_graph(
        job_session,
        company=job_company,
        principal=principal,
        latest_accession=ACCESSION,
        force_refresh=False,
        services=configured,
    )
    assert response.job is not None
    job = job_session.get(IngestionJob, response.job.id)
    assert job is not None
    job.state = "failed"
    job.current_step = "localizing"
    job.error_code = "AGENT_PROVIDER_UNAVAILABLE"
    refund_job_analysis(configured.quota_repository, job.id, now=NOW)
    job_session.add(job)
    job_session.commit()

    retried = await retry_job(
        job_session,
        job.id,
        principal,
        job_backend,
        quota_repository=configured.quota_repository,
        now=NOW,
    )

    assert retried.state == "verifying"
    assert retried.current_step == "verifying"
    assert job_session.exec(select(AgentQuotaReservation)).one().state == "reserved"


@pytest.mark.asyncio
async def test_graph_quota_error_leaves_no_job_or_ledger(
    job_session: Session,
    job_company: Company,
    job_backend,
) -> None:
    principal = RequestPrincipal.guest("graph-guest", "graph-ip")
    repository = SQLiteQuotaRepository(job_session)
    reserve_analysis(repository, principal, usage_date=NOW.date())
    reserve_analysis(repository, principal, usage_date=NOW.date())
    job_session.commit()

    with pytest.raises(QuotaExceeded):
        await synchronize_supply_chain_graph(
            job_session,
            company=job_company,
            principal=principal,
            latest_accession=ACCESSION,
            force_refresh=False,
            services=graph_services(job_session, job_backend),
        )

    assert job_session.exec(select(IngestionJob)).all() == []
    assert job_session.exec(select(AgentQuotaReservation)).all() == []
