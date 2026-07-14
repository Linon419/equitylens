import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.models.company_model import Company
from app.supply_chain.schemas import (
    AcceptedGraph,
    GraphDraft,
    GraphLocalization,
    GraphVerification,
    OfficialSourceDocument,
    SourcePlan,
)
from app.supply_chain.validator import validate_for_publication

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "supply_chain"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_foreign_keys)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as current:
        yield current


@pytest.fixture
def company(session: Session) -> Company:
    row = Company(
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        exchange="Nasdaq",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    assert row.id == 1
    return row


@pytest.fixture
def source_documents() -> list[OfficialSourceDocument]:
    return [
        OfficialSourceDocument.model_validate(item)
        for item in load_fixture("aapl_sources.json")["documents"]
    ]


@pytest.fixture
def graph_draft() -> GraphDraft:
    return GraphDraft.model_validate(load_fixture("aapl_draft.json"))


@pytest.fixture
def graph_verification() -> GraphVerification:
    return GraphVerification.model_validate(load_fixture("aapl_verification.json"))


@pytest.fixture
def source_plan() -> SourcePlan:
    return SourcePlan.model_validate(load_fixture("aapl_sources.json")["source_plan"])


@pytest.fixture
def accepted_graph(
    source_documents: list[OfficialSourceDocument],
    graph_draft: GraphDraft,
    graph_verification: GraphVerification,
) -> AcceptedGraph:
    return validate_for_publication(
        draft=graph_draft,
        verification=graph_verification,
        sources=source_documents,
        min_nodes=25,
        max_nodes=40,
        evidence_threshold=0.75,
    )


@pytest.fixture
def graph_localization(accepted_graph: AcceptedGraph) -> GraphLocalization:
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

    return GraphLocalization.model_validate(
        {
            "locale": "zh",
            "focus_node_key": accepted_graph.focus_node_key,
            "thesis_zh": f"中文 {accepted_graph.thesis_en}",
            "nodes": [node_payload(node) for node in accepted_graph.accepted_nodes],
            "public_edges": [
                edge_payload(edge) for edge in accepted_graph.public_edges
            ],
            "potential_edges": [
                edge_payload(edge) for edge in accepted_graph.potential_edges
            ],
            "internal_edges": [
                edge_payload(edge) for edge in accepted_graph.internal_edges
            ],
        }
    )
