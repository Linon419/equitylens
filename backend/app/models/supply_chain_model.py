from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from app.models.user_model import utc_now


class SupplyChainGraphSnapshot(SQLModel, table=True):
    __tablename__ = "supply_chain_graph_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "source_fingerprint",
            "schema_version",
            "prompt_version",
            "model_id",
            name="uq_supply_chain_graph_snapshot_version",
        ),
        CheckConstraint(
            "status IN ('drafted', 'verified', 'completed', "
            "'insufficient_evidence', 'failed')",
            name="ck_supply_chain_graph_snapshot_status",
        ),
        CheckConstraint(
            "evidence_coverage IN ('complete', 'partial', 'insufficient_evidence')",
            name="ck_supply_chain_graph_snapshot_evidence_coverage",
        ),
        CheckConstraint(
            "overall_confidence IS NULL OR "
            "overall_confidence IN ('High', 'Medium', 'Low')",
            name="ck_supply_chain_graph_snapshot_confidence",
        ),
        CheckConstraint(
            "node_count >= 0",
            name="ck_supply_chain_graph_snapshot_node_count",
        ),
        CheckConstraint(
            "edge_count >= 0",
            name="ck_supply_chain_graph_snapshot_edge_count",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    status: str = Field(max_length=32, index=True)
    schema_version: str = Field(max_length=64)
    prompt_version: str = Field(max_length=64)
    model_id: str = Field(max_length=128)
    source_fingerprint: str = Field(max_length=64, index=True)
    content_en: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    content_zh: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    evidence_coverage: str = Field(
        default="insufficient_evidence",
        max_length=32,
    )
    overall_confidence: str | None = Field(default=None, max_length=16)
    node_count: int = 0
    edge_count: int = 0
    generated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    verified_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class SupplyChainGraphNode(SQLModel, table=True):
    __tablename__ = "supply_chain_graph_node"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "node_key",
            name="uq_supply_chain_graph_node_key",
        ),
        UniqueConstraint(
            "snapshot_id",
            "id",
            name="uq_supply_chain_graph_node_snapshot_identity",
        ),
        CheckConstraint(
            "kind IN ('company', 'product', 'category', 'business')",
            name="ck_supply_chain_graph_node_kind",
        ),
        CheckConstraint(
            "layer IN ('upstream', 'core', 'downstream')",
            name="ck_supply_chain_graph_node_layer",
        ),
        CheckConstraint(
            "importance >= 0 AND importance <= 1",
            name="ck_supply_chain_graph_node_importance",
        ),
        CheckConstraint(
            "confidence IN ('High', 'Medium', 'Low')",
            name="ck_supply_chain_graph_node_confidence",
        ),
        CheckConstraint(
            "rank >= 0",
            name="ck_supply_chain_graph_node_rank",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    snapshot_id: UUID = Field(
        foreign_key="supply_chain_graph_snapshot.id",
        ondelete="CASCADE",
        index=True,
    )
    node_key: str = Field(max_length=160)
    kind: str = Field(max_length=24)
    layer: str = Field(max_length=24)
    company_id: int | None = Field(default=None, foreign_key="company.id")
    symbol: str | None = Field(default=None, max_length=16)
    cik: str | None = Field(default=None, max_length=16)
    label_en: str = Field(max_length=255)
    label_zh: str = Field(max_length=255)
    description_en: str = Field(sa_column=Column(Text(), nullable=False))
    description_zh: str = Field(sa_column=Column(Text(), nullable=False))
    importance: Decimal = Field(
        sa_column=Column(Numeric(5, 4), nullable=False),
    )
    confidence: str = Field(max_length=16)
    rank: int = 0


class SupplyChainGraphEdge(SQLModel, table=True):
    __tablename__ = "supply_chain_graph_edge"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "edge_key",
            name="uq_supply_chain_graph_edge_key",
        ),
        UniqueConstraint(
            "snapshot_id",
            "id",
            name="uq_supply_chain_graph_edge_snapshot_identity",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "source_node_id"],
            [
                "supply_chain_graph_node.snapshot_id",
                "supply_chain_graph_node.id",
            ],
            name="fk_supply_chain_graph_edge_source_node_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "target_node_id"],
            [
                "supply_chain_graph_node.snapshot_id",
                "supply_chain_graph_node.id",
            ],
            name="fk_supply_chain_graph_edge_target_node_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "relationship_type IN ('supplies', 'manufactures_for', "
            "'distributes_for', 'sells_to', 'licenses_to', 'platform_for', "
            "'component_of', 'serves_market')",
            name="ck_supply_chain_graph_edge_relationship_type",
        ),
        CheckConstraint(
            "evidence_status IN ('verified', 'potential', 'internal')",
            name="ck_supply_chain_graph_edge_evidence_status",
        ),
        CheckConstraint(
            "confidence IN ('High', 'Medium', 'Low')",
            name="ck_supply_chain_graph_edge_confidence",
        ),
        CheckConstraint(
            "source_node_id <> target_node_id",
            name="ck_supply_chain_graph_edge_distinct_nodes",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    snapshot_id: UUID = Field(
        foreign_key="supply_chain_graph_snapshot.id",
        ondelete="CASCADE",
        index=True,
    )
    edge_key: str = Field(max_length=255)
    source_node_id: UUID = Field(index=True)
    target_node_id: UUID = Field(index=True)
    relationship_type: str = Field(max_length=64)
    evidence_status: str = Field(max_length=16)
    confidence: str = Field(max_length=16)
    explanation_en: str = Field(sa_column=Column(Text(), nullable=False))
    explanation_zh: str = Field(sa_column=Column(Text(), nullable=False))
    first_observed_at: date | None = None
    last_observed_at: date | None = None


class GraphOfficialSource(SQLModel, table=True):
    __tablename__ = "graph_official_source"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "content_hash",
            name="uq_graph_official_source_hash",
        ),
        UniqueConstraint(
            "snapshot_id",
            "id",
            name="uq_graph_official_source_snapshot_identity",
        ),
        CheckConstraint(
            "source_type IN ('sec_filing', 'annual_report', 'ir_page', "
            "'official_press_release')",
            name="ck_graph_official_source_type",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    snapshot_id: UUID = Field(
        foreign_key="supply_chain_graph_snapshot.id",
        ondelete="CASCADE",
        index=True,
    )
    source_type: str = Field(max_length=32)
    publisher: str = Field(max_length=255)
    title: str = Field(max_length=500)
    canonical_url: str = Field(sa_column=Column(Text(), nullable=False))
    published_at: date | None = None
    fetched_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    content_hash: str = Field(max_length=64)
    artifact_key: str = Field(sa_column=Column(Text(), nullable=False))


class GraphEdgeCitation(SQLModel, table=True):
    __tablename__ = "graph_edge_citation"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "edge_id",
            "source_id",
            "source_anchor",
            name="uq_graph_edge_citation_anchor",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "edge_id"],
            [
                "supply_chain_graph_edge.snapshot_id",
                "supply_chain_graph_edge.id",
            ],
            name="fk_graph_edge_citation_edge_owner",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["snapshot_id", "source_id"],
            [
                "graph_official_source.snapshot_id",
                "graph_official_source.id",
            ],
            name="fk_graph_edge_citation_source_owner",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "support_role IN ('primary', 'corroborating')",
            name="ck_graph_edge_citation_support_role",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    snapshot_id: UUID = Field(
        foreign_key="supply_chain_graph_snapshot.id",
        ondelete="CASCADE",
        index=True,
    )
    edge_id: UUID = Field(index=True)
    source_id: UUID = Field(index=True)
    excerpt: str = Field(max_length=1500)
    source_anchor: str = Field(max_length=500)
    support_role: str = Field(max_length=24)


class AgentQuotaReservation(SQLModel, table=True):
    __tablename__ = "agent_quota_reservation"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            name="uq_agent_quota_reservation_job_id",
        ),
        CheckConstraint(
            "principal_daily_limit > 0",
            name="ck_agent_quota_reservation_principal_daily_limit",
        ),
        CheckConstraint(
            "ip_daily_limit IS NULL OR ip_daily_limit > 0",
            name="ck_agent_quota_reservation_ip_daily_limit",
        ),
        CheckConstraint(
            "state IN ('reserved', 'consumed', 'refunded')",
            name="ck_agent_quota_reservation_state",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_id: UUID = Field(
        foreign_key="ingestion_job.id",
        ondelete="CASCADE",
        index=True,
    )
    principal_type: str = Field(max_length=16)
    principal_hash: str = Field(max_length=64, index=True)
    ip_hash: str | None = Field(default=None, max_length=64, index=True)
    usage_date: date = Field(index=True)
    principal_daily_limit: int
    ip_daily_limit: int | None = None
    state: str = Field(max_length=16, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    consumed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    refunded_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
