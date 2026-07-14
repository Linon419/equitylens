import inspect
import json
from copy import deepcopy
from inspect import Parameter
from pathlib import Path
from typing import Literal, get_type_hints

import pytest
from pydantic import ValidationError

from app.supply_chain.contracts import (
    EntityResolver,
    GraphArtifactStore,
    GraphQuotaLedger,
    OfficialSourceCollector,
    OfficialSourceTools,
    SupplyChainAgent,
    SupplyChainGraphRepository,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    CompanyIdentity,
    EvidenceReference,
    GraphDraft,
    GraphLocalization,
    GraphRefreshRequest,
    GraphRefreshResponse,
    GraphVerification,
    OfficialSourceDocument,
    OfficialSourceMetadata,
    PublicGraphCitation,
    PublicGraphSnapshotSummary,
    SourcePlan,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "supply_chain"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


@pytest.fixture
def source_payload() -> dict:
    return load_fixture("aapl_sources.json")


@pytest.fixture
def draft_payload() -> dict:
    return load_fixture("aapl_draft.json")


@pytest.fixture
def verification_payload() -> dict:
    return load_fixture("aapl_verification.json")


def test_aapl_source_fixture_is_strict_and_serialization_safe(
    source_payload: dict,
) -> None:
    company = CompanyIdentity.model_validate(source_payload["company"])
    documents = [
        OfficialSourceDocument.model_validate(document)
        for document in source_payload["documents"]
    ]
    plan = SourcePlan.model_validate(source_payload["source_plan"])

    assert company.symbol == "AAPL"
    assert company.cik == "0000320193"
    assert len(documents) == len(plan.selected_source_ids)
    assert {document.source_id for document in documents} == set(
        plan.selected_source_ids
    )
    assert all("FIXTURE DATA" in document.body_text for document in documents)
    assert all(
        document.model_dump(mode="json")["canonical_url"]
        == source_payload["documents"][index]["canonical_url"]
        for index, document in enumerate(documents)
    )


def test_aapl_draft_fixture_has_required_supply_chain_coverage(
    draft_payload: dict,
) -> None:
    draft = GraphDraft.model_validate(draft_payload)
    labels = {node.label_en for node in draft.nodes}

    assert len(draft.nodes) == 25
    assert {node.layer for node in draft.nodes} == {
        "upstream",
        "core",
        "downstream",
    }
    assert draft.focus_node_key == "company:0000320193"
    assert labels >= {
        "TSMC Semiconductor Manufacturing",
        "Samsung Display Components",
        "SK hynix Memory",
        "Foxconn Contract Manufacturing",
        "Apple Inc.",
        "iPhone",
        "Mac",
        "Apple Services",
        "US Wireless Carriers",
        "Technology Distributors",
        "Enterprise Channels",
        "Consumer End Markets",
    }
    assert sum(edge.evidence_status == "potential" for edge in draft.edges) >= 2
    assert len(draft.edges) == 28
    assert sum(edge.evidence_status == "verified" for edge in draft.edges) == 23
    assert sum(edge.evidence_status == "potential" for edge in draft.edges) == 4
    assert sum(edge.evidence_status == "internal" for edge in draft.edges) == 1
    assert all(edge.evidence_refs for edge in draft.edges)


def test_every_draft_excerpt_occurs_in_its_source_document(
    source_payload: dict,
    draft_payload: dict,
    verification_payload: dict,
) -> None:
    documents = {
        document.source_key: document
        for document in (
            OfficialSourceDocument.model_validate(item)
            for item in source_payload["documents"]
        )
    }
    draft = GraphDraft.model_validate(draft_payload)

    for edge in draft.edges:
        for evidence in edge.evidence_refs:
            assert evidence.source_key in documents
            assert evidence.excerpt in documents[evidence.source_key].body_text
    verification = GraphVerification.model_validate(verification_payload)
    for decision in verification.edge_verifications:
        for evidence in decision.evidence_refs:
            assert evidence.source_key in documents
            assert evidence.excerpt in documents[evidence.source_key].body_text


def test_aapl_verification_fixture_includes_adversarial_rejection(
    verification_payload: dict,
    draft_payload: dict,
) -> None:
    verification = GraphVerification.model_validate(verification_payload)
    draft = GraphDraft.model_validate(draft_payload)

    rejected = [
        decision
        for decision in verification.edge_verifications
        if decision.verdict == "rejected"
    ]
    assert [decision.edge_key for decision in verification.edge_verifications] == [
        edge.edge_key for edge in draft.edges
    ]
    assert rejected
    assert any("unsupported" in decision.reason_en.lower() for decision in rejected)


def test_empty_draft_has_representable_empty_verification() -> None:
    draft = GraphDraft.model_validate(
        {
            "focus_node_key": "company:focus",
            "thesis_en": "A valid graph can contain a focus node with zero edges.",
            "nodes": [
                {
                    "node_key": "company:focus",
                    "kind": "company",
                    "layer": "core",
                    "label_en": "Focus Company",
                    "description_en": "The focus company for an empty-edge graph.",
                    "importance": 1.0,
                    "confidence": 1.0,
                }
            ],
            "edges": [],
        }
    )
    verification = GraphVerification.model_validate({"edge_verifications": []})

    assert draft.edges == []
    assert verification.edge_verifications == []


def test_public_snapshot_matches_designed_api_shape() -> None:
    snapshot = PublicGraphSnapshotSummary.model_validate(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "status": "completed",
            "symbol": "AAPL",
            "model_id": "gpt-5-mini-2026-07-14",
            "focus_node_key": "company:0000320193",
            "thesis": "Apple operates a multi-layer supply-chain graph.",
            "evidence_coverage": "complete",
            "overall_confidence": "High",
            "node_count": 25,
            "edge_count": 27,
            "generated_at": "2026-07-14T00:00:00Z",
        }
    )

    assert snapshot.symbol == "AAPL"
    assert snapshot.model_id == "gpt-5-mini-2026-07-14"
    assert snapshot.evidence_coverage == "complete"


