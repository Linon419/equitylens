from datetime import UTC, datetime
from uuid import UUID

from sqlmodel import select

from app.core.errors import DomainError
from app.jobs.state import prior_state, states_for
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.supply_chain_model import SupplyChainGraphSnapshot
from app.quota.service import (
    consume_job_analysis,
    refund_job_analysis,
    rereserve_job_analysis,
)
from app.supply_chain._pipeline_support import (
    PUBLIC_GRAPH_STATUSES,
    STAGE_ERROR_CODES,
    source_fingerprint,
)
from app.supply_chain.pipeline_types import SupplyChainPipelineServices
from app.supply_chain.repository import (
    CreateWorkingSnapshotCommand,
    GraphVersionConflict,
    GraphVersionKey,
)
from app.supply_chain.schemas import OfficialSourceDocument


class GraphPipelineLifecycle:
    def __init__(self, services: SupplyChainPipelineServices) -> None:
        self.services = services
        self.session = services.session

    def snapshot_for_sources(
        self,
        company: Company,
        sources: list[OfficialSourceDocument],
    ) -> SupplyChainGraphSnapshot:
        if company.id is None:
            raise DomainError("COMPANY_NOT_FOUND", 404)
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
                    now=self.now(),
                )
            )
        except GraphVersionConflict:
            winner = self.services.repository.find_by_version_key(key)
            if winner is None:
                raise
            return winner

    def complete(
        self,
        job: IngestionJob,
        snapshot: SupplyChainGraphSnapshot,
    ) -> SupplyChainGraphSnapshot:
        job = self.lock_job(job.id)
        if job.state == "completed" and job.graph_snapshot_id == snapshot.id:
            return snapshot
        job.graph_snapshot_id = snapshot.id
        job.state = "completed"
        job.current_step = "completed"
        job.error_code = None
        job.retry_eligible = False
        job.updated_at = self.now()
        if not consume_job_analysis(
            self.services.quota_repository,
            job.id,
            now=self.now(),
        ):
            raise DomainError("GRAPH_QUOTA_CONSUMPTION_FAILED", 409)
        self.session.add(job)
        self.session.commit()
        return snapshot

    def fail(self, job_id: UUID, step: str, error: Exception) -> None:
        self.session.rollback()
        job = self.lock_job(job_id)
        job.state = "failed"
        job.current_step = step
        job.error_code = getattr(error, "code", STAGE_ERROR_CODES[step])
        job.retry_eligible = bool(getattr(error, "retryable", True))
        job.updated_at = self.now()
        snapshot = self.snapshot(job.graph_snapshot_id)
        if snapshot is not None and snapshot.status not in PUBLIC_GRAPH_STATUSES:
            snapshot.status = "failed"
            self.session.add(snapshot)
        refund_job_analysis(
            self.services.quota_repository,
            job.id,
            now=self.now(),
        )
        self.session.add(job)
        self.session.commit()

    def resume_retry(self, job_id: UUID) -> IngestionJob:
        job = self.lock_job(job_id)
        if job.state != "failed":
            return job
        if not job.retry_eligible:
            raise DomainError("JOB_RETRY_UNAVAILABLE", 409)
        if not rereserve_job_analysis(
            self.services.quota_repository,
            job.id,
            now=self.now(),
        ):
            raise DomainError("JOB_RETRY_UNAVAILABLE", 409)
        resume_state = prior_state(job.job_type, job.current_step)
        job.state = resume_state
        job.current_step = resume_state
        job.attempt_count += 1
        job.error_code = None
        job.updated_at = self.now()
        self.session.add(job)
        self.session.commit()
        return job

    def advance_to(self, job: IngestionJob, target: str) -> None:
        job = self.lock_job(job.id)
        states = states_for(job.job_type)
        if job.state == "failed":
            raise DomainError("JOB_STATE_CONFLICT", 409)
        if states.index(job.state) >= states.index(target):
            return
        job.state = target
        job.current_step = target
        job.error_code = None
        job.updated_at = self.now()
        self.session.add(job)
        self.session.commit()

    def link_snapshot(
        self,
        job: IngestionJob,
        snapshot: SupplyChainGraphSnapshot,
    ) -> None:
        job = self.lock_job(job.id)
        if job.graph_snapshot_id == snapshot.id:
            return
        job.graph_snapshot_id = snapshot.id
        job.updated_at = self.now()
        self.session.add(job)
        self.session.commit()

    def revive_snapshot(self, snapshot: SupplyChainGraphSnapshot) -> None:
        if snapshot.status != "failed":
            return
        current = self.snapshot(snapshot.id)
        if current is None:
            raise DomainError("GRAPH_SNAPSHOT_NOT_FOUND", 404)
        current.status = "drafted"
        self.session.add(current)
        self.session.commit()

    def completed_snapshot(
        self,
        job: IngestionJob,
    ) -> SupplyChainGraphSnapshot | None:
        if job.state != "completed" or job.graph_snapshot_id is None:
            return None
        snapshot = self.snapshot(job.graph_snapshot_id)
        if snapshot is None or snapshot.status not in PUBLIC_GRAPH_STATUSES:
            raise DomainError("GRAPH_SNAPSHOT_NOT_FOUND", 404)
        return snapshot

    def lock_job(self, job_id: UUID) -> IngestionJob:
        job = self.session.exec(
            select(IngestionJob)
            .where(IngestionJob.id == job_id)
            .with_for_update()
        ).first()
        if job is None:
            raise DomainError("JOB_NOT_FOUND", 404)
        return job

    def company(self, job: IngestionJob) -> Company:
        company = self.session.get(Company, job.company_id)
        if company is None:
            raise DomainError("COMPANY_NOT_FOUND", 404)
        return company

    def snapshot(self, snapshot_id: UUID | None) -> SupplyChainGraphSnapshot | None:
        if snapshot_id is None:
            return None
        return self.session.get(SupplyChainGraphSnapshot, snapshot_id)

    @staticmethod
    def require_graph_job(job: IngestionJob) -> None:
        if job.job_type != "supply_chain_graph":
            raise DomainError("JOB_TYPE_CONFLICT", 409)

    def now(self) -> datetime:
        value = self.services.now or datetime.now(UTC)
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
