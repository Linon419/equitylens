from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.supply_chain_model import (
    AgentQuotaReservation,
    GraphEdgeCitation,
    GraphOfficialSource,
    SupplyChainGraphEdge,
    SupplyChainGraphNode,
    SupplyChainGraphSnapshot,
)

NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)


def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def build_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def constraint_names(model: type[SQLModel], kind: type) -> set[str | None]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, kind)
    }


def foreign_key(
    model: type[SQLModel],
    column_name: str,
    target: str,
):
    column = model.__table__.columns[column_name]
    return next(
        reference
        for reference in column.foreign_keys
        if reference.target_fullname == target
    )


def composite_foreign_keys(
    model: type[SQLModel],
) -> dict[str | None, tuple[tuple[str, ...], tuple[str, ...]]]:
    return {
        constraint.name: (
            tuple(column.name for column in constraint.columns),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in model.__table__.constraints
        if isinstance(constraint, ForeignKeyConstraint) and len(constraint.elements) > 1
    }


def add_company_and_snapshots(
    session: Session,
) -> tuple[SupplyChainGraphSnapshot, SupplyChainGraphSnapshot]:
    company = Company(symbol="AAPL", cik="0000320193", name="Apple Inc.")
    session.add(company)
    session.commit()
    session.refresh(company)
    assert company.id is not None

    snapshots = (
        SupplyChainGraphSnapshot(
            company_id=company.id,
            status="drafted",
            schema_version="supply-chain-graph.v1",
            prompt_version="supply-chain-graph.2026-07-14",
            model_id="gpt-5-mini",
            source_fingerprint="a" * 64,
        ),
        SupplyChainGraphSnapshot(
            company_id=company.id,
            status="drafted",
            schema_version="supply-chain-graph.v1",
            prompt_version="supply-chain-graph.2026-07-14",
            model_id="gpt-5-mini",
            source_fingerprint="b" * 64,
        ),
    )
    session.add_all(snapshots)
    session.commit()
    for snapshot in snapshots:
        session.refresh(snapshot)
    return snapshots


def graph_node(snapshot_id: UUID, node_key: str) -> SupplyChainGraphNode:
    return SupplyChainGraphNode(
        snapshot_id=snapshot_id,
        node_key=node_key,
        kind="company",
        layer="core",
        label_en=node_key,
        label_zh=node_key,
        description_en="Graph node.",
        description_zh="图节点。",
        importance=Decimal("1.0000"),
        confidence="High",
    )


def graph_edge(
    snapshot_id: UUID,
    source_node_id: UUID,
    target_node_id: UUID,
) -> SupplyChainGraphEdge:
    return SupplyChainGraphEdge(
        snapshot_id=snapshot_id,
        edge_key=f"{source_node_id}|supplies|{target_node_id}",
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relationship_type="supplies",
        evidence_status="verified",
        confidence="High",
        explanation_en="Supplier relationship.",
        explanation_zh="供应关系。",
    )


def graph_source(snapshot_id: UUID, content_hash: str) -> GraphOfficialSource:
    return GraphOfficialSource(
        snapshot_id=snapshot_id,
        source_type="sec_filing",
        publisher="Apple Inc.",
        title="Form 10-K",
        canonical_url="https://www.sec.gov/example",
        content_hash=content_hash,
        artifact_key="supply-chain/apple/source.html",
    )


def test_graph_snapshot_has_versioned_publication_metadata() -> None:
    snapshot = SupplyChainGraphSnapshot(
        company_id=1,
        status="drafted",
        schema_version="supply-chain-graph.v1",
        prompt_version="supply-chain-graph.2026-07-14",
        model_id="gpt-5-mini",
        source_fingerprint="a" * 64,
    )

    assert snapshot.status == "drafted"
    assert snapshot.node_count == 0
    assert snapshot.edge_count == 0
    assert snapshot.evidence_coverage == "insufficient_evidence"
    assert snapshot.content_en == {}
    assert snapshot.content_zh == {}
    assert snapshot.content_en is not snapshot.content_zh
    assert snapshot.generated_at.tzinfo is UTC


def test_graph_edge_identity_is_stable() -> None:
    edge = SupplyChainGraphEdge(
        snapshot_id=uuid4(),
        edge_key="company:0001046179|supplies|company:0000320193",
        source_node_id=uuid4(),
        target_node_id=uuid4(),
        relationship_type="supplies",
        evidence_status="verified",
        confidence="High",
        explanation_en="Broadcom supplies components to Apple.",
        explanation_zh="博通向苹果供应元件。",
    )

    assert isinstance(edge.id, UUID)
    assert "|supplies|" in edge.edge_key


def test_graph_models_have_uuid_identities_and_expected_tables() -> None:
    identities = {
        SupplyChainGraphSnapshot(
            company_id=1,
            status="drafted",
            schema_version="supply-chain-graph.v1",
            prompt_version="supply-chain-graph.2026-07-14",
            model_id="gpt-5-mini",
            source_fingerprint="a" * 64,
        ).id,
        SupplyChainGraphNode(
            snapshot_id=uuid4(),
            node_key="company:0000320193",
            kind="company",
            layer="core",
            label_en="Apple",
            label_zh="苹果",
            description_en="Consumer technology company.",
            description_zh="消费科技公司。",
            importance=Decimal("1.0000"),
            confidence="High",
        ).id,
        SupplyChainGraphEdge(
            snapshot_id=uuid4(),
            edge_key="supplier|supplies|apple",
            source_node_id=uuid4(),
            target_node_id=uuid4(),
            relationship_type="supplies",
            evidence_status="verified",
            confidence="High",
            explanation_en="Supplier relationship.",
            explanation_zh="供应关系。",
        ).id,
        GraphOfficialSource(
            snapshot_id=uuid4(),
            source_type="sec_filing",
            publisher="Apple Inc.",
            title="Form 10-K",
            canonical_url="https://www.sec.gov/example",
            content_hash="b" * 64,
            artifact_key="supply-chain/apple/source.html",
        ).id,
        GraphEdgeCitation(
            snapshot_id=uuid4(),
            edge_id=uuid4(),
            source_id=uuid4(),
            excerpt="Supplier concentration disclosure.",
            source_anchor="item-1-business",
            support_role="primary",
        ).id,
        AgentQuotaReservation(
            job_id=uuid4(),
            principal_type="guest",
            principal_hash="c" * 64,
            usage_date=date(2026, 7, 14),
            principal_daily_limit=2,
            ip_daily_limit=10,
            state="reserved",
        ).id,
    }

    assert all(isinstance(identity, UUID) for identity in identities)
    assert {
        SupplyChainGraphSnapshot.__tablename__,
        SupplyChainGraphNode.__tablename__,
        SupplyChainGraphEdge.__tablename__,
        GraphOfficialSource.__tablename__,
        GraphEdgeCitation.__tablename__,
        AgentQuotaReservation.__tablename__,
    } == {
        "supply_chain_graph_snapshot",
        "supply_chain_graph_node",
        "supply_chain_graph_edge",
        "graph_official_source",
        "graph_edge_citation",
        "agent_quota_reservation",
    }


def test_graph_unique_constraints_are_named() -> None:
    assert "uq_supply_chain_graph_snapshot_version" in constraint_names(
        SupplyChainGraphSnapshot,
        UniqueConstraint,
    )
    assert "uq_supply_chain_graph_node_key" in constraint_names(
        SupplyChainGraphNode,
        UniqueConstraint,
    )
    assert "uq_supply_chain_graph_node_snapshot_identity" in constraint_names(
        SupplyChainGraphNode,
        UniqueConstraint,
    )
    assert "uq_supply_chain_graph_edge_key" in constraint_names(
        SupplyChainGraphEdge,
        UniqueConstraint,
    )
    assert "uq_supply_chain_graph_edge_snapshot_identity" in constraint_names(
        SupplyChainGraphEdge,
        UniqueConstraint,
    )
    assert "uq_graph_official_source_hash" in constraint_names(
        GraphOfficialSource,
        UniqueConstraint,
    )
    assert "uq_graph_official_source_snapshot_identity" in constraint_names(
        GraphOfficialSource,
        UniqueConstraint,
    )
    assert "uq_graph_edge_citation_anchor" in constraint_names(
        GraphEdgeCitation,
        UniqueConstraint,
    )
    assert "uq_agent_quota_reservation_job_id" in constraint_names(
        AgentQuotaReservation,
        UniqueConstraint,
    )


def test_graph_check_constraints_cover_closed_sets_and_numeric_bounds() -> None:
    expectations = {
        SupplyChainGraphSnapshot: {
            "ck_supply_chain_graph_snapshot_status",
            "ck_supply_chain_graph_snapshot_evidence_coverage",
            "ck_supply_chain_graph_snapshot_confidence",
            "ck_supply_chain_graph_snapshot_node_count",
            "ck_supply_chain_graph_snapshot_edge_count",
        },
        SupplyChainGraphNode: {
            "ck_supply_chain_graph_node_kind",
            "ck_supply_chain_graph_node_layer",
            "ck_supply_chain_graph_node_importance",
            "ck_supply_chain_graph_node_confidence",
            "ck_supply_chain_graph_node_rank",
        },
        SupplyChainGraphEdge: {
            "ck_supply_chain_graph_edge_relationship_type",
            "ck_supply_chain_graph_edge_evidence_status",
            "ck_supply_chain_graph_edge_confidence",
            "ck_supply_chain_graph_edge_distinct_nodes",
        },
        GraphOfficialSource: {"ck_graph_official_source_type"},
        GraphEdgeCitation: {"ck_graph_edge_citation_support_role"},
        AgentQuotaReservation: {
            "ck_agent_quota_reservation_principal_daily_limit",
            "ck_agent_quota_reservation_ip_daily_limit",
            "ck_agent_quota_reservation_state",
        },
    }

    for model, expected in expectations.items():
        assert expected <= constraint_names(model, CheckConstraint)


def test_graph_foreign_keys_expose_cascade_relationships() -> None:
    relationships = (
        (SupplyChainGraphSnapshot, "company_id", "company.id", "CASCADE"),
        (
            SupplyChainGraphNode,
            "snapshot_id",
            "supply_chain_graph_snapshot.id",
            "CASCADE",
        ),
        (SupplyChainGraphNode, "company_id", "company.id", None),
        (
            SupplyChainGraphEdge,
            "snapshot_id",
            "supply_chain_graph_snapshot.id",
            "CASCADE",
        ),
        (
            SupplyChainGraphEdge,
            "source_node_id",
            "supply_chain_graph_node.id",
            "CASCADE",
        ),
        (
            SupplyChainGraphEdge,
            "target_node_id",
            "supply_chain_graph_node.id",
            "CASCADE",
        ),
        (
            GraphOfficialSource,
            "snapshot_id",
            "supply_chain_graph_snapshot.id",
            "CASCADE",
        ),
        (
            GraphEdgeCitation,
            "snapshot_id",
            "supply_chain_graph_snapshot.id",
            "CASCADE",
        ),
        (
            GraphEdgeCitation,
            "edge_id",
            "supply_chain_graph_edge.id",
            "CASCADE",
        ),
        (
            GraphEdgeCitation,
            "source_id",
            "graph_official_source.id",
            "CASCADE",
        ),
        (AgentQuotaReservation, "job_id", "ingestion_job.id", "CASCADE"),
    )

    for model, column_name, target, ondelete in relationships:
        reference = foreign_key(model, column_name, target)
        assert reference.target_fullname == target
        assert reference.ondelete == ondelete


def test_graph_ownership_uses_named_composite_foreign_keys() -> None:
    assert composite_foreign_keys(SupplyChainGraphEdge) == {
        "fk_supply_chain_graph_edge_source_node_owner": (
            ("snapshot_id", "source_node_id"),
            (
                "supply_chain_graph_node.snapshot_id",
                "supply_chain_graph_node.id",
            ),
        ),
        "fk_supply_chain_graph_edge_target_node_owner": (
            ("snapshot_id", "target_node_id"),
            (
                "supply_chain_graph_node.snapshot_id",
                "supply_chain_graph_node.id",
            ),
        ),
    }
    assert composite_foreign_keys(GraphEdgeCitation) == {
        "fk_graph_edge_citation_edge_owner": (
            ("snapshot_id", "edge_id"),
            (
                "supply_chain_graph_edge.snapshot_id",
                "supply_chain_graph_edge.id",
            ),
        ),
        "fk_graph_edge_citation_source_owner": (
            ("snapshot_id", "source_id"),
            (
                "graph_official_source.snapshot_id",
                "graph_official_source.id",
            ),
        ),
    }


def test_ingestion_job_exposes_nullable_graph_snapshot_relationship() -> None:
    column = IngestionJob.__table__.columns["graph_snapshot_id"]
    reference = next(iter(column.foreign_keys))
    job = IngestionJob(
        company_id=1,
        requested_by_type="guest",
        requested_by_hash="guest-hash",
        deduplication_key="graph:company:schema:prompt:model",
        state="queued",
        current_step="queued",
    )

    assert job.graph_snapshot_id is None
    assert column.nullable is True
    assert reference.target_fullname == "supply_chain_graph_snapshot.id"
    assert reference.ondelete == "SET NULL"


def test_agent_quota_reservation_has_one_unique_job_id() -> None:
    with build_session() as session:
        company = Company(symbol="AAPL", cik="0000320193", name="Apple Inc.")
        session.add(company)
        session.commit()
        session.refresh(company)
        assert company.id is not None

        job = IngestionJob(
            job_type="supply_chain_graph",
            company_id=company.id,
            requested_by_type="guest",
            requested_by_hash="guest-hash",
            deduplication_key="graph:company:schema:prompt:model",
            state="queued",
            current_step="queued",
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        reservation = AgentQuotaReservation(
            job_id=job.id,
            principal_type="guest",
            principal_hash="guest-hash",
            usage_date=date(2026, 7, 14),
            principal_daily_limit=2,
            ip_daily_limit=10,
            state="reserved",
        )
        duplicate = AgentQuotaReservation(
            job_id=job.id,
            principal_type="guest",
            principal_hash="guest-hash",
            usage_date=date(2026, 7, 14),
            principal_daily_limit=2,
            ip_daily_limit=10,
            state="reserved",
        )
        session.add(reservation)
        session.commit()
        session.add(duplicate)

        with pytest.raises(IntegrityError):
            session.commit()


def test_graph_entities_round_trip_with_citations_and_job_reference() -> None:
    with build_session() as session:
        company = Company(symbol="AAPL", cik="0000320193", name="Apple Inc.")
        session.add(company)
        session.commit()
        session.refresh(company)
        assert company.id is not None

        snapshot = SupplyChainGraphSnapshot(
            company_id=company.id,
            status="completed",
            schema_version="supply-chain-graph.v1",
            prompt_version="supply-chain-graph.2026-07-14",
            model_id="gpt-5-mini",
            source_fingerprint="a" * 64,
            evidence_coverage="complete",
            overall_confidence="High",
            node_count=2,
            edge_count=1,
            verified_at=NOW,
            completed_at=NOW,
        )
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)

        supplier = SupplyChainGraphNode(
            snapshot_id=snapshot.id,
            node_key="company:0001046179",
            kind="company",
            layer="upstream",
            symbol="AVGO",
            cik="0001046179",
            label_en="Broadcom",
            label_zh="博通",
            description_en="Semiconductor supplier.",
            description_zh="半导体供应商。",
            importance=Decimal("0.9000"),
            confidence="High",
            rank=1,
        )
        core = SupplyChainGraphNode(
            snapshot_id=snapshot.id,
            node_key="company:0000320193",
            kind="company",
            layer="core",
            company_id=company.id,
            symbol="AAPL",
            cik="0000320193",
            label_en="Apple",
            label_zh="苹果",
            description_en="Consumer technology company.",
            description_zh="消费科技公司。",
            importance=Decimal("1.0000"),
            confidence="High",
            rank=0,
        )
        session.add_all([supplier, core])
        session.commit()
        session.refresh(supplier)
        session.refresh(core)

        edge = SupplyChainGraphEdge(
            snapshot_id=snapshot.id,
            edge_key=("company:0001046179|supplies|company:0000320193"),
            source_node_id=supplier.id,
            target_node_id=core.id,
            relationship_type="supplies",
            evidence_status="verified",
            confidence="High",
            explanation_en="Broadcom supplies components to Apple.",
            explanation_zh="博通向苹果供应元件。",
            first_observed_at=date(2025, 9, 28),
            last_observed_at=date(2026, 7, 14),
        )
        source = GraphOfficialSource(
            snapshot_id=snapshot.id,
            source_type="sec_filing",
            publisher="Apple Inc.",
            title="Form 10-K",
            canonical_url="https://www.sec.gov/example",
            published_at=date(2025, 10, 31),
            content_hash="b" * 64,
            artifact_key="supply-chain/apple/source.html",
        )
        session.add_all([edge, source])
        session.commit()
        session.refresh(edge)
        session.refresh(source)

        citation = GraphEdgeCitation(
            snapshot_id=snapshot.id,
            edge_id=edge.id,
            source_id=source.id,
            excerpt="Supplier concentration disclosure.",
            source_anchor="item-1-business",
            support_role="primary",
        )
        job = IngestionJob(
            job_type="supply_chain_graph",
            company_id=company.id,
            requested_by_type="user",
            requested_by_hash="user-hash",
            deduplication_key="graph:company:schema:prompt:model",
            state="completed",
            current_step="completed",
            graph_snapshot_id=snapshot.id,
        )
        session.add_all([citation, job])
        session.commit()

        assert citation.edge_id == edge.id
        assert citation.source_id == source.id
        assert job.graph_snapshot_id == snapshot.id


def test_same_snapshot_edge_and_citation_commit_with_foreign_keys_enabled() -> None:
    with build_session() as session:
        snapshot, _ = add_company_and_snapshots(session)
        source_node = graph_node(snapshot.id, "source")
        target_node = graph_node(snapshot.id, "target")
        session.add_all([source_node, target_node])
        session.commit()

        edge = graph_edge(snapshot.id, source_node.id, target_node.id)
        source = graph_source(snapshot.id, "c" * 64)
        session.add_all([edge, source])
        session.commit()

        citation = GraphEdgeCitation(
            snapshot_id=snapshot.id,
            edge_id=edge.id,
            source_id=source.id,
            excerpt="Supplier concentration disclosure.",
            source_anchor="item-1-business",
            support_role="primary",
        )
        session.add(citation)
        session.commit()

        assert citation.snapshot_id == snapshot.id


def test_cross_snapshot_edge_is_rejected_with_foreign_keys_enabled() -> None:
    with build_session() as session:
        snapshot_a, snapshot_b = add_company_and_snapshots(session)
        node_a = graph_node(snapshot_a.id, "node-a")
        node_b = graph_node(snapshot_b.id, "node-b")
        session.add_all([node_a, node_b])
        session.commit()

        invalid_edge = graph_edge(snapshot_a.id, node_b.id, node_a.id)
        session.add(invalid_edge)

        with pytest.raises(IntegrityError):
            session.commit()


def test_cross_snapshot_citation_is_rejected_with_foreign_keys_enabled() -> None:
    with build_session() as session:
        snapshot_a, snapshot_b = add_company_and_snapshots(session)
        source_node = graph_node(snapshot_a.id, "source-a")
        target_node = graph_node(snapshot_a.id, "target-a")
        session.add_all([source_node, target_node])
        session.commit()

        edge = graph_edge(snapshot_a.id, source_node.id, target_node.id)
        source = graph_source(snapshot_b.id, "d" * 64)
        session.add_all([edge, source])
        session.commit()

        invalid_citation = GraphEdgeCitation(
            snapshot_id=snapshot_a.id,
            edge_id=edge.id,
            source_id=source.id,
            excerpt="Supplier concentration disclosure.",
            source_anchor="item-1-business",
            support_role="primary",
        )
        session.add(invalid_citation)

        with pytest.raises(IntegrityError):
            session.commit()


def test_database_rejects_invalid_graph_values() -> None:
    with build_session() as session:
        company = Company(symbol="AAPL", cik="0000320193", name="Apple Inc.")
        session.add(company)
        session.commit()
        session.refresh(company)
        assert company.id is not None

        invalid = SupplyChainGraphSnapshot(
            company_id=company.id,
            status="unknown",
            schema_version="supply-chain-graph.v1",
            prompt_version="supply-chain-graph.2026-07-14",
            model_id="gpt-5-mini",
            source_fingerprint="a" * 64,
        )
        session.add(invalid)

        with pytest.raises(IntegrityError):
            session.commit()
