from app.models.supply_chain_model import SupplyChainGraphSnapshot
from app.supply_chain.pipeline_types import SupplyChainPipelineServices
from app.supply_chain.schemas import (
    AcceptedGraph,
    CompanyIdentity,
    GraphDraft,
    GraphLocalization,
    GraphVerification,
    OfficialSourceDocument,
)


class SupplyChainStageRunner:
    def __init__(self, services: SupplyChainPipelineServices) -> None:
        self._services = services

    async def draft(
        self,
        snapshot: SupplyChainGraphSnapshot,
        company: CompanyIdentity,
        sources: list[OfficialSourceDocument],
    ) -> GraphDraft:
        stored = self._services.repository.load_stage(snapshot.id, stage="draft")
        if stored is not None:
            return GraphDraft.model_validate(stored)
        draft = await self._services.agent.extract_graph(
            company=company,
            sources=sources,
        )
        self._services.repository.save_stage(
            snapshot.id,
            stage="draft",
            payload=draft,
        )
        return draft

    async def resolved_draft(
        self,
        snapshot: SupplyChainGraphSnapshot,
        draft: GraphDraft,
    ) -> GraphDraft:
        stored = self._services.repository.load_stage(snapshot.id, stage="resolved")
        if stored is not None:
            return GraphDraft.model_validate(stored)
        resolved = await self._services.resolver.resolve_draft(draft)
        self._services.repository.save_stage(
            snapshot.id,
            stage="resolved",
            payload=resolved,
        )
        return resolved

    async def verification(
        self,
        snapshot: SupplyChainGraphSnapshot,
        draft: GraphDraft,
        sources: list[OfficialSourceDocument],
    ) -> GraphVerification:
        stored = self._services.repository.load_stage(
            snapshot.id,
            stage="verification",
        )
        if stored is not None:
            return GraphVerification.model_validate(stored)
        verification = await self._services.agent.verify_graph(
            draft=draft,
            sources=sources,
        )
        self._services.repository.save_stage(
            snapshot.id,
            stage="verification",
            payload=verification,
        )
        return verification

    def accepted_graph(
        self,
        snapshot: SupplyChainGraphSnapshot,
        draft: GraphDraft,
        verification: GraphVerification,
        sources: list[OfficialSourceDocument],
    ) -> AcceptedGraph:
        stored = self._services.repository.load_stage(snapshot.id, stage="accepted")
        if stored is not None:
            return AcceptedGraph.model_validate(stored)
        accepted = self._services.validator(
            draft=draft,
            verification=verification,
            sources=sources,
            min_nodes=self._services.min_nodes,
            max_nodes=self._services.max_nodes,
            evidence_threshold=self._services.evidence_threshold,
        )
        self._services.repository.save_stage(
            snapshot.id,
            stage="accepted",
            payload=accepted,
        )
        return accepted

    async def localization(
        self,
        snapshot: SupplyChainGraphSnapshot,
        graph: AcceptedGraph,
    ) -> GraphLocalization:
        stored = self._services.repository.load_stage(
            snapshot.id,
            stage="localization",
        )
        if stored is not None:
            return GraphLocalization.model_validate(stored)
        localization = await self._services.agent.localize_graph(
            graph=graph,
            locale="zh",
        )
        self._services.repository.save_stage(
            snapshot.id,
            stage="localization",
            payload=localization,
        )
        return localization
