from copy import deepcopy

import pytest

from app.supply_chain.entity_resolver import (
    CompanyDirectoryEntry,
    DeterministicEntityResolver,
    non_company_node_key,
)
from app.supply_chain.schemas import EntityCandidate, GraphDraft


@pytest.fixture
def directory() -> tuple[CompanyDirectoryEntry, ...]:
    return (
        CompanyDirectoryEntry(
            company_id=1,
            symbol="AAPL",
            cik="0000320193",
            legal_name="Apple Inc.",
            aliases=("Apple",),
        ),
        CompanyDirectoryEntry(
            company_id=2,
            symbol="TSM",
            cik="0001046179",
            legal_name="Taiwan Semiconductor Manufacturing Company Limited",
            aliases=("TSMC", "Taiwan Semiconductor Manufacturing Company"),
        ),
    )


@pytest.fixture
def resolver(
    directory: tuple[CompanyDirectoryEntry, ...],
) -> DeterministicEntityResolver:
    return DeterministicEntityResolver(directory)


@pytest.mark.anyio
async def test_cik_is_the_primary_company_identity(
    resolver: DeterministicEntityResolver,
) -> None:
    resolved = await resolver.resolve(
        EntityCandidate(
            node_key="company:model-apple",
            kind="company",
            label_en="A conflicting model label",
            symbol="TSM",
            cik="0000320193",
        )
    )

    assert resolved.node_key == "company:0000320193"
    assert resolved.company_id == 1
    assert resolved.symbol == "AAPL"
    assert resolved.resolution_status == "resolved"
    assert resolved.resolution_basis == "cik"
    assert resolved.confidence == 1.0


@pytest.mark.anyio
async def test_exact_ticker_resolves_a_company(
    resolver: DeterministicEntityResolver,
) -> None:
    resolved = await resolver.resolve(
        EntityCandidate(
            node_key="company:model-ticker",
            kind="company",
            label_en="Foundry partner",
            symbol="TSM",
        )
    )

    assert resolved.node_key == "company:0001046179"
    assert resolved.resolution_basis == "ticker"
    assert resolved.confidence == 0.98


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("label", "basis"),
    [
        ("TSMC", "legal_name"),
        ("Taiwan  Semiconductor Manufacturing Company", "legal_name"),
    ],
)
async def test_directory_aliases_converge_to_the_same_company_key(
    resolver: DeterministicEntityResolver,
    label: str,
    basis: str,
) -> None:
    resolved = await resolver.resolve(
        EntityCandidate(
            node_key=f"company:model-{label.casefold().replace(' ', '-')}",
            kind="company",
            label_en=label,
        )
    )

    assert resolved.node_key == "company:0001046179"
    assert resolved.cik == "0001046179"
    assert resolved.resolution_basis == basis


@pytest.mark.anyio
async def test_ambiguous_company_name_stays_unresolved() -> None:
    resolver = DeterministicEntityResolver(
        (
            CompanyDirectoryEntry(
                company_id=10,
                symbol="GFA",
                cik="0000000010",
                legal_name="Global Foundry Alpha",
                aliases=("Global Foundry",),
            ),
            CompanyDirectoryEntry(
                company_id=11,
                symbol="GFB",
                cik="0000000011",
                legal_name="Global Foundry Beta",
                aliases=("Global Foundry",),
            ),
        )
    )

    resolved = await resolver.resolve(
        EntityCandidate(
            node_key="company:model-global-foundry",
            kind="company",
            label_en="Global Foundry",
        )
    )

    assert resolved.node_key.startswith("company:unresolved:")
    assert resolved.company_id is None
    assert resolved.resolution_status == "ambiguous"
    assert resolved.resolution_basis == "ambiguous_name"
    assert resolved.confidence < 0.8


@pytest.mark.anyio
async def test_non_company_keys_are_deterministic_and_kind_scoped(
    resolver: DeterministicEntityResolver,
) -> None:
    product = await resolver.resolve(
        EntityCandidate(
            node_key="model:one",
            kind="product",
            label_en="  Apple Vision Pro  ",
        )
    )
    same_product = await resolver.resolve(
        EntityCandidate(
            node_key="model:two",
            kind="product",
            label_en="Apple Vision Pro",
        )
    )
    business = await resolver.resolve(
        EntityCandidate(
            node_key="model:three",
            kind="business",
            label_en="Apple Vision Pro",
        )
    )

    assert product.node_key == same_product.node_key
    assert product.node_key == non_company_node_key("product", "Apple Vision Pro")
    assert business.node_key != product.node_key
    assert product.resolution_basis == "deterministic_key"


@pytest.mark.anyio
async def test_unknown_company_receives_a_stable_low_confidence_key(
    resolver: DeterministicEntityResolver,
) -> None:
    first = await resolver.resolve(
        EntityCandidate(
            node_key="company:model-one",
            kind="company",
            label_en="Unknown Example Corporation",
        )
    )
    second = await resolver.resolve(
        EntityCandidate(
            node_key="company:model-two",
            kind="company",
            label_en="Unknown  Example Corporation",
        )
    )

    assert first.node_key == second.node_key
    assert first.resolution_status == "unresolved"
    assert first.resolution_basis == "unresolved_hash"
    assert first.confidence < 0.8


