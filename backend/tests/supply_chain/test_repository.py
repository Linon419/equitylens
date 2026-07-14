from datetime import UTC, datetime

import pytest
from sqlmodel import Session, func, select

from app.models.company_model import Company
from app.models.supply_chain_model import (
    GraphEdgeCitation,
    GraphOfficialSource,
    SupplyChainGraphEdge,
    SupplyChainGraphNode,
    SupplyChainGraphSnapshot,
)
from app.supply_chain.repository import (
    CreateWorkingSnapshotCommand,
    GraphPublicationError,
    GraphVersionConflict,
    GraphVersionKey,
    PublishGraphCommand,
    SqlSupplyChainGraphRepository,
)
from app.supply_chain.schemas import (
    AcceptedGraph,
    GraphLocalization,
    OfficialSourceDocument,
)

NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)


def working_command(
    company: Company,
    sources: list[OfficialSourceDocument],
    *,
    fingerprint: str = "a" * 64,
) -> CreateWorkingSnapshotCommand:
    assert company.id is not None
    return CreateWorkingSnapshotCommand(
        company_id=company.id,
        sources=sources,
        source_fingerprint=fingerprint,
        schema_version="supply-chain-graph.v1",
        prompt_version="supply-chain-graph.2026-07-14",
        model_id="gpt-5-mini",
        now=NOW,
    )


def publish_command(
    snapshot_id,
    graph: AcceptedGraph,
    localization: GraphLocalization,
) -> PublishGraphCommand:
    return PublishGraphCommand(
        snapshot_id=snapshot_id,
        graph=graph,
        localization=localization,
        now=NOW,
    )


def test_working_snapshot_persists_sources_and_resumable_stages(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
) -> None:
    repository = SqlSupplyChainGraphRepository(session)
    working = repository.create_working_snapshot(
        working_command(company, source_documents)
    )
    repository.save_stage(
        working.id,
        stage="extracted",
        payload=accepted_graph,
    )

    assert working.status == "drafted"
    assert repository.load_stage(working.id, stage="extracted") == (
        accepted_graph.model_dump(mode="json")
    )
    assert repository.latest_public(company.id) is None
    assert session.exec(select(func.count(GraphOfficialSource.id))).one() == 4


