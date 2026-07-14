from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.supply_chain_model import (
    GraphEdgeCitation,
    GraphOfficialSource,
    SupplyChainGraphEdge,
    SupplyChainGraphNode,
    SupplyChainGraphSnapshot,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    GraphLocalization,
    OfficialSourceDocument,
)


def source_rows(
    snapshot_id: UUID,
    sources: list[OfficialSourceDocument],
) -> tuple[list[GraphOfficialSource], list[dict[str, str]]]:
    by_hash: dict[str, GraphOfficialSource] = {}
    index: list[dict[str, str]] = []
    for source in sources:
        row = by_hash.get(source.content_hash)
        if row is None:
            row = GraphOfficialSource(
                snapshot_id=snapshot_id,
                source_type=source.source_type,
                publisher=source.publisher,
                title=source.title,
                canonical_url=source.canonical_url,
                published_at=source.published_at,
                content_hash=source.content_hash,
                artifact_key=source.artifact_key,
            )
            by_hash[source.content_hash] = row
        index.append(
            {
                "database_id": str(row.id),
                "source_id": source.source_id,
                "source_key": source.source_key,
            }
        )
    return list(by_hash.values()), index


def graph_nodes(
    snapshot_id: UUID,
    graph: AcceptedGraph,
    localization: GraphLocalization,
) -> list[SupplyChainGraphNode]:
    localized = {node.node_key: node for node in localization.nodes}
    return [
        SupplyChainGraphNode(
            snapshot_id=snapshot_id,
            node_key=node.node_key,
            kind=node.kind,
            layer=node.layer,
            company_id=node.company_id,
            symbol=node.symbol,
            cik=node.cik,
            label_en=node.label_en,
            label_zh=localized[node.node_key].label_zh,
            description_en=node.description_en,
            description_zh=localized[node.node_key].description_zh,
            importance=Decimal(str(node.importance)),
            confidence=confidence_label(node.confidence),
            rank=node.rank,
        )
        for node in graph.accepted_nodes
    ]


def graph_edges(
    snapshot_id: UUID,
    graph: AcceptedGraph,
    localization: GraphLocalization,
    node_ids: dict[str, UUID],
) -> list[SupplyChainGraphEdge]:
    localized = {
        edge.edge_key: edge
        for edge in [*localization.public_edges, *localization.potential_edges]
    }
    return [
        SupplyChainGraphEdge(
            snapshot_id=snapshot_id,
            edge_key=edge.edge_key,
            source_node_id=node_ids[edge.source_node_key],
            target_node_id=node_ids[edge.target_node_key],
            relationship_type=edge.relationship_type,
            evidence_status=edge.evidence_status,
            confidence=confidence_label(edge.confidence),
            explanation_en=edge.explanation_en,
            explanation_zh=localized[edge.edge_key].explanation_zh,
        )
        for edge in [*graph.public_edges, *graph.potential_edges]
    ]


def graph_citations(
    snapshot_id: UUID,
    rows: list[SupplyChainGraphEdge],
    graph: AcceptedGraph,
    index: dict[UUID, list[dict[str, str]]],
) -> list[GraphEdgeCitation]:
    edge_rows = {edge.edge_key: edge for edge in rows}
    source_ids = {
        item["source_key"]: database_id
        for database_id, items in index.items()
        for item in items
    }
    citations: list[GraphEdgeCitation] = []
    seen: set[tuple[UUID, UUID, str]] = set()
    for edge in [*graph.public_edges, *graph.potential_edges]:
        edge_row = edge_rows[edge.edge_key]
        for reference in sorted(
            edge.evidence_refs,
            key=lambda item: (item.support_role != "primary", -item.confidence),
        ):
            source_id = source_ids[reference.source_key]
            identity = edge_row.id, source_id, reference.locator
            if identity in seen:
                continue
            seen.add(identity)
            citations.append(
                GraphEdgeCitation(
                    snapshot_id=snapshot_id,
                    edge_id=edge_row.id,
                    source_id=source_id,
                    excerpt=reference.excerpt,
                    source_anchor=reference.locator,
                    support_role=reference.support_role,
                )
            )
    return citations


def finalize_snapshot(
    snapshot: SupplyChainGraphSnapshot,
    *,
    graph: AcceptedGraph,
    localization: GraphLocalization,
    now: datetime,
) -> None:
    stored_index = snapshot.content_en.get("source_index", [])
    snapshot.content_en = {
        **graph.model_dump(mode="json"),
        "source_index": stored_index,
    }
    snapshot.content_zh = {
        **localization.model_dump(mode="json"),
        "status": graph.status,
        "rejected_edges": [
            item.model_dump(mode="json") for item in graph.rejected_edges
        ],
        "sources": [item.model_dump(mode="json") for item in graph.sources],
        "evidence_coverage": graph.evidence_coverage,
        "overall_confidence": graph.overall_confidence,
        "reason_codes": graph.reason_codes,
    }
    snapshot.status = graph.status
    snapshot.evidence_coverage = coverage_label(graph)
    snapshot.overall_confidence = graph.overall_confidence
    snapshot.node_count = len(graph.accepted_nodes)
    snapshot.edge_count = len(graph.public_edges) + len(graph.potential_edges)
    snapshot.verified_at = now
    snapshot.completed_at = now


def source_index(
    snapshot: SupplyChainGraphSnapshot,
) -> dict[UUID, list[dict[str, str]]]:
    result: dict[UUID, list[dict[str, str]]] = {}
    for item in snapshot.content_en.get("source_index", []):
        result.setdefault(UUID(item["database_id"]), []).append(dict(item))
    return result


def require_graph_sources(
    graph: AcceptedGraph,
    index: dict[UUID, list[dict[str, str]]],
) -> bool:
    available = {item["source_key"] for items in index.values() for item in items}
    required = {
        reference.source_key
        for edge in [*graph.public_edges, *graph.potential_edges]
        for reference in edge.evidence_refs
    }
    return required <= available


def edge_importance(content: dict[str, Any]) -> dict[str, float]:
    return {
        edge["edge_key"]: float(edge["importance"])
        for edge in [
            *content.get("public_edges", []),
            *content.get("potential_edges", []),
        ]
    }


def citation_confidence(
    content: dict[str, Any],
) -> dict[tuple[str, str, str, str, str], float]:
    return {
        (
            edge["edge_key"],
            reference["source_key"],
            reference["excerpt"],
            reference["locator"],
            reference["support_role"],
        ): float(reference["confidence"])
        for edge in [
            *content.get("public_edges", []),
            *content.get("potential_edges", []),
        ]
        for reference in edge["evidence_refs"]
    }


def json_payload(payload: BaseModel | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    return deepcopy(payload)


def coverage_label(graph: AcceptedGraph) -> str:
    if graph.status == "insufficient_evidence":
        return "insufficient_evidence"
    return "complete" if graph.evidence_coverage >= 0.85 else "partial"


def confidence_label(score: float) -> str:
    if score >= 0.85:
        return "High"
    if score >= 0.65:
        return "Medium"
    return "Low"
