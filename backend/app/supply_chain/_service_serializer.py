from collections import defaultdict, deque
from uuid import UUID

from app.core.errors import DomainError
from app.models.company_model import Company
from app.models.supply_chain_model import (
    GraphEdgeCitation,
    GraphOfficialSource,
    SupplyChainGraphEdge,
    SupplyChainGraphNode,
)
from app.quota.schemas import QuotaStatus
from app.supply_chain.repository import PersistedGraph
from app.supply_chain.schemas import (
    PublicGraphCitation,
    PublicGraphEdge,
    PublicGraphNode,
    PublicGraphSnapshotSummary,
    PublicGraphSource,
    PublicSupplyChainGraph,
)

_LAYER_ORDER = {"upstream": 0, "core": 1, "downstream": 2}


def serialize_graph(
    persisted: PersistedGraph,
    *,
    company: Company,
    locale: str,
    evidence: set[str],
    limit: int,
    quota: QuotaStatus,
) -> PublicSupplyChainGraph:
    snapshot = persisted.snapshot
    focus_key = str(snapshot.content_en["focus_node_key"])
    node_by_id = {node.id: node for node in persisted.nodes}
    focus = next(
        (node for node in persisted.nodes if node.node_key == focus_key),
        None,
    )
    if focus is None:
        raise DomainError("GRAPH_FOCUS_NODE_MISSING", 500)
    eligible_edges = [
        edge for edge in persisted.edges if edge.evidence_status in evidence
    ]
    selected_ids = _reachable_node_ids(focus.id, eligible_edges, node_by_id, limit)
    selected_nodes = [node for node in persisted.nodes if node.id in selected_ids]
    selected_edges = [
        edge
        for edge in eligible_edges
        if {edge.source_node_id, edge.target_node_id} <= selected_ids
    ]
    citations = _public_citations(persisted, selected_edges)
    cited_source_ids = {
        citation.source_id
        for edge_citations in citations.values()
        for citation in edge_citations
    }
    sources = _public_sources(persisted, cited_source_ids, citations)
    thesis_key = "thesis_en" if locale == "en" else "thesis_zh"
    content = snapshot.content_en if locale == "en" else snapshot.content_zh
    return PublicSupplyChainGraph(
        snapshot=PublicGraphSnapshotSummary(
            id=snapshot.id,
            status=snapshot.status,
            symbol=company.symbol,
            model_id=snapshot.model_id,
            focus_node_key=focus_key,
            thesis=str(content[thesis_key]),
            evidence_coverage=snapshot.evidence_coverage,
            overall_confidence=snapshot.overall_confidence,
            node_count=snapshot.node_count,
            edge_count=snapshot.edge_count,
            generated_at=snapshot.generated_at,
        ),
        nodes=[_public_node(node, locale) for node in selected_nodes],
        edges=[
            _public_edge(
                edge,
                locale,
                persisted.edge_importance,
                citations[edge.id],
            )
            for edge in selected_edges
        ],
        sources=sources,
        quota=quota,
    )


def _reachable_node_ids(
    focus_id: UUID,
    edges: list[SupplyChainGraphEdge],
    nodes: dict[UUID, SupplyChainGraphNode],
    limit: int,
) -> set[UUID]:
    adjacency: dict[UUID, set[UUID]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.source_node_id].add(edge.target_node_id)
        adjacency[edge.target_node_id].add(edge.source_node_id)
    selected = {focus_id}
    queue = deque([focus_id])
    while queue and len(selected) < limit:
        current = queue.popleft()
        neighbors = sorted(
            adjacency[current] - selected,
            key=lambda node_id: _node_order(nodes[node_id]),
        )
        for neighbor in neighbors:
            if len(selected) == limit:
                break
            selected.add(neighbor)
            queue.append(neighbor)
    return selected


def _public_node(
    node: SupplyChainGraphNode,
    locale: str,
) -> PublicGraphNode:
    return PublicGraphNode(
        id=node.id,
        node_key=node.node_key,
        kind=node.kind,
        layer=node.layer,
        label=node.label_en if locale == "en" else node.label_zh,
        description=(node.description_en if locale == "en" else node.description_zh),
        symbol=node.symbol,
        cik=node.cik,
        importance=float(node.importance),
        confidence=node.confidence,
        rank=node.rank,
    )


def _public_edge(
    edge: SupplyChainGraphEdge,
    locale: str,
    importance: dict[str, float],
    citations: list[PublicGraphCitation],
) -> PublicGraphEdge:
    return PublicGraphEdge(
        id=edge.id,
        edge_key=edge.edge_key,
        source=edge.source_node_id,
        target=edge.target_node_id,
        relationship_type=edge.relationship_type,
        evidence_status=edge.evidence_status,
        confidence=edge.confidence,
        importance=importance[edge.edge_key],
        explanation=(edge.explanation_en if locale == "en" else edge.explanation_zh),
        citations=citations,
    )


def _public_citations(
    persisted: PersistedGraph,
    edges: list[SupplyChainGraphEdge],
) -> dict[UUID, list[PublicGraphCitation]]:
    edge_by_id = {edge.id: edge for edge in edges}
    result: dict[UUID, list[PublicGraphCitation]] = defaultdict(list)
    for citation in persisted.citations:
        edge = edge_by_id.get(citation.edge_id)
        if edge is None:
            continue
        source_key, confidence = _citation_metadata(persisted, edge, citation)
        result[edge.id].append(
            PublicGraphCitation(
                id=citation.id,
                source_id=citation.source_id,
                source_key=source_key,
                excerpt=citation.excerpt,
                locator=citation.source_anchor,
                support_role=citation.support_role,
                confidence=confidence,
            )
        )
    return result


def _citation_metadata(
    persisted: PersistedGraph,
    edge: SupplyChainGraphEdge,
    citation: GraphEdgeCitation,
) -> tuple[str, float]:
    for item in persisted.source_index[citation.source_id]:
        key = (
            edge.edge_key,
            item["source_key"],
            citation.excerpt,
            citation.source_anchor,
            citation.support_role,
        )
        if key in persisted.citation_confidence:
            return item["source_key"], persisted.citation_confidence[key]
    raise DomainError("GRAPH_CITATION_AUDIT_MISSING", 500)


def _public_sources(
    persisted: PersistedGraph,
    selected_ids: set[UUID],
    citations: dict[UUID, list[PublicGraphCitation]],
) -> list[PublicGraphSource]:
    selected_keys = {
        citation.source_id: citation.source_key
        for values in citations.values()
        for citation in values
    }
    rows = {source.id: source for source in persisted.sources}
    return [
        _public_source(
            rows[source_id],
            next(
                item
                for item in persisted.source_index[source_id]
                if item["source_key"] == selected_keys[source_id]
            ),
        )
        for source_id in sorted(selected_ids, key=str)
    ]


def _public_source(
    source: GraphOfficialSource,
    index: dict[str, str],
) -> PublicGraphSource:
    return PublicGraphSource(
        id=source.id,
        source_id=index["source_id"],
        source_key=index["source_key"],
        source_type=source.source_type,
        publisher=source.publisher,
        title=source.title,
        canonical_url=source.canonical_url,
        published_at=source.published_at,
    )


def _node_order(node: SupplyChainGraphNode) -> tuple[int, int, str]:
    return _LAYER_ORDER[node.layer], node.rank, node.node_key
