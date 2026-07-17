from collections.abc import Sequence
from typing import Literal

from app.supply_chain.schemas import (
    EdgeRejection,
    EdgeVerification,
    GraphDraft,
    GraphEdgeDraft,
    OfficialSourceDocument,
    OfficialSourceMetadata,
)

_SOURCE_METADATA_FIELDS = {
    "source_id",
    "source_key",
    "source_type",
    "publisher",
    "title",
    "canonical_url",
    "published_at",
}


def evidence_coverage(edges: Sequence[GraphEdgeDraft]) -> float:
    weighted_total = sum(max(edge.importance, 0.1) for edge in edges)
    weighted_supported = sum(
        max(edge.importance, 0.1)
        for edge in edges
        if edge.evidence_status == "verified" and edge.evidence_refs
    )
    return weighted_supported / weighted_total if weighted_total else 0.0


def apply_edge_gates(
    *,
    draft: GraphDraft,
    verification_by_edge: dict[str, EdgeVerification],
    sources: list[OfficialSourceDocument],
    evidence_threshold: float,
) -> tuple[list[GraphEdgeDraft], list[GraphEdgeDraft], list[EdgeRejection], list[str]]:
    source_map = {source.source_key: source for source in sources}
    ambiguous = {
        node.node_key for node in draft.nodes if node.resolution_status == "ambiguous"
    }
    accepted: list[GraphEdgeDraft] = []
    internal: list[GraphEdgeDraft] = []
    rejected: list[EdgeRejection] = []
    reasons: list[str] = []
    for edge in draft.edges:
        decision = verification_by_edge[edge.edge_key]
        code = _edge_rejection_code(edge, decision, source_map, ambiguous)
        if code is not None:
            reasons.append(code)
            rejected.append(_rejection(edge, decision, code))
            internal.append(_as_internal(edge, decision))
            continue
        status = decision.verdict
        if status == "verified" and decision.confidence < evidence_threshold:
            status = "potential"
            reasons.append("VERIFIED_CONFIDENCE_BELOW_THRESHOLD")
        accepted.append(
            edge.model_copy(
                update={
                    "evidence_status": status,
                    "confidence": min(edge.confidence, decision.confidence),
                    "evidence_refs": list(decision.evidence_refs),
                }
            )
        )
    return accepted, internal, rejected, reasons


def source_integrity(
    sources: list[OfficialSourceDocument],
) -> tuple[list[OfficialSourceMetadata], list[str]]:
    by_key: dict[str, OfficialSourceMetadata] = {}
    source_ids: list[str] = []
    for source in sources:
        by_key.setdefault(source.source_key, _source_metadata(source))
        source_ids.append(source.source_id)
    codes = []
    if len(by_key) != len(sources):
        codes.append("DUPLICATE_SOURCE_KEY")
    elif len(source_ids) != len(set(source_ids)):
        codes.append("DUPLICATE_SOURCE_ID")
    return list(by_key.values()), codes


def simple_rejection(
    edge: GraphEdgeDraft,
    code: str,
    *,
    verdict: Literal["rejected", "conflicted"] = "rejected",
) -> EdgeRejection:
    return EdgeRejection(
        edge_key=edge.edge_key,
        verdict=verdict,
        reason_en=f"{code}: deterministic publication gate rejected this edge.",
        evidence_refs=tuple(edge.evidence_refs),
    )


def _edge_rejection_code(
    edge: GraphEdgeDraft,
    decision: EdgeVerification,
    sources: dict[str, OfficialSourceDocument],
    ambiguous: set[str],
) -> str | None:
    if decision.verdict in {"rejected", "conflicted"}:
        return f"VERIFICATION_{decision.verdict.upper()}"
    if {edge.source_node_key, edge.target_node_key} & ambiguous:
        return "AMBIGUOUS_ENTITY"
    for reference in decision.evidence_refs:
        source = sources.get(reference.source_key)
        if source is None:
            return "UNKNOWN_SOURCE_KEY"
    return None


def _rejection(
    edge: GraphEdgeDraft,
    decision: EdgeVerification,
    code: str,
) -> EdgeRejection:
    verdict = (
        decision.verdict
        if decision.verdict in {"rejected", "conflicted"}
        else "rejected"
    )
    return simple_rejection(
        edge.model_copy(
            update={"evidence_refs": list(decision.evidence_refs or edge.evidence_refs)}
        ),
        code,
        verdict=verdict,
    )


def _as_internal(
    edge: GraphEdgeDraft,
    decision: EdgeVerification,
) -> GraphEdgeDraft:
    return edge.model_copy(
        update={
            "evidence_status": "internal",
            "confidence": min(edge.confidence, decision.confidence),
            "evidence_refs": list(decision.evidence_refs or edge.evidence_refs),
        }
    )


def _source_metadata(source: OfficialSourceDocument) -> OfficialSourceMetadata:
    return OfficialSourceMetadata.model_validate(
        source.model_dump(include=_SOURCE_METADATA_FIELDS)
    )