def test_publish_writes_normalized_graph_and_citations_atomically(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> None:
    repository = SqlSupplyChainGraphRepository(session)
    working = repository.create_working_snapshot(
        working_command(company, source_documents)
    )

    snapshot = repository.publish(
        publish_command(working.id, accepted_graph, graph_localization)
    )
    persisted = repository.load_public(snapshot.id)

    assert snapshot.status == "completed"
    assert snapshot.node_count == len(accepted_graph.accepted_nodes)
    assert snapshot.edge_count == (
        len(accepted_graph.public_edges) + len(accepted_graph.potential_edges)
    )
    assert len(persisted.nodes) == snapshot.node_count
    assert len(persisted.edges) == snapshot.edge_count
    assert persisted.citations
    node_ids = {node.id for node in persisted.nodes}
    assert all(
        {edge.source_node_id, edge.target_node_id} <= node_ids
        for edge in persisted.edges
    )
    assert snapshot.content_en["internal_edges"]
    assert snapshot.content_en["rejected_edges"]
    assert snapshot.content_zh["internal_edges"]


def test_failed_publication_keeps_previous_snapshot_readable(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> None:
    repository = SqlSupplyChainGraphRepository(session)
    previous = repository.create_working_snapshot(
        working_command(company, source_documents)
    )
    repository.publish(publish_command(previous.id, accepted_graph, graph_localization))
    working = repository.create_working_snapshot(
        working_command(company, source_documents, fingerprint="b" * 64)
    )
    graph_payload = accepted_graph.model_dump()
    graph_payload["accepted_nodes"][0]["company_id"] = 999
    invalid_graph = AcceptedGraph.model_validate(graph_payload)
    localization_payload = graph_localization.model_dump()
    localization_payload["nodes"][0]["company_id"] = 999
    invalid_localization = GraphLocalization.model_validate(localization_payload)

    with pytest.raises(GraphPublicationError):
        repository.publish(
            publish_command(working.id, invalid_graph, invalid_localization)
        )

    latest = repository.latest_public(company.id)
    assert latest is not None
    assert latest.id == previous.id
    assert session.get(SupplyChainGraphSnapshot, working.id).status == "drafted"
    assert (
        session.exec(
            select(func.count(SupplyChainGraphNode.id)).where(
                SupplyChainGraphNode.snapshot_id == working.id
            )
        ).one()
        == 0
    )


def test_version_key_is_unique_and_queryable(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
) -> None:
    repository = SqlSupplyChainGraphRepository(session)
    command = working_command(company, source_documents)
    working = repository.create_working_snapshot(command)
    key = GraphVersionKey(
        company_id=command.company_id,
        source_fingerprint=command.source_fingerprint,
        schema_version=command.schema_version,
        prompt_version=command.prompt_version,
        model_id=command.model_id,
    )

    assert repository.find_by_version_key(key).id == working.id
    with pytest.raises(GraphVersionConflict):
        repository.create_working_snapshot(command)


def test_source_content_hashes_are_deduplicated_with_all_keys_indexed(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> None:
    duplicate = source_documents[0].model_copy(
        update={
            "source_id": "apple-2025-10k-copy",
            "source_key": "source:apple-2025-10k-copy",
        }
    )
    repository = SqlSupplyChainGraphRepository(session)

    working = repository.create_working_snapshot(
        working_command(company, [*source_documents, duplicate])
    )

    rows = session.exec(
        select(GraphOfficialSource).where(GraphOfficialSource.snapshot_id == working.id)
    ).all()
    index = working.content_en["source_index"]
    assert len(rows) == len(source_documents)
    assert len(index) == len(source_documents) + 1
    assert len({item["database_id"] for item in index}) == len(source_documents)

    snapshot = repository.publish(
        publish_command(working.id, accepted_graph, graph_localization)
    )
    persisted = repository.load_public(snapshot.id)
    assert {citation.source_id for citation in persisted.citations} <= {
        source.id for source in persisted.sources
    }


def test_missing_source_mapping_rolls_back_all_normalized_rows(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> None:
    repository = SqlSupplyChainGraphRepository(session)
    working = repository.create_working_snapshot(
        working_command(company, source_documents[:1])
    )

    with pytest.raises(GraphPublicationError) as error:
        repository.publish(
            publish_command(working.id, accepted_graph, graph_localization)
        )

    assert error.value.code == "GRAPH_SOURCE_MAPPING_MISSING"
    assert session.get(SupplyChainGraphSnapshot, working.id).status == "drafted"
    assert (
        session.exec(
            select(func.count(SupplyChainGraphNode.id)).where(
                SupplyChainGraphNode.snapshot_id == working.id
            )
        ).one()
        == 0
    )


def test_terminal_snapshot_is_immutable(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> None:
    repository = SqlSupplyChainGraphRepository(session)
    working = repository.create_working_snapshot(
        working_command(company, source_documents)
    )
    repository.publish(publish_command(working.id, accepted_graph, graph_localization))

    with pytest.raises(GraphPublicationError):
        repository.save_stage(working.id, stage="verified", payload=accepted_graph)
    with pytest.raises(GraphPublicationError):
        repository.publish(
            publish_command(working.id, accepted_graph, graph_localization)
        )

    assert (
        session.exec(
            select(func.count(SupplyChainGraphEdge.id)).where(
                SupplyChainGraphEdge.snapshot_id == working.id
            )
        ).one()
        == working.edge_count
    )
    assert (
        session.exec(
            select(func.count(GraphEdgeCitation.id)).where(
                GraphEdgeCitation.snapshot_id == working.id
            )
        ).one()
        > 0
    )


def test_insufficient_evidence_snapshot_is_public_terminal_state(
    session: Session,
    company: Company,
    source_documents: list[OfficialSourceDocument],
    accepted_graph: AcceptedGraph,
    graph_localization: GraphLocalization,
) -> None:
    repository = SqlSupplyChainGraphRepository(session)
    working = repository.create_working_snapshot(
        working_command(company, source_documents)
    )
    graph = accepted_graph.model_copy(update={"status": "insufficient_evidence"})

    snapshot = repository.publish(
        publish_command(working.id, graph, graph_localization)
    )

    assert snapshot.status == "insufficient_evidence"
    assert repository.latest_public(company.id).id == snapshot.id
