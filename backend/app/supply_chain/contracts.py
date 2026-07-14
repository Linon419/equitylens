from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

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
    ResolvedEntity,
    SourcePlan,
    SourceType,
)

if TYPE_CHECKING:
    from app.models.supply_chain_model import SupplyChainGraphSnapshot
    from app.supply_chain.repository import (
        CreateWorkingSnapshotCommand,
        GraphVersionKey,
        PersistedGraph,
        PublishGraphCommand,
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
        *,
        company: CompanyIdentity,
        tools: OfficialSourceTools,
    ) -> SourcePlan: ...

    async def extract_graph(
        self,
        *,
        company: CompanyIdentity,
        sources: list[OfficialSourceDocument],
    ) -> GraphDraft: ...

    async def verify_graph(
        self,
        *,
        draft: GraphDraft,
        sources: list[OfficialSourceDocument],
    ) -> GraphVerification: ...

    async def localize_graph(
        self,
        *,
        graph: AcceptedGraph,
        locale: Literal["zh"] = "zh",
    ) -> GraphLocalization: ...


class EntityResolver(Protocol):
    async def resolve(self, candidate: EntityCandidate) -> ResolvedEntity: ...

    async def resolve_draft(self, draft: GraphDraft) -> GraphDraft: ...


class SupplyChainGraphRepository(Protocol):
    def latest_public(self, company_id: int) -> SupplyChainGraphSnapshot | None: ...

    def find_by_version_key(
        self, key: GraphVersionKey
    ) -> SupplyChainGraphSnapshot | None: ...

    def create_working_snapshot(
        self, command: CreateWorkingSnapshotCommand
    ) -> SupplyChainGraphSnapshot: ...

    def save_stage(
        self,
        snapshot_id: UUID,
        *,
        stage: str,
        payload: BaseModel | dict[str, object],
    ) -> None: ...

    def load_stage(
        self,
        snapshot_id: UUID,
        *,
        stage: str,
    ) -> dict[str, object] | None: ...

    def publish(self, command: PublishGraphCommand) -> SupplyChainGraphSnapshot: ...

    def load_public(self, snapshot_id: UUID) -> PersistedGraph: ...


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
