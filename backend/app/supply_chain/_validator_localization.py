import re
from collections import Counter

from app.supply_chain.schemas import (
    AcceptedGraph,
    GraphEdgeDraft,
    GraphLocalization,
    GraphNodeDraft,
    LocalizedGraphEdge,
    LocalizedGraphNode,
)

_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)*%?")


class GraphLocalizationError(ValueError):
    retryable = True

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_localization(
    *,
    graph: AcceptedGraph,
    localization: GraphLocalization,
) -> GraphLocalization:
    if localization.focus_node_key != graph.focus_node_key:
        raise GraphLocalizationError("LOCALIZATION_FOCUS_CHANGED")
    _validate_translated_text(graph.thesis_en, localization.thesis_zh)
    nodes = {node.node_key: node for node in graph.accepted_nodes}
    localized_nodes = {node.node_key: node for node in localization.nodes}
    if len(localization.nodes) != len(localized_nodes) or set(nodes) != set(
        localized_nodes
    ):
        raise GraphLocalizationError("LOCALIZATION_NODE_KEYS_CHANGED")
    for key, node in nodes.items():
        _validate_localized_node(node, localized_nodes[key])
    groups = (
        (graph.public_edges, localization.public_edges),
        (graph.potential_edges, localization.potential_edges),
        (graph.internal_edges, localization.internal_edges),
    )
    for original, localized in groups:
        _validate_localized_edges(original, localized)
    return localization


def _validate_localized_node(
    node: GraphNodeDraft,
    localized: LocalizedGraphNode,
) -> None:
    invariant = (
        node.kind,
        node.layer,
        node.company_id,
        node.symbol,
        node.cik,
        node.importance,
        node.confidence,
        node.rank,
    )
    localized_invariant = (
        localized.kind,
        localized.layer,
        localized.company_id,
        localized.symbol,
        localized.cik,
        localized.importance,
        localized.confidence,
        localized.rank,
    )
    if invariant != localized_invariant:
        raise GraphLocalizationError("LOCALIZATION_NODE_INVARIANT_CHANGED")
    _validate_translated_text(
        f"{node.label_en} {node.description_en}",
        f"{localized.label_zh} {localized.description_zh}",
        chinese_text=localized.description_zh,
    )


def _validate_localized_edges(
    edges: list[GraphEdgeDraft],
    localized_edges: list[LocalizedGraphEdge],
) -> None:
    originals = {edge.edge_key: edge for edge in edges}
    localized = {edge.edge_key: edge for edge in localized_edges}
    if len(localized_edges) != len(localized) or set(originals) != set(localized):
        raise GraphLocalizationError("LOCALIZATION_EDGE_KEYS_CHANGED")
    for key, edge in originals.items():
        translated = localized[key]
        invariant = (
            edge.source_node_key,
            edge.target_node_key,
            edge.relationship_type,
            edge.evidence_status,
            edge.confidence,
            edge.importance,
            edge.evidence_refs,
        )
        translated_invariant = (
            translated.source_node_key,
            translated.target_node_key,
            translated.relationship_type,
            translated.evidence_status,
            translated.confidence,
            translated.importance,
            translated.evidence_refs,
        )
        if invariant != translated_invariant:
            raise GraphLocalizationError("LOCALIZATION_EDGE_INVARIANT_CHANGED")
        _validate_translated_text(edge.explanation_en, translated.explanation_zh)


def _validate_translated_text(
    original: str,
    translated: str,
    *,
    chinese_text: str | None = None,
) -> None:
    if Counter(_NUMBER_PATTERN.findall(original)) != Counter(
        _NUMBER_PATTERN.findall(translated)
    ):
        raise GraphLocalizationError("LOCALIZATION_NUMERIC_CONTENT_CHANGED")
    if _CJK_PATTERN.search(chinese_text or translated) is None:
        raise GraphLocalizationError("LOCALIZATION_TEXT_NOT_CHINESE")
