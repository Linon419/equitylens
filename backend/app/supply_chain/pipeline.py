from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import Session, select

from app.core.errors import DomainError
from app.jobs.state import states_for
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.supply_chain_model import SupplyChainGraphSnapshot
from app.quota.repository import QuotaRepository
from app.quota.service import consume_job_analysis, refund_job_analysis
from app.supply_chain._pipeline_stages import SupplyChainStageRunner
from app.supply_chain._pipeline_support import (
    PUBLIC_GRAPH_STATUSES,
    STAGE_ERROR_CODES,
    company_identity,
    source_fingerprint,
)
from app.supply_chain.collector import SourceCollectionError
from app.supply_chain.contracts import (
    EntityResolver,
    OfficialSourceCollector,
    SupplyChainAgent,
    SupplyChainGraphRepository,
)
from app.supply_chain.repository import (
    CreateWorkingSnapshotCommand,
    GraphVersionConflict,
    GraphVersionKey,
    PublishGraphCommand,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    OfficialSourceDocument,
)

type GraphValidator = Callable[..., AcceptedGraph]


@dataclass
class SupplyChainPipelineServices:
    session: Session
    collector: OfficialSourceCollector
    agent: SupplyChainAgent
    resolver: EntityResolver
    repository: SupplyChainGraphRepository
    quota_repository: QuotaRepository
    validator: GraphValidator
    schema_version: str
    prompt_version: str
    model_id: str
    min_nodes: int
    max_nodes: int
    evidence_threshold: float
    now: datetime | None = None


