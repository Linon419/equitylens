from uuid import UUID

from pydantic import BaseModel

from app.core.errors import DomainError
from app.models.job_model import IngestionJob
from app.models.supply_chain_model import SupplyChainGraphSnapshot
from app.supply_chain._pipeline_lifecycle import GraphPipelineLifecycle
from app.supply_chain._pipeline_stages import SupplyChainStageRunner
from app.supply_chain._pipeline_support import (
    PUBLIC_GRAPH_STATUSES,
    company_identity,
    source_fingerprint,
)
from app.supply_chain.collector import SourceCollectionError
from app.supply_chain.pipeline_types import SupplyChainPipelineServices
from app.supply_chain.repository import PublishGraphCommand
from app.supply_chain.schemas import (
    AcceptedGraph,
    CompanyIdentity,
    GraphDraft,
    GraphLocalization,
    OfficialSourceDocument,
    SourcePlan,
)

__all__ = [
    "SupplyChainGraphPipeline",
    "SupplyChainPipelineServices",
    "source_fingerprint",
]
_STEP_ARTIFACTS = {
    "collect": "source_plan",
    "extract": "draft",
    "resolve": "resolved",
    "verify": "accepted",
    "localize": "localization",
}


class SupplyChainGraphPipeline:
    def __init__(self, services: SupplyChainPipelineServices) -> None:
        self.services = services
        self._lifecycle = GraphPipelineLifecycle(services)
        self._stages = SupplyChainStageRunner(services)
        self._source_cache: dict[
            UUID,
            tuple[CompanyIdentity, list[OfficialSourceDocument]],
        ] = {}

    async def run(self, job_id: UUID) -> SupplyChainGraphSnapshot:
        await self.collect(job_id)
        completed = self._terminal(job_id)
        if completed is not None:
            return completed
        await self.extract(job_id)
        await self.resolve(job_id)
        await self.verify(job_id)
        await self.localize(job_id)
        result = await self.publish(job_id)
        assert isinstance(result, SupplyChainGraphSnapshot)
        return result

    def is_step_complete(self, job_id: UUID, step: str) -> bool:
        job = self._job(job_id)
        if self._lifecycle.completed_snapshot(job) is not None:
            return True
        if step == "publish":
            return False
        artifact = _STEP_ARTIFACTS.get(step)
        if artifact is None:
            raise DomainError("GRAPH_STEP_INVALID", 422)
        snapshot = self._lifecycle.snapshot(job.graph_snapshot_id)
        return snapshot is not None and self._stage(snapshot, artifact) is not None

    def resume_retry(self, job_id: UUID) -> None:
        job = self._job(job_id)
        if job.state == "failed":
            self._lifecycle.resume_retry(job_id)

    async def collect(self, job_id: UUID) -> SupplyChainGraphSnapshot:
        job = self._job(job_id)
        completed = self._lifecycle.completed_snapshot(job)
        if completed is not None:
            return completed
        linked = self._lifecycle.snapshot(job.graph_snapshot_id)
        if linked is not None and self._stage(linked, "source_plan") is not None:
            self._lifecycle.revive_snapshot(linked)
            return linked
        try:
            company = self._lifecycle.company(job)
            identity = company_identity(company)
            self._lifecycle.advance_to(job, "collecting")
            tools = await self.services.collector.prepare_catalog(company=identity)
            plan = await self.services.agent.plan_sources(company=identity, tools=tools)
            sources = tools.selected_documents(plan.selected_source_ids)
            self._require_sources(sources)
            snapshot = self._lifecycle.snapshot_for_sources(company, sources)
            self._lifecycle.link_snapshot(job, snapshot)
            if snapshot.status in PUBLIC_GRAPH_STATUSES:
                return self._lifecycle.complete(job, snapshot)
            self._lifecycle.revive_snapshot(snapshot)
            self.services.repository.save_stage(
                snapshot.id,
                stage="source_plan",
                payload=plan,
            )
            self._source_cache[snapshot.id] = (identity, sources)
            return snapshot
        except Exception as error:
            self._lifecycle.fail(job_id, "collecting", error)
            raise

    async def extract(
        self,
        job_id: UUID,
    ) -> GraphDraft | SupplyChainGraphSnapshot:
        job, snapshot, completed = self._stage_context(job_id)
        if completed is not None:
            return completed
        stored = self._stage(snapshot, "draft")
        if stored is not None:
            return GraphDraft.model_validate(stored)
        try:
            identity, sources = await self._sources(job, snapshot)
            self._lifecycle.advance_to(job, "extracting")
            return await self._stages.draft(snapshot, identity, sources)
        except Exception as error:
            self._lifecycle.fail(job_id, "extracting", error)
            raise

    async def resolve(
        self,
        job_id: UUID,
    ) -> GraphDraft | SupplyChainGraphSnapshot:
        job, snapshot, completed = self._stage_context(job_id)
        if completed is not None:
            return completed
        stored = self._stage(snapshot, "resolved")
        if stored is not None:
            return GraphDraft.model_validate(stored)
        try:
            draft = self._required_stage(snapshot, "draft", GraphDraft)
            self._lifecycle.advance_to(job, "resolving")
            return await self._stages.resolved_draft(snapshot, draft)
        except Exception as error:
            self._lifecycle.fail(job_id, "resolving", error)
            raise

    async def verify(
        self,
        job_id: UUID,
    ) -> AcceptedGraph | SupplyChainGraphSnapshot:
        job, snapshot, completed = self._stage_context(job_id)
        if completed is not None:
            return completed
        stored = self._stage(snapshot, "accepted")
        if stored is not None:
            return AcceptedGraph.model_validate(stored)
        try:
            resolved = self._required_stage(snapshot, "resolved", GraphDraft)
            _, sources = await self._sources(job, snapshot)
            self._lifecycle.advance_to(job, "verifying")
            verification = await self._stages.verification(
                snapshot,
                resolved,
                sources,
            )
            return self._stages.accepted_graph(
                snapshot,
                resolved,
                verification,
                sources,
            )
        except Exception as error:
            self._lifecycle.fail(job_id, "verifying", error)
            raise

    async def localize(
        self,
        job_id: UUID,
    ) -> GraphLocalization | SupplyChainGraphSnapshot:
        job, snapshot, completed = self._stage_context(job_id)
        if completed is not None:
            return completed
        stored = self._stage(snapshot, "localization")
        if stored is not None:
            return GraphLocalization.model_validate(stored)
        try:
            graph = self._required_stage(snapshot, "accepted", AcceptedGraph)
            self._lifecycle.advance_to(job, "localizing")
            return await self._stages.localization(snapshot, graph)
        except Exception as error:
            self._lifecycle.fail(job_id, "localizing", error)
            raise

    async def publish(self, job_id: UUID) -> SupplyChainGraphSnapshot:
        job, snapshot, completed = self._stage_context(job_id)
        if completed is not None:
            return completed
        try:
            graph = self._required_stage(snapshot, "accepted", AcceptedGraph)
            localization = self._required_stage(
                snapshot,
                "localization",
                GraphLocalization,
            )
            published = self.services.repository.publish(
                PublishGraphCommand(
                    snapshot_id=snapshot.id,
                    graph=graph,
                    localization=localization,
                    now=self._lifecycle.now(),
                )
            )
            return self._lifecycle.complete(job, published)
        except Exception as error:
            self._lifecycle.fail(job_id, "localizing", error)
            raise

    async def _sources(
        self,
        job: IngestionJob,
        snapshot: SupplyChainGraphSnapshot,
    ) -> tuple[CompanyIdentity, list[OfficialSourceDocument]]:
        cached = self._source_cache.get(snapshot.id)
        if cached is not None:
            return cached
        plan = self._required_stage(snapshot, "source_plan", SourcePlan)
        identity = company_identity(self._lifecycle.company(job))
        tools = await self.services.collector.prepare_catalog(company=identity)
        for source_id in plan.selected_source_ids:
            await tools.fetch_official_source(source_id=source_id)
        sources = tools.selected_documents(plan.selected_source_ids)
        self._require_sources(sources)
        if source_fingerprint(sources) != snapshot.source_fingerprint:
            raise SourceCollectionError("SOURCE_VERSION_CHANGED", retryable=True)
        self._source_cache[snapshot.id] = (identity, sources)
        return identity, sources

    def _stage_context(
        self,
        job_id: UUID,
    ) -> tuple[
        IngestionJob,
        SupplyChainGraphSnapshot,
        SupplyChainGraphSnapshot | None,
    ]:
        job = self._job(job_id)
        completed = self._lifecycle.completed_snapshot(job)
        if completed is not None:
            return job, completed, completed
        snapshot = self._lifecycle.snapshot(job.graph_snapshot_id)
        if snapshot is None:
            raise DomainError("GRAPH_SNAPSHOT_NOT_FOUND", 404)
        self._lifecycle.revive_snapshot(snapshot)
        return job, snapshot, None

    def _job(self, job_id: UUID) -> IngestionJob:
        job = self._lifecycle.lock_job(job_id)
        self._lifecycle.require_graph_job(job)
        return job

    def _terminal(self, job_id: UUID) -> SupplyChainGraphSnapshot | None:
        return self._lifecycle.completed_snapshot(self._job(job_id))

    def _stage(
        self,
        snapshot: SupplyChainGraphSnapshot,
        name: str,
    ) -> dict | None:
        return self.services.repository.load_stage(snapshot.id, stage=name)

    def _required_stage[ModelT: BaseModel](
        self,
        snapshot: SupplyChainGraphSnapshot,
        name: str,
        model: type[ModelT],
    ) -> ModelT:
        payload = self._stage(snapshot, name)
        if payload is None:
            raise DomainError("GRAPH_STAGE_PREREQUISITE_MISSING", 409)
        return model.model_validate(payload)

    @staticmethod
    def _require_sources(sources: list[OfficialSourceDocument]) -> None:
        if not sources:
            raise SourceCollectionError("SOURCE_SELECTION_EMPTY")
