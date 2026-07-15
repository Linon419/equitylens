from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlmodel import Session

from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.quota.identity import RequestPrincipal
from app.quota.repository import InMemoryQuotaRepository
from app.quota.service import (
    get_quota,
    reserve_job_analysis,
)
from app.supply_chain.collector import SourceCollectionError
from app.supply_chain.openai_agent import SupplyChainAgentError
from app.supply_chain.pipeline import (
    SupplyChainGraphPipeline,
    SupplyChainPipelineServices,
    source_fingerprint,
)
from app.supply_chain.repository import (
    CreateWorkingSnapshotCommand,
    PublishGraphCommand,
    SqlSupplyChainGraphRepository,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    CompanyIdentity,
    GraphDraft,
    GraphLocalization,
    GraphVerification,
    OfficialSourceDocument,
    ResolvedEntity,
    SourcePlan,
)
from app.supply_chain.validator import validate_for_publication

NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)
PRINCIPAL = RequestPrincipal.guest("pipeline-guest", "pipeline-ip")


@dataclass
class FakeTools:
    documents: list[OfficialSourceDocument]
    calls: list[str]

    def selected_documents(self, source_ids) -> list[OfficialSourceDocument]:
        self.calls.append("selected_documents")
        selected = set(source_ids)
        return [item for item in self.documents if item.source_id in selected]

    async def fetch_official_source(
        self,
        *,
        source_id: str,
    ) -> OfficialSourceDocument:
        return next(item for item in self.documents if item.source_id == source_id)


@dataclass
class FakeCollector:
    tools: FakeTools
    calls: list[str]
    error: Exception | None = None

    async def prepare_catalog(self, *, company: CompanyIdentity) -> FakeTools:
        self.calls.append("prepare_catalog")
        if self.error is not None:
            raise self.error
        return self.tools


@dataclass
class FakeAgent:
    plan: SourcePlan
    draft: GraphDraft
    verification: GraphVerification
    localization: GraphLocalization
    calls: list[str]
    localization_error: Exception | None = None

    async def plan_sources(self, *, company, tools) -> SourcePlan:
        self.calls.append("plan_sources")
        return self.plan

    async def extract_graph(self, *, company, sources) -> GraphDraft:
        self.calls.append("extract_graph")
        return self.draft

    async def verify_graph(self, *, draft, sources) -> GraphVerification:
        self.calls.append("verify_graph")
        return self.verification

    async def localize_graph(self, *, graph, locale="zh") -> GraphLocalization:
        self.calls.append("localize_graph")
        if self.localization_error is not None:
            raise self.localization_error
        return self.localization


@dataclass
class FakeResolver:
    calls: list[str]

    async def resolve(self, candidate) -> ResolvedEntity:
        raise AssertionError("pipeline uses resolve_draft")

    async def resolve_draft(self, draft: GraphDraft) -> GraphDraft:
        self.calls.append("resolve_draft")
        return draft


class RecordingRepository:
    def __init__(self, session: Session, calls: list[str]) -> None:
        self.inner = SqlSupplyChainGraphRepository(session)
        self.calls = calls

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def publish(self, command: PublishGraphCommand):
        self.calls.append("publish")
        return self.inner.publish(command)


class RecordingQuota(InMemoryQuotaRepository):
    def __init__(self, calls: list[str]) -> None:
        super().__init__()
        self.calls = calls

    def consume_for_job(self, job_id: UUID, *, now: datetime) -> bool:
        self.calls.append("consume_quota")
        return super().consume_for_job(job_id, now=now)

    def refund_for_job(self, job_id: UUID, *, now: datetime) -> bool:
        self.calls.append("refund_quota")
        return super().refund_for_job(job_id, now=now)


@dataclass
class PipelineHarness:
    pipeline: SupplyChainGraphPipeline
    repository: RecordingRepository
    quota: RecordingQuota
    collector: FakeCollector
    agent: FakeAgent
    calls: list[str] = field(default_factory=list)