@pytest.mark.anyio
async def test_unknown_companies_with_distinct_tickers_keep_distinct_keys(
    resolver: DeterministicEntityResolver,
) -> None:
    first = await resolver.resolve(
        EntityCandidate(
            node_key="company:model-first",
            kind="company",
            label_en="Emerging Technology Holdings",
            symbol="ETA",
        )
    )
    second = await resolver.resolve(
        EntityCandidate(
            node_key="company:model-second",
            kind="company",
            label_en="Emerging Technology Holdings",
            symbol="ETB",
        )
    )

    assert first.node_key != second.node_key


@pytest.mark.anyio
async def test_equivalent_directory_alias_does_not_create_false_ambiguity() -> None:
    resolver = DeterministicEntityResolver(
        (
            CompanyDirectoryEntry(
                company_id=20,
                symbol="ACME",
                cik="0000000020",
                legal_name="Acme, Inc.",
                aliases=("Acme Inc",),
            ),
        )
    )

    resolved = await resolver.resolve(
        EntityCandidate(
            node_key="company:model-acme",
            kind="company",
            label_en="Acme Inc",
        )
    )

    assert resolved.node_key == "company:0000000020"
    assert resolved.resolution_status == "resolved"


@pytest.mark.anyio
async def test_unresolved_company_confidence_is_capped_in_the_draft(
    resolver: DeterministicEntityResolver,
) -> None:
    payload = _same_label_different_kind_draft()
    payload["nodes"] = [payload["nodes"][0]]
    payload["nodes"][0].update(
        {
            "symbol": None,
            "label_en": "Unknown Example Corporation",
            "confidence": 0.99,
        }
    )

    resolved = await resolver.resolve_draft(GraphDraft.model_validate(payload))

    assert resolved.nodes[0].resolution_status == "unresolved"
    assert resolved.nodes[0].confidence == 0.5


@pytest.mark.anyio
async def test_unresolved_draft_resolution_is_idempotent(
    resolver: DeterministicEntityResolver,
) -> None:
    payload = _same_label_different_kind_draft()
    payload["nodes"] = [payload["nodes"][0]]
    payload["nodes"][0].update(
        {
            "symbol": "ETA",
            "label_en": "Emerging Technology Holdings",
            "confidence": 0.99,
        }
    )

    first = await resolver.resolve_draft(GraphDraft.model_validate(payload))
    second = await resolver.resolve_draft(first)

    assert second.model_dump() == first.model_dump()


@pytest.mark.anyio
async def test_resolve_draft_merges_nodes_redirects_edges_and_preserves_audit(
    resolver: DeterministicEntityResolver,
) -> None:
    draft = GraphDraft.model_validate(_duplicate_company_draft())

    resolved = await resolver.resolve_draft(draft)

    assert resolved.focus_node_key == "company:0000320193"
    assert len(resolved.nodes) == 2
    tsmc = next(node for node in resolved.nodes if node.symbol == "TSM")
    assert tsmc.node_key == "company:0001046179"
    assert tsmc.importance == 0.9
    assert tsmc.confidence == 0.95
    assert tsmc.resolution_basis == "cik"
    assert tsmc.aliases == [
        "TSMC",
        "Taiwan Semiconductor Manufacturing Company",
    ]

    assert len(resolved.edges) == 1
    edge = resolved.edges[0]
    assert edge.source_node_key == "company:0001046179"
    assert edge.target_node_key == "company:0000320193"
    assert edge.confidence == 0.94
    assert edge.importance == 0.92
    assert len(edge.evidence_refs) == 2


@pytest.mark.anyio
async def test_resolve_draft_caps_merged_evidence_at_schema_limit(
    resolver: DeterministicEntityResolver,
) -> None:
    payload = _duplicate_company_draft()
    for edge_index, edge in enumerate(payload["edges"]):
        edge["evidence_refs"] = [
            {
                "source_key": f"fixture:source:{edge_index}:{index}",
                "excerpt": (
                    "FIXTURE DATA: deterministic evidence reference "
                    f"{edge_index}-{index} supports the relationship."
                ),
                "locator": f"Section {edge_index}-{index}",
                "confidence": (index + 1) / 20,
            }
            for index in range(12)
        ]

    resolved = await resolver.resolve_draft(GraphDraft.model_validate(payload))

    assert len(resolved.edges[0].evidence_refs) == 12
    assert {reference.confidence for reference in resolved.edges[0].evidence_refs} == {
        value / 20 for value in range(7, 13)
    }


