import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.supply_chain.schemas import (
    AcceptedGraph,
    GraphDraft,
    GraphEdgeDraft,
    GraphLocalization,
    GraphVerification,
    OfficialSourceDocument,
)
from app.supply_chain.validator import (
    GraphLocalizationError,
    validate_for_publication,
    validate_localization,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "supply_chain"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


@pytest.fixture
def draft() -> GraphDraft:
    return GraphDraft.model_validate(load_fixture("aapl_draft.json"))


@pytest.fixture
def verification() -> GraphVerification:
    return GraphVerification.model_validate(load_fixture("aapl_verification.json"))


@pytest.fixture
def sources() -> list[OfficialSourceDocument]:
    return [
        OfficialSourceDocument.model_validate(item)
        for item in load_fixture("aapl_sources.json")["documents"]
    ]


def validate(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
    *,
    min_nodes: int = 25,
    max_nodes: int = 40,
    evidence_threshold: float = 0.75,
) -> AcceptedGraph:
    return validate_for_publication(
        draft=draft,
        verification=verification,
        sources=sources,
        min_nodes=min_nodes,
        max_nodes=max_nodes,
        evidence_threshold=evidence_threshold,
    )


def update_decision(
    verification: GraphVerification,
    edge_key: str,
    **updates: object,
) -> GraphVerification:
    payload = verification.model_dump()
    decision = next(
        item for item in payload["edge_verifications"] if item["edge_key"] == edge_key
    )
    decision.update(updates)
    return GraphVerification.model_validate(payload)


def localized_payload(graph: AcceptedGraph) -> dict[str, Any]:
    def node_payload(node) -> dict[str, Any]:
        return {
            "node_key": node.node_key,
            "kind": node.kind,
            "layer": node.layer,
            "label_zh": f"中文 {node.label_en}",
            "description_zh": f"中文说明 {node.description_en}",
            "company_id": node.company_id,
            "symbol": node.symbol,
            "cik": node.cik,
            "importance": node.importance,
            "confidence": node.confidence,
            "rank": node.rank,
        }

    def edge_payload(edge) -> dict[str, Any]:
        return {
            "edge_key": edge.edge_key,
            "source_node_key": edge.source_node_key,
            "target_node_key": edge.target_node_key,
            "relationship_type": edge.relationship_type,
            "evidence_status": edge.evidence_status,
            "confidence": edge.confidence,
            "importance": edge.importance,
            "explanation_zh": f"中文说明 {edge.explanation_en}",
            "evidence_refs": [item.model_dump() for item in edge.evidence_refs],
        }

    return {
        "locale": "zh",
        "focus_node_key": graph.focus_node_key,
        "thesis_zh": f"中文 {graph.thesis_en}",
        "nodes": [node_payload(node) for node in graph.accepted_nodes],
        "public_edges": [edge_payload(edge) for edge in graph.public_edges],
        "potential_edges": [edge_payload(edge) for edge in graph.potential_edges],
        "internal_edges": [edge_payload(edge) for edge in graph.internal_edges],
    }


def test_valid_graph_separates_verified_potential_and_rejected_edges(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    result = validate(draft, verification, sources)

    assert result.status == "completed"
    assert len(result.accepted_nodes) == 25
    assert all(edge.evidence_status == "verified" for edge in result.public_edges)
    assert all(edge.evidence_status == "potential" for edge in result.potential_edges)
    assert all(edge.evidence_status == "internal" for edge in result.internal_edges)
    assert result.rejected_edges[0].edge_key == (
        "company:arm|manufactures_for|company:0000320193"
    )
    assert result.evidence_coverage >= 0.75


def test_unknown_evidence_source_blocks_minimum_graph(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    edge_key = draft.edges[0].edge_key
    invalid = update_decision(
        verification,
        edge_key,
        evidence_refs=[
            {
                "source_key": "source:unknown-official-record",
                "excerpt": (
                    "TSMC Semiconductor Manufacturing fabricates Apple-designed "
                    "silicon used across Apple products."
                ),
                "locator": "Supplier fixture paragraph 1",
                "support_role": "primary",
                "confidence": 0.98,
            }
        ],
    )

    result = validate(draft, invalid, sources)

    assert result.status == "insufficient_evidence"
    assert "UNKNOWN_SOURCE_KEY" in result.reason_codes
    assert edge_key not in {edge.edge_key for edge in result.public_edges}


def test_verified_evidence_supersedes_draft_evidence(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    payload = draft.model_dump()
    edge_key = payload["edges"][0]["edge_key"]
    payload["edges"][0]["evidence_refs"][0]["excerpt"] = (
        "An extraction-stage paraphrase that is absent from the source."
    )

    result = validate(GraphDraft.model_validate(payload), verification, sources)

    assert edge_key in {edge.edge_key for edge in result.public_edges}


def test_known_source_paraphrase_does_not_block_graph(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    draft_payload = draft.model_dump()
    verification_payload = verification.model_dump()
    edge_key = draft_payload["edges"][0]["edge_key"]
    excerpt = "A concise paraphrase attributed to the existing official source."
    draft_payload["edges"][0]["evidence_refs"][0]["excerpt"] = excerpt
    decision = next(
        item
        for item in verification_payload["edge_verifications"]
        if item["edge_key"] == edge_key
    )
    decision["evidence_refs"][0]["excerpt"] = excerpt

    result = validate(
        GraphDraft.model_validate(draft_payload),
        GraphVerification.model_validate(verification_payload),
        sources,
    )

    assert edge_key in {edge.edge_key for edge in result.public_edges}


def test_focus_must_connect_to_upstream_and_downstream_paths(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    payload = verification.model_dump()
    focus = draft.focus_node_key
    endpoints = {
        edge.edge_key: {edge.source_node_key, edge.target_node_key}
        for edge in draft.edges
    }
    for decision in payload["edge_verifications"]:
        if focus in endpoints[decision["edge_key"]]:
            decision["verdict"] = "rejected"
    disconnected = GraphVerification.model_validate(payload)

    result = validate(draft, disconnected, sources)

    assert result.status == "insufficient_evidence"
    assert "FOCUS_DISCONNECTED" in result.reason_codes


def test_low_confidence_verified_decision_is_downgraded(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    edge_key = draft.edges[0].edge_key
    low_confidence = update_decision(verification, edge_key, confidence=0.5)

    result = validate(draft, low_confidence, sources)

    assert edge_key not in {edge.edge_key for edge in result.public_edges}
    assert edge_key in {edge.edge_key for edge in result.potential_edges}
    assert "VERIFIED_CONFIDENCE_BELOW_THRESHOLD" in result.reason_codes


def test_missing_upstream_layer_blocks_publication(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    payload = draft.model_dump()
    for node in payload["nodes"]:
        if node["layer"] == "upstream":
            node["layer"] = "core"

    result = validate(GraphDraft.model_validate(payload), verification, sources)

    assert result.status == "insufficient_evidence"
    assert "UPSTREAM_PATH_MISSING" in result.reason_codes


def test_ambiguous_entity_is_retained_only_in_internal_audit(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    payload = draft.model_dump()
    payload["nodes"][0].update(
        {
            "resolution_status": "ambiguous",
            "resolution_basis": "ambiguous_name",
        }
    )

    result = validate(GraphDraft.model_validate(payload), verification, sources)

    assert result.status == "insufficient_evidence"
    assert "AMBIGUOUS_ENTITY" in result.reason_codes
    assert payload["nodes"][0]["node_key"] not in {
        node.node_key for node in result.accepted_nodes
    }


def test_duplicate_source_keys_fail_unique_key_integrity(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    result = validate(draft, verification, [*sources, sources[0]])

    assert result.status == "insufficient_evidence"
    assert result.reason_codes == ["DUPLICATE_SOURCE_KEY"]
    assert len({source.source_key for source in result.sources}) == len(result.sources)


def test_cycle_and_duplicate_semantic_edge_are_pruned(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    payload = draft.model_dump()
    verification_payload = verification.model_dump()
    base_edge = deepcopy(payload["edges"][0])
    duplicate = deepcopy(base_edge)
    duplicate["edge_key"] = "duplicate:tsmc-supplies-silicon"
    cycle = deepcopy(base_edge)
    cycle.update(
        {
            "edge_key": "cycle:apple-sells-to-tsmc",
            "source_node_key": draft.focus_node_key,
            "target_node_key": "company:tsmc",
            "relationship_type": "sells_to",
            "confidence": 1.0,
            "importance": 1.0,
        }
    )
    payload["edges"].extend([duplicate, cycle])
    for edge in (duplicate, cycle):
        decision = deepcopy(verification_payload["edge_verifications"][0])
        decision["edge_key"] = edge["edge_key"]
        decision["confidence"] = edge["confidence"]
        verification_payload["edge_verifications"].append(decision)

    result = validate(
        GraphDraft.model_validate(payload),
        GraphVerification.model_validate(verification_payload),
        sources,
    )

    accepted_keys = {
        edge.edge_key for edge in [*result.public_edges, *result.potential_edges]
    }
    assert duplicate["edge_key"] not in accepted_keys
    assert "DUPLICATE_SEMANTIC_EDGE" in result.reason_codes
    assert "GRAPH_CYCLE" in result.reason_codes
    assert "company:0000320193|sells_to|business:enterprise-channels" in accepted_keys


def test_self_edge_fails_schema_integrity_gate(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    bad_edge = GraphEdgeDraft.model_construct(
        **{
            **draft.edges[0].model_dump(),
            "edge_key": "self:focus",
            "source_node_key": draft.focus_node_key,
            "target_node_key": draft.focus_node_key,
        }
    )
    unsafe = GraphDraft.model_construct(
        focus_node_key=draft.focus_node_key,
        thesis_en=draft.thesis_en,
        nodes=draft.nodes,
        edges=[bad_edge, *draft.edges],
    )

    result = validate(unsafe, verification, sources)

    assert result.status == "insufficient_evidence"
    assert "SELF_EDGE" in result.reason_codes


def test_orphans_are_pruned_and_node_ranking_is_deterministic(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    payload = draft.model_dump()
    verification_payload = verification.model_dump()
    evidence = deepcopy(payload["edges"][0]["evidence_refs"])
    for index in range(15):
        node_key = f"company:rank-{index:02d}"
        payload["nodes"].append(
            {
                "node_key": node_key,
                "kind": "company",
                "layer": "upstream",
                "label_en": f"Ranked Supplier {index}",
                "description_en": f"Synthetic ranked supplier {index} for tests.",
                "importance": (index + 1) / 20,
                "confidence": 0.9,
                "rank": index + 20,
            }
        )
        edge_key = f"{node_key}|supplies|{draft.focus_node_key}"
        payload["edges"].append(
            {
                "edge_key": edge_key,
                "source_node_key": node_key,
                "target_node_key": draft.focus_node_key,
                "relationship_type": "supplies",
                "evidence_status": "verified",
                "confidence": 0.9,
                "importance": (index + 1) / 20,
                "explanation_en": "Synthetic ranked supplier relationship.",
                "evidence_refs": evidence,
            }
        )
        verification_payload["edge_verifications"].append(
            {
                "edge_key": edge_key,
                "verdict": "verified",
                "confidence": 0.9,
                "reason_en": "The immutable fixture supports the ranked test edge.",
                "evidence_refs": evidence,
            }
        )
    ranked_draft = GraphDraft.model_validate(payload)
    ranked_verification = GraphVerification.model_validate(verification_payload)

    first = validate(
        ranked_draft,
        ranked_verification,
        sources,
        min_nodes=25,
        max_nodes=30,
    )
    second = validate(
        ranked_draft,
        ranked_verification,
        sources,
        min_nodes=25,
        max_nodes=30,
    )

    assert len(first.accepted_nodes) == 30
    assert [node.node_key for node in first.accepted_nodes] == [
        node.node_key for node in second.accepted_nodes
    ]
    assert first.focus_node_key in {node.node_key for node in first.accepted_nodes}
    assert {node.layer for node in first.accepted_nodes} >= {"upstream", "downstream"}


def test_localization_preserves_all_structural_and_evidence_invariants(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    graph = validate(draft, verification, sources)
    localization = GraphLocalization.model_validate(localized_payload(graph))

    assert validate_localization(graph=graph, localization=localization) is localization


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda payload: payload["nodes"][0].update(
                {"node_key": "company:changed-by-translator"}
            ),
            "LOCALIZATION_NODE_KEYS_CHANGED",
        ),
        (
            lambda payload: payload["public_edges"][0]["evidence_refs"][0].update(
                {"excerpt": "Translator changed this immutable evidence excerpt."}
            ),
            "LOCALIZATION_EDGE_INVARIANT_CHANGED",
        ),
    ],
)
def test_invalid_localization_is_retryable(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
    mutate,
    code: str,
) -> None:
    graph = validate(draft, verification, sources)
    payload = localized_payload(graph)
    mutate(payload)
    localization = GraphLocalization.model_validate(payload)

    with pytest.raises(GraphLocalizationError) as error:
        validate_localization(graph=graph, localization=localization)

    assert error.value.code == code
    assert error.value.retryable is True


def test_duplicate_localization_keys_are_rejected(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    graph = validate(draft, verification, sources)
    payload = localized_payload(graph)
    payload["nodes"].append(deepcopy(payload["nodes"][0]))
    localization = GraphLocalization.model_validate(payload)

    with pytest.raises(GraphLocalizationError) as error:
        validate_localization(graph=graph, localization=localization)

    assert error.value.code == "LOCALIZATION_NODE_KEYS_CHANGED"


def test_localization_preserves_numeric_content(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    graph = validate(draft, verification, sources)
    graph_payload = graph.model_dump()
    graph_payload["accepted_nodes"][0]["description_en"] = (
        "Supplies 3 component platforms documented in 2025."
    )
    graph = AcceptedGraph.model_validate(graph_payload)
    payload = localized_payload(graph)
    payload["nodes"][0]["description_zh"] = "供应 4 个记录于 2025 年的组件平台。"
    localization = GraphLocalization.model_validate(payload)

    with pytest.raises(GraphLocalizationError) as error:
        validate_localization(graph=graph, localization=localization)

    assert error.value.code == "LOCALIZATION_NUMERIC_CONTENT_CHANGED"


def test_localization_requires_chinese_translated_text(
    draft: GraphDraft,
    verification: GraphVerification,
    sources: list[OfficialSourceDocument],
) -> None:
    graph = validate(draft, verification, sources)
    payload = localized_payload(graph)
    payload["thesis_zh"] = graph.thesis_en
    localization = GraphLocalization.model_validate(payload)

    with pytest.raises(GraphLocalizationError) as error:
        validate_localization(graph=graph, localization=localization)

    assert error.value.code == "LOCALIZATION_TEXT_NOT_CHINESE"
