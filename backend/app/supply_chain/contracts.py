from collections.abc import Sequence
from typing import Literal, Protocol
from uuid import UUID

from app.quota.schemas import QuotaStatus
from app.supply_chain.schemas import (
    AcceptedGraph,
    CompanyIdentity,
    EntityCandidate,
    GraphDraft,
    GraphLocalization,
    GraphVerification,
    OfficialSourceDocument,
    OfficialSourceMetadata,
    PublicSupplyChainGraph,
    ResolvedEntity,
    SourcePlan,
    SourceType,
)


class GraphArtifactStore(Protocol):
    async def put(
        self,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> str: ...

    async def get(self, *, artifact_key: str) -> bytes: ...


class OfficialSourceTools(Protocol):
    async def list_official_sources(
        self,
        *,
        company: CompanyIdentity,
        query: str,
        source_types: tuple[SourceType, ...],
    ) -> list[OfficialSourceMetadata]: ...

    async def fetch_official_source(
        self,
        *,
        source_id: str,
    ) -> OfficialSourceDocument: ...

    def selected_documents(
        self,
        source_ids: Sequence[str],
    ) -> list[OfficialSourceDocument]: ...


class OfficialSourceCollector(Protocol):
    async def prepare_catalog(
        self,
        *,
        company: CompanyIdentity,
    ) -> OfficialSourceTools: ...


class SupplyChainAgent(Protocol):
    async def plan_sources(
        self,
        company: CompanyIdentity,
        tools: OfficialSourceTools,
    ) -> SourcePlan: ...

    async def extract_graph(
        self,
        company: CompanyIdentity,
        sources: Sequence[OfficialSourceDocument],
    ) -> GraphDraft: ...

    async def verify_graph(
        self,
        draft: GraphDraft,
        sources: Sequence[OfficialSourceDocument],
    ) -> GraphVerification: ...

    async def localize_graph(
        self,
        graph: AcceptedGraph,
        locale: Literal["zh"] = "zh",
    ) -> GraphLocalization: ...


class EntityResolver(Protocol):
    async def resolve(self, candidate: EntityCandidate) -> ResolvedEntity: ...

    async def resolve_draft(self, draft: GraphDraft) -> GraphDraft: ...


class SupplyChainGraphRepository(Protocol):
    async def latest_public(
        self,
        *,
        company_id: int,
        locale: Literal["en", "zh"],
    ) -> PublicSupplyChainGraph | None: ...

    async def get_version(
        self,
        *,
        company_id: int,
        source_fingerprint: str,
        schema_version: str,
        prompt_version: str,
        model_id: str,
    ) -> UUID | None: ...

    async def create_working_snapshot(
        self,
        *,
        company_id: int,
        source_fingerprint: str,
        schema_version: str,
        prompt_version: str,
        model_id: str,
    ) -> UUID: ...

    async def save_stage(
        self,
        *,
        snapshot_id: UUID,
        stage: Literal["source_plan", "draft", "verification", "localization"],
        payload: dict[str, object],
    ) -> None: ...

    async def load_stage(
        self,
        *,
        snapshot_id: UUID,
        stage: Literal["source_plan", "draft", "verification", "localization"],
    ) -> dict[str, object] | None: ...

    async def publish(
        self,
        *,
        snapshot_id: UUID,
        graph: AcceptedGraph,
        localization: GraphLocalization,
    ) -> PublicSupplyChainGraph: ...

    async def load_public(
        self,
        *,
        snapshot_id: UUID,
        locale: Literal["en", "zh"],
    ) -> PublicSupplyChainGraph | None: ...


class GraphQuotaLedger(Protocol):
    async def reserve(
        self,
        *,
        job_id: UUID,
        principal_type: Literal["guest", "user"],
        principal_hash: str,
        ip_hash: str | None,
    ) -> QuotaStatus: ...

    async def consume(self, *, job_id: UUID) -> None: ...

    async def refund(self, *, job_id: UUID) -> None: ...

    async def status(self, *, job_id: UUID) -> QuotaStatus: ...
