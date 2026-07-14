from collections.abc import Iterable
from typing import Literal

from app.supply_chain._validator_evidence import (
    apply_edge_gates,
    evidence_coverage,
    simple_rejection,
    source_integrity,
)
from app.supply_chain._validator_localization import (
    GraphLocalizationError,
    validate_localization,
)
from app.supply_chain._validator_topology import (
    deduplicate_edges,
    remove_cycles,
    select_public_topology,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    EdgeRejection,
    GraphDraft,
    GraphEdgeDraft,
    GraphVerification,
    OfficialSourceDocument,
    OfficialSourceMetadata,
)

__all__ = [
    "GraphLocalizationError",
    "evidence_coverage",
    "validate_for_publication",
    "validate_localization",
]


def validate_for_publication(
    *,
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
    min_nodes: int,
    max_nodes: int,
    evidence_threshold: float,
) -> AcceptedGraph:
    _validate_limits(min_nodes, max_nodes, evidence_threshold)
    metadata, source_codes = source_integrity(sources)
    if source_codes:
        return _integrity_failure(draft, metadata, max_nodes, source_codes)
    integrity_codes = _integrity_codes(draft, verification)
    if integrity_codes:
        return _integrity_failure(draft, metadata, max_nodes, integrity_codes)

    accepted, internal, rejected, reasons = apply_edge_gates(
        draft=draft,
        verification_by_edge={
            decision.edge_key: decision for decision in verification.edge_verifications
        },
        sources=sources,
        evidence_threshold=evidence_threshold,
    )
    accepted, duplicates = deduplicate_edges(accepted)
    _record_pruned_edges(
        duplicates,
        code="DUPLICATE_SEMANTIC_EDGE",
        reasons=reasons,
        internal=internal,
        rejected=rejected,
    )
    accepted, cyclic = remove_cycles(accepted)
    _record_pruned_edges(
        cyclic,
        code="GRAPH_CYCLE",
        verdict="conflicted",
        reasons=reasons,
        internal=internal,
        rejected=rejected,
    )
    nodes, accepted, topology = select_public_topology(
        draft=draft,
        edges=accepted,
        max_nodes=max_nodes,
    )
    reasons.extend(topology)
    selected_keys = {node.node_key for node in nodes}
    internal = [
        edge
        for edge in _unique_edges(internal)
        if {edge.source_node_key, edge.target_node_key} <= selected_keys
    ]
    verified = _edges_with_status(accepted, "verified")
    potential = _edges_with_status(accepted, "potential")
    coverage = evidence_coverage([*verified, *potential])
    status = _publication_status(
        reasons=reasons,
        node_count=len(nodes),
        min_nodes=min_nodes,
        coverage=coverage,
        evidence_threshold=evidence_threshold,
    )
    return AcceptedGraph(
        status=status,
        focus_node_key=draft.focus_node_key,
        thesis_en=draft.thesis_en,
        accepted_nodes=nodes,
        public_edges=verified,
        potential_edges=potential,
        internal_edges=sorted(internal, key=lambda edge: edge.edge_key),
        rejected_edges=sorted(rejected, key=lambda item: item.edge_key),
        sources=metadata,
        evidence_coverage=coverage,
        overall_confidence=_confidence_label(coverage, bool(accepted)),
        reason_codes=_unique(reasons),
    )


def _record_pruned_edges(
    edges: list[GraphEdgeDraft],
    *,
    code: str,
    reasons: list[str],
    internal: list[GraphEdgeDraft],
    rejected: list[EdgeRejection],
    verdict: Literal["rejected", "conflicted"] = "rejected",
) -> None:
    for edge in edges:
        reasons.append(code)
        rejected.append(simple_rejection(edge, code, verdict=verdict))
        internal.append(edge.model_copy(update={"evidence_status": "internal"}))


def _publication_status(
    *,
    reasons: list[str],
    node_count: int,
    min_nodes: int,
    coverage: float,
    evidence_threshold: float,
) -> Literal["completed", "insufficient_evidence"]:
    blocking = {
        "FOCUS_DISCONNECTED",
        "UPSTREAM_PATH_MISSING",
        "DOWNSTREAM_PATH_MISSING",
        "NODE_BUDGET_UNSATISFIED",
    }
    if node_count < min_nodes:
        reasons.append("MINIMUM_NODE_COUNT_NOT_MET")
        blocking.add("MINIMUM_NODE_COUNT_NOT_MET")
    if coverage < evidence_threshold:
        reasons.append("EVIDENCE_COVERAGE_BELOW_THRESHOLD")
        blocking.add("EVIDENCE_COVERAGE_BELOW_THRESHOLD")
    return "insufficient_evidence" if blocking.intersection(reasons) else "completed"


def _integrity_codes(
    draft: GraphDraft,
    verification: GraphVerification,
) -> list[str]:
    codes: list[str] = []
    node_keys = [node.node_key for node in draft.nodes]
    edge_keys = [edge.edge_key for edge in draft.edges]
    if len(node_keys) != len(set(node_keys)):
        codes.append("DUPLICATE_NODE_KEY")
    if node_keys.count(draft.focus_node_key) != 1:
        codes.append("FOCUS_NODE_INVALID")
    if len(edge_keys) != len(set(edge_keys)):
        codes.append("DUPLICATE_EDGE_KEY")
    known = set(node_keys)
    for edge in draft.edges:
        if edge.source_node_key == edge.target_node_key:
            codes.append("SELF_EDGE")
        if {edge.source_node_key, edge.target_node_key} - known:
            codes.append("UNKNOWN_EDGE_ENDPOINT")
    verification_keys = [item.edge_key for item in verification.edge_verifications]
    if set(verification_keys) != set(edge_keys):
        codes.append("VERIFICATION_EDGE_SET_MISMATCH")
    return _unique(codes)


def _integrity_failure(
    draft: GraphDraft,
    sources: list[OfficialSourceMetadata],
    max_nodes: int,
    codes: list[str],
) -> AcceptedGraph:
    unique_nodes = {node.node_key: node for node in draft.nodes}
    if draft.focus_node_key not in unique_nodes:
        raise ValueError("invalid graph has no usable focus node")
    nodes = [unique_nodes[draft.focus_node_key]]
    nodes.extend(
        node
        for key, node in sorted(unique_nodes.items())
        if key != draft.focus_node_key
    )
    return AcceptedGraph(
        status="insufficient_evidence",
        focus_node_key=draft.focus_node_key,
        thesis_en=draft.thesis_en,
        accepted_nodes=nodes[:max_nodes],
        sources=sources,
        evidence_coverage=0.0,
        reason_codes=codes,
    )


def _edges_with_status(
    edges: list[GraphEdgeDraft],
    status: Literal["verified", "potential"],
) -> list[GraphEdgeDraft]:
    return sorted(
        (edge for edge in edges if edge.evidence_status == status),
        key=lambda edge: edge.edge_key,
    )


def _unique_edges(edges: list[GraphEdgeDraft]) -> list[GraphEdgeDraft]:
    return list({edge.edge_key: edge for edge in edges}.values())


def _confidence_label(coverage: float, has_edges: bool) -> str | None:
    if not has_edges:
        return None
    if coverage >= 0.85:
        return "High"
    if coverage >= 0.75:
        return "Medium"
    return "Low"


def _validate_limits(
    min_nodes: int,
    max_nodes: int,
    evidence_threshold: float,
) -> None:
    if not 1 <= min_nodes <= max_nodes <= 40:
        raise ValueError("graph node limits are invalid")
    if not 0 <= evidence_threshold <= 1:
        raise ValueError("evidence threshold is invalid")


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))