def test_public_snapshot_rejects_numeric_evidence_coverage() -> None:
    with pytest.raises(ValidationError):
        PublicGraphSnapshotSummary.model_validate(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "status": "completed",
                "symbol": "AAPL",
                "model_id": "gpt-5-mini-2026-07-14",
                "focus_node_key": "company:0000320193",
                "thesis": "Apple operates a multi-layer supply-chain graph.",
                "evidence_coverage": 1.0,
                "overall_confidence": "High",
                "node_count": 25,
                "edge_count": 27,
                "generated_at": "2026-07-14T00:00:00Z",
            }
        )


@pytest.mark.parametrize(
    "status_payload",
    [
        {
            "status": "accepted",
            "job_id": "00000000-0000-0000-0000-000000000001",
        },
        {
            "status": "active_job",
            "job_id": "00000000-0000-0000-0000-000000000001",
        },
        {
            "status": "reused_snapshot",
            "snapshot_id": "00000000-0000-0000-0000-000000000002",
        },
    ],
)
def test_refresh_response_accepts_usable_status_reference(status_payload: dict) -> None:
    response = GraphRefreshResponse.model_validate(
        {
            **status_payload,
            "quota": {
                "limit": 2,
                "used": 1,
                "remaining": 1,
                "resets_at": "2026-07-15T00:00:00Z",
            },
        }
    )

    assert response.status == status_payload["status"]


@pytest.mark.parametrize("status", ["accepted", "active_job", "reused_snapshot"])
def test_refresh_response_rejects_status_without_usable_reference(status: str) -> None:
    with pytest.raises(ValidationError, match="requires"):
        GraphRefreshResponse.model_validate(
            {
                "status": status,
                "quota": {
                    "limit": 2,
                    "used": 1,
                    "remaining": 1,
                    "resets_at": "2026-07-15T00:00:00Z",
                },
            }
        )


@pytest.mark.parametrize("value", [-0.01, 1.01])
@pytest.mark.parametrize(
    "path",
    [
        ("nodes", 0, "confidence"),
        ("nodes", 0, "importance"),
        ("edges", 0, "confidence"),
        ("edges", 0, "importance"),
        ("edges", 0, "evidence_refs", 0, "confidence"),
    ],
)
def test_graph_rejects_out_of_range_scores(
    draft_payload: dict,
    path: tuple[str | int, ...],
    value: float,
) -> None:
    invalid = deepcopy(draft_payload)
    target = invalid
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        GraphDraft.model_validate(invalid)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_graph_rejects_non_finite_scores(
    draft_payload: dict,
    value: float,
) -> None:
    invalid = deepcopy(draft_payload)
    invalid["edges"][0]["confidence"] = value

    with pytest.raises(ValidationError):
        GraphDraft.model_validate(invalid)