def make_job(
    session: Session,
    company: Company,
    quota: RecordingQuota,
) -> IngestionJob:
    assert company.id is not None
    job = IngestionJob(
        job_type="supply_chain_graph",
        company_id=company.id,
        requested_by_type="guest",
        requested_by_hash=PRINCIPAL.principal_hash,
        deduplication_key=f"supply-chain-graph:pipeline:{company.id}",
        state="queued",
        current_step="queued",
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(job)
    session.commit()
    reserve_job_analysis(quota, PRINCIPAL, job.id, NOW.date())
    return job


@pytest.fixture
def pipeline_harness(
    session: Session,
    source_documents: list[OfficialSourceDocument],
    source_plan: SourcePlan,
    graph_draft: GraphDraft,
    graph_verification: GraphVerification,
    graph_localization: GraphLocalization,
) -> PipelineHarness:
    calls: list[str] = []
    tools = FakeTools(source_documents, calls)
    collector = FakeCollector(tools, calls)
    agent = FakeAgent(
        source_plan,
        graph_draft,
        graph_verification,
        graph_localization,
        calls,
    )
    repository = RecordingRepository(session, calls)
    quota = RecordingQuota(calls)

    def validator(**kwargs) -> AcceptedGraph:
        calls.append("validate_for_publication")
        return validate_for_publication(**kwargs)

    services = SupplyChainPipelineServices(
        session=session,
        collector=collector,
        agent=agent,
        resolver=FakeResolver(calls),
        repository=repository,
        quota_repository=quota,
        validator=validator,
        schema_version="supply-chain-graph.v1",
        prompt_version="supply-chain-graph.2026-07-14",
        model_id="gpt-5-mini",
        min_nodes=25,
        max_nodes=40,
        evidence_threshold=0.75,
        now=NOW,
    )
    return PipelineHarness(
        SupplyChainGraphPipeline(services),
        repository,
        quota,
        collector,
        agent,
        calls,
    )


@pytest.mark.asyncio
async def test_pipeline_runs_agent_stages_and_consumes_quota(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
) -> None:
    job = make_job(session, company, pipeline_harness.quota)

    result = await pipeline_harness.pipeline.run(job.id)

    assert pipeline_harness.calls == [
        "prepare_catalog",
        "plan_sources",
        "selected_documents",
        "extract_graph",
        "resolve_draft",
        "verify_graph",
        "validate_for_publication",
        "localize_graph",
        "publish",
        "consume_quota",
    ]
    assert result.status == "completed"
    session.refresh(job)
    assert job.state == "completed"
    assert job.graph_snapshot_id == result.id
    assert pipeline_harness.quota.lease_for_job(job.id).state == "consumed"


@pytest.mark.asyncio
async def test_completed_pipeline_replay_is_idempotent(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
) -> None:
    job = make_job(session, company, pipeline_harness.quota)
    first = await pipeline_harness.pipeline.run(job.id)
    calls = list(pipeline_harness.calls)

    second = await pipeline_harness.pipeline.run(job.id)

    assert second.id == first.id
    assert pipeline_harness.calls == calls


@pytest.mark.asyncio
async def test_public_stages_resume_across_pipeline_instances(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
) -> None:
    job = make_job(session, company, pipeline_harness.quota)
    services = pipeline_harness.pipeline.services

    await SupplyChainGraphPipeline(services).collect(job.id)
    await SupplyChainGraphPipeline(services).extract(job.id)
    await SupplyChainGraphPipeline(services).resolve(job.id)
    await SupplyChainGraphPipeline(services).verify(job.id)
    await SupplyChainGraphPipeline(services).localize(job.id)
    result = await SupplyChainGraphPipeline(services).publish(job.id)

    assert result.status == "completed"
    assert pipeline_harness.calls.count("plan_sources") == 1
    assert pipeline_harness.calls.count("extract_graph") == 1
    assert pipeline_harness.calls.count("resolve_draft") == 1
    assert pipeline_harness.calls.count("verify_graph") == 1
    assert pipeline_harness.calls.count("localize_graph") == 1
    assert pipeline_harness.calls.count("publish") == 1


@pytest.mark.asyncio
async def test_replayed_public_stage_returns_stored_result(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
) -> None:
    job = make_job(session, company, pipeline_harness.quota)
    pipeline = SupplyChainGraphPipeline(pipeline_harness.pipeline.services)

    first = await pipeline.collect(job.id)
    calls = list(pipeline_harness.calls)
    replayed = await SupplyChainGraphPipeline(pipeline.services).collect(job.id)

    assert replayed.id == first.id
    assert pipeline_harness.calls == calls


@pytest.mark.asyncio
async def test_retryable_collection_failure_refunds_and_preserves_previous(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> None:
    assert company.id is not None
    previous = pipeline_harness.repository.inner.create_working_snapshot(
        CreateWorkingSnapshotCommand(
            company_id=company.id,
            sources=source_documents,
            source_fingerprint="f" * 64,
            schema_version="previous-v1",
            prompt_version="previous-p1",
            model_id="previous-model",
            now=NOW,
        )
    )
    previous = pipeline_harness.repository.inner.publish(
        PublishGraphCommand(
            snapshot_id=previous.id,
            graph=accepted_graph,
            localization=graph_localization,
            now=NOW,
        )
    )
    job = make_job(session, company, pipeline_harness.quota)
    pipeline_harness.collector.error = SourceCollectionError(
        "SEC_UNAVAILABLE",
        retryable=True,
    )

    with pytest.raises(SourceCollectionError):
        await pipeline_harness.pipeline.run(job.id)

    session.refresh(job)
    assert job.state == "failed"
    assert job.retry_eligible is True
    assert pipeline_harness.quota.lease_for_job(job.id).state == "refunded"
    assert pipeline_harness.repository.latest_public(company.id).id == previous.id


@pytest.mark.asyncio
async def test_existing_source_version_links_snapshot_without_agent_rework(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> None:
    assert company.id is not None
    existing = pipeline_harness.repository.inner.create_working_snapshot(
        CreateWorkingSnapshotCommand(
            company_id=company.id,
            sources=source_documents,
            source_fingerprint=source_fingerprint(source_documents),
            schema_version="supply-chain-graph.v1",
            prompt_version="supply-chain-graph.2026-07-14",
            model_id="gpt-5-mini",
            now=NOW,
        )
    )
    existing = pipeline_harness.repository.inner.publish(
        PublishGraphCommand(
            snapshot_id=existing.id,
            graph=accepted_graph,
            localization=graph_localization,
            now=NOW,
        )
    )
    job = make_job(session, company, pipeline_harness.quota)

    result = await pipeline_harness.pipeline.run(job.id)

    assert result.id == existing.id
    assert pipeline_harness.calls == [
        "prepare_catalog",
        "plan_sources",
        "selected_documents",
        "consume_quota",
    ]
    session.refresh(job)
    assert job.state == "completed"
    assert job.graph_snapshot_id == existing.id


@pytest.mark.asyncio
async def test_localization_failure_resumes_from_accepted_stage(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
) -> None:
    job = make_job(session, company, pipeline_harness.quota)
    pipeline_harness.agent.localization_error = SupplyChainAgentError(
        "AGENT_PROVIDER_UNAVAILABLE",
        retryable=True,
    )

    with pytest.raises(SupplyChainAgentError):
        await pipeline_harness.pipeline.run(job.id)

    session.refresh(job)
    assert job.state == "failed"
    assert job.current_step == "localizing"
    assert pipeline_harness.quota.lease_for_job(job.id).state == "refunded"

    pipeline_harness.pipeline.resume_retry(job.id)
    session.refresh(job)
    assert job.state == "verifying"
    pipeline_harness.agent.localization_error = None
    result = await pipeline_harness.pipeline.run(job.id)

    assert result.status == "completed"
    assert pipeline_harness.calls.count("extract_graph") == 1
    assert pipeline_harness.calls.count("resolve_draft") == 1
    assert pipeline_harness.calls.count("verify_graph") == 1
    assert pipeline_harness.calls.count("localize_graph") == 2
    assert pipeline_harness.quota.lease_for_job(job.id).state == "consumed"


@pytest.mark.asyncio
async def test_invalid_stored_localization_is_regenerated(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
    graph_localization: GraphLocalization,
) -> None:
    job = make_job(session, company, pipeline_harness.quota)
    snapshot = await pipeline_harness.pipeline.collect(job.id)
    await pipeline_harness.pipeline.extract(job.id)
    await pipeline_harness.pipeline.resolve(job.id)
    await pipeline_harness.pipeline.verify(job.id)
    invalid_payload = graph_localization.model_dump(mode="json")
    for group in ("public_edges", "potential_edges", "internal_edges"):
        if invalid_payload[group]:
            invalid_payload[group].pop()
            break
    else:
        raise AssertionError("localization fixture must contain an edge")
    pipeline_harness.repository.save_stage(
        snapshot.id,
        stage="localization",
        payload=invalid_payload,
    )

    result = await pipeline_harness.pipeline.localize(job.id)

    assert result == graph_localization
    assert pipeline_harness.calls.count("localize_graph") == 1
    stored = pipeline_harness.repository.load_stage(
        snapshot.id,
        stage="localization",
    )
    assert GraphLocalization.model_validate(stored) == graph_localization


@pytest.mark.asyncio
async def test_insufficient_evidence_is_published_and_consumed(
    session: Session,
    company: Company,
    pipeline_harness: PipelineHarness,
    accepted_graph: AcceptedGraph,
) -> None:
    job = make_job(session, company, pipeline_harness.quota)

    def insufficient(**_kwargs) -> AcceptedGraph:
        pipeline_harness.calls.append("validate_for_publication")
        return accepted_graph.model_copy(update={"status": "insufficient_evidence"})

    pipeline_harness.pipeline.services.validator = insufficient
    result = await pipeline_harness.pipeline.run(job.id)

    assert result.status == "insufficient_evidence"
    assert pipeline_harness.quota.lease_for_job(job.id).state == "consumed"
    assert get_quota(pipeline_harness.quota, PRINCIPAL, NOW.date()).used == 1