class SupplyChainGraphPipeline:
    def __init__(self, services: SupplyChainPipelineServices) -> None:
        self.services = services
        self._session = services.session
        self._stages = SupplyChainStageRunner(services)

    async def run(self, job_id: UUID) -> SupplyChainGraphSnapshot:
        job = self._lock_job(job_id)
        self._require_graph_job(job)
        completed = self._completed_snapshot(job)
        if completed is not None:
            return completed

        step = "collecting"
        snapshot: SupplyChainGraphSnapshot | None = None
        try:
            company = self._company(job)
            identity = company_identity(company)
            self._advance_to(job, step)
            tools = await self.services.collector.prepare_catalog(company=identity)
            plan = await self.services.agent.plan_sources(company=identity, tools=tools)
            sources = tools.selected_documents(plan.selected_source_ids)
            if not sources:
                raise SourceCollectionError("SOURCE_SELECTION_EMPTY")

            snapshot = self._snapshot_for_sources(company, sources)
            self._link_snapshot(job, snapshot)
            if snapshot.status in PUBLIC_GRAPH_STATUSES:
                return self._complete(job, snapshot)
            self._revive_snapshot(snapshot)
            self.services.repository.save_stage(
                snapshot.id,
                stage="source_plan",
                payload=plan,
            )

            step = "extracting"
            self._advance_to(job, step)
            draft = await self._stages.draft(snapshot, identity, sources)

            step = "resolving"
            self._advance_to(job, step)
            resolved = await self._stages.resolved_draft(snapshot, draft)

            step = "verifying"
            self._advance_to(job, step)
            verification = await self._stages.verification(snapshot, resolved, sources)
            accepted = self._stages.accepted_graph(
                snapshot,
                resolved,
                verification,
                sources,
            )

            step = "localizing"
            self._advance_to(job, step)
            localization = await self._stages.localization(snapshot, accepted)
            published = self.services.repository.publish(
                PublishGraphCommand(
                    snapshot_id=snapshot.id,
                    graph=accepted,
                    localization=localization,
                    now=self._now(),
                )
            )
            return self._complete(job, published)
        except Exception as error:
            self._fail(job_id, snapshot, step, error)
            raise

    def _snapshot_for_sources(
        self,
        company: Company,
        sources: list[OfficialSourceDocument],
    ) -> SupplyChainGraphSnapshot:
        assert company.id is not None
        key = GraphVersionKey(
            company_id=company.id,
            source_fingerprint=source_fingerprint(sources),
            schema_version=self.services.schema_version,
            prompt_version=self.services.prompt_version,
            model_id=self.services.model_id,
        )
        existing = self.services.repository.find_by_version_key(key)
        if existing is not None:
            return existing
        try:
            return self.services.repository.create_working_snapshot(
                CreateWorkingSnapshotCommand(
                    **key.__dict__,
                    sources=sources,
                    now=self._now(),
                )
            )
        except GraphVersionConflict:
            winner = self.services.repository.find_by_version_key(key)
            if winner is None:
                raise
            return winner

    def _complete(
        self,
        job: IngestionJob,
        snapshot: SupplyChainGraphSnapshot,
    ) -> SupplyChainGraphSnapshot:
        job = self._lock_job(job.id)
        if job.state == "completed" and job.graph_snapshot_id == snapshot.id:
            return snapshot
        job.graph_snapshot_id = snapshot.id
        job.state = "completed"
        job.current_step = "completed"
        job.error_code = None
        job.retry_eligible = False
        job.updated_at = self._now()
        if not consume_job_analysis(
            self.services.quota_repository,
            job.id,
            now=self._now(),
        ):
            raise DomainError("GRAPH_QUOTA_CONSUMPTION_FAILED", 409)
        self._session.add(job)
        self._session.commit()
        return snapshot

    def _fail(
        self,
        job_id: UUID,
        snapshot: SupplyChainGraphSnapshot | None,
        step: str,
        error: Exception,
    ) -> None:
        self._session.rollback()
        job = self._lock_job(job_id)
        job.state = "failed"
        job.current_step = step
        job.error_code = getattr(error, "code", STAGE_ERROR_CODES[step])
        job.retry_eligible = bool(getattr(error, "retryable", True))
        job.updated_at = self._now()
        if snapshot is not None:
            current = self._session.get(SupplyChainGraphSnapshot, snapshot.id)
            if current is not None and current.status not in PUBLIC_GRAPH_STATUSES:
                current.status = "failed"
                self._session.add(current)
        refund_job_analysis(
            self.services.quota_repository,
            job.id,
            now=self._now(),
        )
        self._session.add(job)
        self._session.commit()

    def _advance_to(self, job: IngestionJob, target: str) -> None:
        job = self._lock_job(job.id)
        states = states_for(job.job_type)
        if job.state == "failed":
            raise DomainError("JOB_STATE_CONFLICT", 409)
        if states.index(job.state) >= states.index(target):
            return
        job.state = target
        job.current_step = target
        job.error_code = None
        job.updated_at = self._now()
        self._session.add(job)
        self._session.commit()

    def _link_snapshot(
        self,
        job: IngestionJob,
        snapshot: SupplyChainGraphSnapshot,
    ) -> None:
        job = self._lock_job(job.id)
        if job.graph_snapshot_id == snapshot.id:
            return
        job.graph_snapshot_id = snapshot.id
        job.updated_at = self._now()
        self._session.add(job)
        self._session.commit()

    def _revive_snapshot(self, snapshot: SupplyChainGraphSnapshot) -> None:
        if snapshot.status != "failed":
            return
        snapshot = self._session.get(SupplyChainGraphSnapshot, snapshot.id)
        if snapshot is None:
            raise DomainError("GRAPH_SNAPSHOT_NOT_FOUND", 404)
        snapshot.status = "drafted"
        self._session.add(snapshot)
        self._session.commit()

    def _completed_snapshot(
        self,
        job: IngestionJob,
    ) -> SupplyChainGraphSnapshot | None:
        if job.state != "completed" or job.graph_snapshot_id is None:
            return None
        snapshot = self._session.get(SupplyChainGraphSnapshot, job.graph_snapshot_id)
        if snapshot is None or snapshot.status not in PUBLIC_GRAPH_STATUSES:
            raise DomainError("GRAPH_SNAPSHOT_NOT_FOUND", 404)
        return snapshot

    def _lock_job(self, job_id: UUID) -> IngestionJob:
        job = self._session.exec(
            select(IngestionJob)
            .where(IngestionJob.id == job_id)
            .with_for_update()
        ).first()
        if job is None:
            raise DomainError("JOB_NOT_FOUND", 404)
        return job

    def _company(self, job: IngestionJob) -> Company:
        company = self._session.get(Company, job.company_id)
        if company is None:
            raise DomainError("COMPANY_NOT_FOUND", 404)
        return company

    @staticmethod
    def _require_graph_job(job: IngestionJob) -> None:
        if job.job_type != "supply_chain_graph":
            raise DomainError("JOB_TYPE_CONFLICT", 409)

    def _now(self) -> datetime:
        value = self.services.now or datetime.now(UTC)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