def test_graph_rejects_duplicate_node_keys(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    invalid["nodes"][1]["node_key"] = invalid["nodes"][0]["node_key"]

    with pytest.raises(ValidationError, match="duplicate node keys"):
        GraphDraft.model_validate(invalid)


def test_graph_rejects_duplicate_edge_keys(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    invalid["edges"][1]["edge_key"] = invalid["edges"][0]["edge_key"]

    with pytest.raises(ValidationError, match="duplicate edge keys"):
        GraphDraft.model_validate(invalid)


def test_graph_rejects_duplicate_evidence_references(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    invalid["edges"][0]["evidence_refs"].append(
        deepcopy(invalid["edges"][0]["evidence_refs"][0])
    )

    with pytest.raises(ValidationError, match="duplicate evidence references"):
        GraphDraft.model_validate(invalid)


def test_graph_rejects_orphan_endpoint(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    invalid["edges"][0]["target_node_key"] = "company:missing"

    with pytest.raises(ValidationError, match="unknown endpoint"):
        GraphDraft.model_validate(invalid)


def test_graph_rejects_self_edge(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    invalid["edges"][0]["target_node_key"] = invalid["edges"][0]["source_node_key"]

    with pytest.raises(ValidationError, match="self-edge"):
        GraphDraft.model_validate(invalid)


def test_graph_rejects_missing_focus(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    invalid["focus_node_key"] = "company:missing"

    with pytest.raises(ValidationError, match="focus_node_key"):
        GraphDraft.model_validate(invalid)


def test_graph_rejects_more_than_forty_nodes(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    template = invalid["nodes"][-1]
    invalid["nodes"] = [
        {**template, "node_key": f"category:extra-{index}"} for index in range(41)
    ]
    invalid["focus_node_key"] = "category:extra-0"
    invalid["edges"] = []

    with pytest.raises(ValidationError):
        GraphDraft.model_validate(invalid)


@pytest.mark.parametrize("evidence_status", ["verified", "potential"])
def test_evidence_backed_edge_requires_reference(
    draft_payload: dict,
    evidence_status: str,
) -> None:
    invalid = deepcopy(draft_payload)
    invalid["edges"][0]["evidence_status"] = evidence_status
    invalid["edges"][0]["evidence_refs"] = []

    with pytest.raises(ValidationError, match="evidence reference"):
        GraphDraft.model_validate(invalid)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("nodes", 0, "label_en"), " "),
        (("nodes", 0, "description_en"), ""),
        (("thesis_en",), "\t"),
        (("edges", 0, "explanation_en"), " "),
    ],
)
def test_graph_rejects_blank_english_text(
    draft_payload: dict,
    path: tuple[str | int, ...],
    value: str,
) -> None:
    invalid = deepcopy(draft_payload)
    target = invalid
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValidationError):
        GraphDraft.model_validate(invalid)


def test_graph_rejects_unsupported_edge_type(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    invalid["edges"][0]["relationship_type"] = "owns"

    with pytest.raises(ValidationError):
        GraphDraft.model_validate(invalid)


def test_source_rejects_unsupported_source_type(source_payload: dict) -> None:
    invalid = deepcopy(source_payload["documents"][0])
    invalid["source_type"] = "news_article"

    with pytest.raises(ValidationError):
        OfficialSourceDocument.model_validate(invalid)


@pytest.mark.parametrize(
    "canonical_url",
    [
        "https:///x",
        "https://user:password@apple.com/fixture",
        "https://apple.com:invalid/fixture",
    ],
)
def test_source_rejects_malformed_or_credentialed_https_url(
    source_payload: dict,
    canonical_url: str,
) -> None:
    invalid = deepcopy(source_payload["documents"][0])
    invalid["canonical_url"] = canonical_url

    with pytest.raises(ValidationError, match="canonical_url"):
        OfficialSourceDocument.model_validate(invalid)


def test_source_preserves_valid_canonical_url_exactly(source_payload: dict) -> None:
    payload = deepcopy(source_payload["documents"][0])
    payload["canonical_url"] = "https://Apple.com:443/fixture%20path?x=1#section"

    source = OfficialSourceDocument.model_validate(payload)

    assert source.canonical_url == payload["canonical_url"]


@pytest.mark.parametrize("symbol", ["aapl", " AAPL "])
def test_company_identity_rejects_normalized_symbol(
    source_payload: dict,
    symbol: str,
) -> None:
    invalid = deepcopy(source_payload["company"])
    invalid["symbol"] = symbol

    with pytest.raises(ValidationError, match="symbol"):
        CompanyIdentity.model_validate(invalid)


def test_verification_rejects_duplicate_edge_decisions(
    verification_payload: dict,
) -> None:
    invalid = deepcopy(verification_payload)
    invalid["edge_verifications"].append(deepcopy(invalid["edge_verifications"][0]))

    with pytest.raises(ValidationError, match="duplicate edge verification"):
        GraphVerification.model_validate(invalid)


def test_verified_verdict_requires_evidence(verification_payload: dict) -> None:
    invalid = deepcopy(verification_payload)
    invalid["edge_verifications"][0]["verdict"] = "verified"
    invalid["edge_verifications"][0]["evidence_refs"] = []

    with pytest.raises(ValidationError, match="evidence reference"):
        GraphVerification.model_validate(invalid)


def test_source_plan_rejects_more_than_twenty_four_sources(
    source_payload: dict,
) -> None:
    invalid = deepcopy(source_payload["source_plan"])
    invalid["selected_source_ids"] = [f"source-{index}" for index in range(25)]

    with pytest.raises(ValidationError):
        SourcePlan.model_validate(invalid)


def test_source_plan_rejects_duplicate_source_ids(source_payload: dict) -> None:
    invalid = deepcopy(source_payload["source_plan"])
    invalid["selected_source_ids"].append(invalid["selected_source_ids"][0])

    with pytest.raises(ValidationError, match="duplicate selected source IDs"):
        SourcePlan.model_validate(invalid)


@pytest.mark.parametrize(
    ("schema", "payload"),
    [
        (GraphRefreshRequest, {"force_refresh": False, "unexpected": True}),
        (
            EvidenceReference,
            {
                "source_key": "source:apple-10k",
                "excerpt": "This evidence excerpt is long enough for validation.",
                "locator": "Item 1",
                "unexpected": True,
            },
        ),
    ],
)
def test_agent_value_schemas_reject_extra_fields(schema, payload: dict) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_refresh_request_rejects_coerced_boolean() -> None:
    with pytest.raises(ValidationError):
        GraphRefreshRequest.model_validate({"force_refresh": "false"})


def test_evidence_reference_is_immutable() -> None:
    evidence = EvidenceReference(
        source_key="source:apple-10k",
        excerpt="This evidence excerpt is long enough for validation.",
        locator="Item 1",
    )

    with pytest.raises(ValidationError):
        evidence.confidence = 0.5


def test_official_source_metadata_is_immutable(source_payload: dict) -> None:
    payload = source_payload["documents"][0]
    source = OfficialSourceMetadata.model_validate(
        {key: payload[key] for key in OfficialSourceMetadata.model_fields}
    )

    with pytest.raises(ValidationError):
        source.title = "Changed"


@pytest.mark.parametrize(
    ("schema", "payload", "field"),
    [
        (
            OfficialSourceDocument,
            {
                "source_id": "source-id",
                "source_key": "source:key",
                "source_type": "sec_filing",
                "publisher": "Apple Inc.",
                "title": "Fixture filing",
                "canonical_url": "https://www.apple.com/fixture",
                "content_hash": "a" * 64,
                "artifact_key": "fixtures/source.txt",
                "content_type": "text/plain",
                "body_text": " " * 20,
            },
            "body_text",
        ),
        (
            EvidenceReference,
            {
                "source_key": "source:key",
                "excerpt": " " * 20,
                "locator": "Item 1",
            },
            "excerpt",
        ),
        (
            PublicGraphCitation,
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "source_id": "00000000-0000-0000-0000-000000000002",
                "source_key": "source:key",
                "excerpt": " " * 20,
                "locator": "Item 1",
                "support_role": "primary",
                "confidence": 1.0,
            },
            "excerpt",
        ),
    ],
)
def test_evidence_text_rejects_whitespace_only(
    schema, payload: dict, field: str
) -> None:
    with pytest.raises(ValidationError, match=field):
        schema.model_validate(payload)


@pytest.mark.parametrize(
    ("schema", "payload", "field", "exact_text"),
    [
        (
            OfficialSourceDocument,
            {
                "source_id": "source-id",
                "source_key": "source:key",
                "source_type": "sec_filing",
                "publisher": "Apple Inc.",
                "title": "Fixture filing",
                "canonical_url": "https://www.apple.com/fixture",
                "content_hash": "a" * 64,
                "artifact_key": "fixtures/source.txt",
                "content_type": "text/plain",
                "body_text": "  FIXTURE DATA body stays exact.  \n",
            },
            "body_text",
            "  FIXTURE DATA body stays exact.  \n",
        ),
        (
            EvidenceReference,
            {
                "source_key": "source:key",
                "excerpt": "  Evidence excerpt stays exact.  ",
                "locator": "Item 1",
            },
            "excerpt",
            "  Evidence excerpt stays exact.  ",
        ),
        (
            PublicGraphCitation,
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "source_id": "00000000-0000-0000-0000-000000000002",
                "source_key": "source:key",
                "excerpt": "  Public excerpt stays exact.  ",
                "locator": "Item 1",
                "support_role": "primary",
                "confidence": 1.0,
            },
            "excerpt",
            "  Public excerpt stays exact.  ",
        ),
    ],
)
def test_evidence_text_preserves_valid_exact_string(
    schema,
    payload: dict,
    field: str,
    exact_text: str,
) -> None:
    assert getattr(schema.model_validate(payload), field) == exact_text


@pytest.mark.parametrize(
    "protocol",
    [
        GraphArtifactStore,
        OfficialSourceTools,
        OfficialSourceCollector,
        SupplyChainAgent,
        EntityResolver,
        SupplyChainGraphRepository,
        GraphQuotaLedger,
    ],
)
def test_dependency_contracts_are_runtime_independent_protocols(protocol) -> None:
    assert getattr(protocol, "_is_protocol", False)


def test_agent_contract_exposes_exact_stage_methods() -> None:
    methods = {
        name
        for name, value in inspect.getmembers(SupplyChainAgent, inspect.isfunction)
        if not name.startswith("_")
    }

    assert methods == {
        "plan_sources",
        "extract_graph",
        "verify_graph",
        "localize_graph",
    }


@pytest.mark.parametrize(
    ("method_name", "parameter_names", "expected_hints"),
    [
        (
            "plan_sources",
            ["company", "tools"],
            {
                "company": CompanyIdentity,
                "tools": OfficialSourceTools,
                "return": SourcePlan,
            },
        ),
        (
            "extract_graph",
            ["company", "sources"],
            {
                "company": CompanyIdentity,
                "sources": list[OfficialSourceDocument],
                "return": GraphDraft,
            },
        ),
        (
            "verify_graph",
            ["draft", "sources"],
            {
                "draft": GraphDraft,
                "sources": list[OfficialSourceDocument],
                "return": GraphVerification,
            },
        ),
        (
            "localize_graph",
            ["graph", "locale"],
            {
                "graph": AcceptedGraph,
                "locale": Literal["zh"],
                "return": GraphLocalization,
            },
        ),
    ],
)
def test_agent_stage_signatures_are_exact_and_keyword_only(
    method_name: str,
    parameter_names: list[str],
    expected_hints: dict,
) -> None:
    method = getattr(SupplyChainAgent, method_name)
    signature = inspect.signature(method)
    parameters = list(signature.parameters.values())

    assert parameters[0].name == "self"
    assert [parameter.name for parameter in parameters[1:]] == parameter_names
    assert all(parameter.kind is Parameter.KEYWORD_ONLY for parameter in parameters[1:])
    assert get_type_hints(method) == expected_hints
    if method_name == "localize_graph":
        assert signature.parameters["locale"].default == "zh"