@pytest.mark.anyio
async def test_resolve_draft_caps_discarded_aliases_at_schema_limit(
    resolver: DeterministicEntityResolver,
) -> None:
    payload = _same_label_different_kind_draft()
    payload["nodes"] = [
        {
            **payload["nodes"][0],
            "node_key": f"company:model-apple-{index}",
            "label_en": f"Apple Alias {index:02d}",
            "cik": "0000320193",
        }
        for index in range(25)
    ]
    payload["focus_node_key"] = "company:model-apple-0"

    resolved = await resolver.resolve_draft(GraphDraft.model_validate(payload))

    assert len(resolved.nodes) == 1
    assert len(resolved.nodes[0].aliases) == 24


@pytest.mark.anyio
async def test_resolve_draft_is_deterministic_and_keeps_kinds_distinct(
    resolver: DeterministicEntityResolver,
) -> None:
    payload = _same_label_different_kind_draft()
    forward = await resolver.resolve_draft(GraphDraft.model_validate(payload))
    reverse_payload = deepcopy(payload)
    reverse_payload["nodes"].reverse()
    reverse = await resolver.resolve_draft(GraphDraft.model_validate(reverse_payload))

    assert forward.model_dump() == reverse.model_dump()
    keys = {
        node.node_key for node in forward.nodes if node.label_en == "Cloud Services"
    }
    assert len(keys) == 2
    assert {node.kind for node in forward.nodes if node.node_key in keys} == {
        "business",
        "product",
    }


def _duplicate_company_draft() -> dict:
    evidence_one = {
        "source_key": "sec:aapl:10-k:one",
        "excerpt": "FIXTURE DATA: TSMC supplies advanced chips to Apple products.",
        "locator": "Item 1, suppliers",
        "confidence": 0.9,
    }
    evidence_two = {
        "source_key": "issuer:tsmc:report:two",
        "excerpt": "FIXTURE DATA: Apple is a customer for advanced foundry services.",
        "locator": "Customer concentration",
        "confidence": 0.88,
    }
    return {
        "focus_node_key": "company:model-apple",
        "thesis_en": "A deterministic fixture graph for entity resolution.",
        "nodes": [
            {
                "node_key": "company:model-apple",
                "kind": "company",
                "layer": "core",
                "label_en": "Apple",
                "description_en": "The focus company in this deterministic fixture.",
                "symbol": "AAPL",
                "importance": 1.0,
                "confidence": 0.99,
                "rank": 1,
            },
            {
                "node_key": "company:model-tsmc",
                "kind": "company",
                "layer": "upstream",
                "label_en": "TSMC",
                "description_en": "An upstream semiconductor foundry alias.",
                "symbol": "TSM",
                "importance": 0.8,
                "confidence": 0.9,
                "rank": 3,
            },
            {
                "node_key": "company:model-taiwan-semiconductor",
                "kind": "company",
                "layer": "upstream",
                "label_en": "Taiwan Semiconductor Manufacturing Company",
                "description_en": "The resolved upstream semiconductor foundry.",
                "cik": "0001046179",
                "importance": 0.9,
                "confidence": 0.95,
                "rank": 2,
            },
        ],
        "edges": [
            {
                "edge_key": "edge:model-tsmc-apple",
                "source_node_key": "company:model-tsmc",
                "target_node_key": "company:model-apple",
                "relationship_type": "supplies",
                "evidence_status": "verified",
                "confidence": 0.9,
                "importance": 0.86,
                "explanation_en": "TSMC supplies semiconductor components to Apple.",
                "evidence_refs": [evidence_one],
            },
            {
                "edge_key": "edge:model-taiwan-apple",
                "source_node_key": "company:model-taiwan-semiconductor",
                "target_node_key": "company:model-apple",
                "relationship_type": "supplies",
                "evidence_status": "verified",
                "confidence": 0.94,
                "importance": 0.92,
                "explanation_en": (
                    "The foundry relationship is supported by issuer evidence."
                ),
                "evidence_refs": [evidence_two],
            },
        ],
    }


def _same_label_different_kind_draft() -> dict:
    return {
        "focus_node_key": "company:model-apple",
        "thesis_en": "A deterministic fixture graph with kind-scoped labels.",
        "nodes": [
            {
                "node_key": "company:model-apple",
                "kind": "company",
                "layer": "core",
                "label_en": "Apple",
                "description_en": "The focus company for this deterministic fixture.",
                "symbol": "AAPL",
                "importance": 1.0,
                "confidence": 0.99,
            },
            {
                "node_key": "model:cloud-business",
                "kind": "business",
                "layer": "core",
                "label_en": "Cloud Services",
                "description_en": "A business segment in the deterministic fixture.",
                "importance": 0.7,
                "confidence": 0.8,
            },
            {
                "node_key": "model:cloud-product",
                "kind": "product",
                "layer": "core",
                "label_en": "Cloud Services",
                "description_en": "A product category in the deterministic fixture.",
                "importance": 0.6,
                "confidence": 0.7,
            },
        ],
        "edges": [],
    }
