from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.supply_chain_model import (
    GraphEdgeCitation,
    GraphOfficialSource,
    SupplyChainGraphEdge,
    SupplyChainGraphNode,
    SupplyChainGraphSnapshot,
)
from app.supply_chain._repository_mapper import (
    citation_confidence,
    edge_importance,
    finalize_snapshot,
    graph_citations,
    graph_edges,
    graph_nodes,
    json_payload,
    require_graph_sources,
    source_index,
    source_rows,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    GraphLocalization,
    OfficialSourceDocument,
)
from app.supply_chain.validator import validate_localization

_PUBLIC_STATUSES = {"completed", "insufficient_evidence"}


class GraphPublicationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class GraphVersionConflict(GraphPublicationError):
    pass


@dataclass(frozen=True)
class GraphVersionKey:
    company_id: int
    source_fingerprint: str
    schema_version: str
    prompt_version: str
    model_id: str


@dataclass(frozen=True)
class CreateWorkingSnapshotCommand(GraphVersionKey):
    sources: list[OfficialSourceDocument]
    now: datetime


@dataclass(frozen=True)
class PublishGraphCommand:
    snapshot_id: UUID
    graph: AcceptedGraph
    localization: GraphLocalization
    now: datetime


@dataclass(frozen=True)
class PersistedGraph:
    snapshot: SupplyChainGraphSnapshot
    nodes: list[SupplyChainGraphNode]
    edges: list[SupplyChainGraphEdge]
    citations: list[GraphEdgeCitation]
    sources: list[GraphOfficialSource]
    source_index: dict[UUID, list[dict[str, str]]]
    edge_importance: dict[str, float]
    citation_confidence: dict[tuple[str, str, str, str, str], float]


class SqlSupplyChainGraphRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_public(self, company_id: int) -> SupplyChainGraphSnapshot | None:
        return self._session.exec(
            select(SupplyChainGraphSnapshot)
            .where(
                SupplyChainGraphSnapshot.company_id == company_id,
                SupplyChainGraphSnapshot.status.in_(_PUBLIC_STATUSES),
            )
            .order_by(
                case(
                    (SupplyChainGraphSnapshot.status == "completed", 0),
                    else_=1,
                ),
                SupplyChainGraphSnapshot.completed_at.desc(),
                SupplyChainGraphSnapshot.generated_at.desc(),
            )
        ).first()

    def find_by_version_key(
        self,
        key: GraphVersionKey,
    ) -> SupplyChainGraphSnapshot | None:
        return self._session.exec(
            select(SupplyChainGraphSnapshot).where(
                SupplyChainGraphSnapshot.company_id == key.company_id,
                SupplyChainGraphSnapshot.source_fingerprint == key.source_fingerprint,
                SupplyChainGraphSnapshot.schema_version == key.schema_version,
                SupplyChainGraphSnapshot.prompt_version == key.prompt_version,
                SupplyChainGraphSnapshot.model_id == key.model_id,
            )
        ).first()

    def create_working_snapshot(
        self,
        command: CreateWorkingSnapshotCommand,
    ) -> SupplyChainGraphSnapshot:
        if self.find_by_version_key(command) is not None:
            raise GraphVersionConflict("GRAPH_VERSION_EXISTS")
        snapshot = SupplyChainGraphSnapshot(
            company_id=command.company_id,
            status="drafted",
            schema_version=command.schema_version,
            prompt_version=command.prompt_version,
            model_id=command.model_id,
            source_fingerprint=command.source_fingerprint,
            generated_at=command.now,
        )
        rows, index = source_rows(snapshot.id, command.sources)
        snapshot.content_en = {"stages": {}, "source_index": index}
        try:
            self._session.add(snapshot)
            self._session.flush()
            self._session.add_all(rows)
            self._session.commit()
            self._session.refresh(snapshot)
        except IntegrityError as error:
            self._session.rollback()
            if self.find_by_version_key(command) is not None:
                raise GraphVersionConflict("GRAPH_VERSION_EXISTS") from error
            raise GraphPublicationError("GRAPH_WORKING_SNAPSHOT_FAILED") from error
        except Exception as error:
            self._session.rollback()
            raise GraphPublicationError("GRAPH_WORKING_SNAPSHOT_FAILED") from error
        return snapshot

    def save_stage(
        self,
        snapshot_id: UUID,
        *,
        stage: str,
        payload: BaseModel | dict[str, Any],
    ) -> None:
        snapshot = self._working_snapshot(snapshot_id)
        stages = dict(snapshot.content_en.get("stages", {}))
        stages[stage] = json_payload(payload)
        snapshot.content_en = {**snapshot.content_en, "stages": stages}
        try:
            self._session.add(snapshot)
            self._session.commit()
        except Exception as error:
            self._session.rollback()
            raise GraphPublicationError("GRAPH_STAGE_SAVE_FAILED") from error

    def load_stage(
        self,
        snapshot_id: UUID,
        *,
        stage: str,
    ) -> dict[str, Any] | None:
        snapshot = self._snapshot(snapshot_id)
        payload = snapshot.content_en.get("stages", {}).get(stage)
        return deepcopy(payload) if payload is not None else None

    def publish(self, command: PublishGraphCommand) -> SupplyChainGraphSnapshot:
        try:
            validate_localization(
                graph=command.graph,
                localization=command.localization,
            )
            snapshot = self._working_snapshot(command.snapshot_id, lock=True)
            index = source_index(snapshot)
            if not require_graph_sources(command.graph, index):
                raise GraphPublicationError("GRAPH_SOURCE_MAPPING_MISSING")
            nodes = graph_nodes(snapshot.id, command.graph, command.localization)
            self._session.add_all(nodes)
            self._session.flush()
            node_ids = {node.node_key: node.id for node in nodes}
            edges = graph_edges(
                snapshot.id,
                command.graph,
                command.localization,
                node_ids,
            )
            self._session.add_all(edges)
            self._session.flush()
            self._session.add_all(
                graph_citations(snapshot.id, edges, command.graph, index)
            )
            finalize_snapshot(
                snapshot,
                graph=command.graph,
                localization=command.localization,
                now=command.now,
            )
            self._session.add(snapshot)
            self._session.commit()
            self._session.refresh(snapshot)
            return snapshot
        except GraphPublicationError:
            self._session.rollback()
            raise
        except Exception as error:
            self._session.rollback()
            raise GraphPublicationError("GRAPH_PUBLICATION_FAILED") from error

    def load_public(self, snapshot_id: UUID) -> PersistedGraph:
        snapshot = self._snapshot(snapshot_id)
        if snapshot.status not in _PUBLIC_STATUSES:
            raise GraphPublicationError("GRAPH_SNAPSHOT_NOT_PUBLIC")
        nodes = list(
            self._session.exec(
                select(SupplyChainGraphNode)
                .where(SupplyChainGraphNode.snapshot_id == snapshot_id)
                .order_by(SupplyChainGraphNode.rank, SupplyChainGraphNode.node_key)
            ).all()
        )
        edges = list(
            self._session.exec(
                select(SupplyChainGraphEdge)
                .where(SupplyChainGraphEdge.snapshot_id == snapshot_id)
                .order_by(SupplyChainGraphEdge.edge_key)
            ).all()
        )
        citations = list(
            self._session.exec(
                select(GraphEdgeCitation)
                .where(GraphEdgeCitation.snapshot_id == snapshot_id)
                .order_by(GraphEdgeCitation.edge_id, GraphEdgeCitation.id)
            ).all()
        )
        sources = list(
            self._session.exec(
                select(GraphOfficialSource)
                .where(GraphOfficialSource.snapshot_id == snapshot_id)
                .order_by(GraphOfficialSource.id)
            ).all()
        )
        return PersistedGraph(
            snapshot=snapshot,
            nodes=nodes,
            edges=edges,
            citations=citations,
            sources=sources,
            source_index=source_index(snapshot),
            edge_importance=edge_importance(snapshot.content_en),
            citation_confidence=citation_confidence(snapshot.content_en),
        )

    def _working_snapshot(
        self,
        snapshot_id: UUID,
        *,
        lock: bool = False,
    ) -> SupplyChainGraphSnapshot:
        statement = select(SupplyChainGraphSnapshot).where(
            SupplyChainGraphSnapshot.id == snapshot_id
        )
        if lock:
            statement = statement.with_for_update()
        snapshot = self._session.exec(statement).first()
        if snapshot is None:
            raise GraphPublicationError("GRAPH_SNAPSHOT_NOT_FOUND")
        if snapshot.status in _PUBLIC_STATUSES or snapshot.status == "failed":
            raise GraphPublicationError("GRAPH_SNAPSHOT_IMMUTABLE")
        return snapshot

    def _snapshot(self, snapshot_id: UUID) -> SupplyChainGraphSnapshot:
        snapshot = self._session.get(SupplyChainGraphSnapshot, snapshot_id)
        if snapshot is None:
            raise GraphPublicationError("GRAPH_SNAPSHOT_NOT_FOUND")
        return snapshot
