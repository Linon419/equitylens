"""Add agentic supply-chain graph persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0004"
down_revision: str | None = "20260713_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "supply_chain_graph_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("content_en", sa.JSON(), nullable=False),
        sa.Column("content_zh", sa.JSON(), nullable=False),
        sa.Column("evidence_coverage", sa.String(length=32), nullable=False),
        sa.Column("overall_confidence", sa.String(length=16), nullable=True),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('drafted', 'verified', 'completed', "
            "'insufficient_evidence', 'failed')",
            name="ck_supply_chain_graph_snapshot_status",
        ),
        sa.CheckConstraint(
            "evidence_coverage IN ('complete', 'partial', 'insufficient_evidence')",
            name="ck_supply_chain_graph_snapshot_evidence_coverage",
        ),
        sa.CheckConstraint(
            "overall_confidence IS NULL OR "
            "overall_confidence IN ('High', 'Medium', 'Low')",
            name="ck_supply_chain_graph_snapshot_confidence",
        ),
        sa.CheckConstraint(
            "node_count >= 0",
            name="ck_supply_chain_graph_snapshot_node_count",
        ),
        sa.CheckConstraint(
            "edge_count >= 0",
            name="ck_supply_chain_graph_snapshot_edge_count",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "source_fingerprint",
            "schema_version",
            "prompt_version",
            "model_id",
            name="uq_supply_chain_graph_snapshot_version",
        ),
    )
    op.create_index(
        "ix_supply_chain_graph_snapshot_company_id",
        "supply_chain_graph_snapshot",
        ["company_id"],
    )
    op.create_index(
        "ix_supply_chain_graph_snapshot_status",
        "supply_chain_graph_snapshot",
        ["status"],
    )
    op.create_index(
        "ix_supply_chain_graph_snapshot_source_fingerprint",
        "supply_chain_graph_snapshot",
        ["source_fingerprint"],
    )

    op.create_table(
        "supply_chain_graph_node",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("node_key", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("layer", sa.String(length=24), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=16), nullable=True),
        sa.Column("cik", sa.String(length=16), nullable=True),
        sa.Column("label_en", sa.String(length=255), nullable=False),
        sa.Column("label_zh", sa.String(length=255), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=False),
        sa.Column("description_zh", sa.Text(), nullable=False),
        sa.Column("importance", sa.Numeric(5, 4), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('company', 'product', 'category', 'business')",
            name="ck_supply_chain_graph_node_kind",
        ),
        sa.CheckConstraint(
            "layer IN ('upstream', 'core', 'downstream')",
            name="ck_supply_chain_graph_node_layer",
        ),
        sa.CheckConstraint(
            "importance >= 0 AND importance <= 1",
            name="ck_supply_chain_graph_node_importance",
        ),
        sa.CheckConstraint(
            "confidence IN ('High', 'Medium', 'Low')",
            name="ck_supply_chain_graph_node_confidence",
        ),
        sa.CheckConstraint(
            "rank >= 0",
            name="ck_supply_chain_graph_node_rank",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["supply_chain_graph_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "node_key",
            name="uq_supply_chain_graph_node_key",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "id",
            name="uq_supply_chain_graph_node_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_supply_chain_graph_node_snapshot_id",
        "supply_chain_graph_node",
        ["snapshot_id"],
    )

    op.create_table(
        "supply_chain_graph_edge",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("edge_key", sa.String(length=255), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_status", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("explanation_en", sa.Text(), nullable=False),
        sa.Column("explanation_zh", sa.Text(), nullable=False),
        sa.Column("first_observed_at", sa.Date(), nullable=True),
        sa.Column("last_observed_at", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "relationship_type IN ('supplies', 'manufactures_for', "
            "'distributes_for', 'sells_to', 'licenses_to', 'platform_for', "
            "'component_of', 'serves_market')",
            name="ck_supply_chain_graph_edge_relationship_type",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('verified', 'potential', 'internal')",
            name="ck_supply_chain_graph_edge_evidence_status",
        ),
        sa.CheckConstraint(
            "confidence IN ('High', 'Medium', 'Low')",
            name="ck_supply_chain_graph_edge_confidence",
        ),
        sa.CheckConstraint(
            "source_node_id <> target_node_id",
            name="ck_supply_chain_graph_edge_distinct_nodes",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["supply_chain_graph_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "source_node_id"],
            [
                "supply_chain_graph_node.snapshot_id",
                "supply_chain_graph_node.id",
            ],
            name="fk_supply_chain_graph_edge_source_node_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "target_node_id"],
            [
                "supply_chain_graph_node.snapshot_id",
                "supply_chain_graph_node.id",
            ],
            name="fk_supply_chain_graph_edge_target_node_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "edge_key",
            name="uq_supply_chain_graph_edge_key",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "id",
            name="uq_supply_chain_graph_edge_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_supply_chain_graph_edge_snapshot_id",
        "supply_chain_graph_edge",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_supply_chain_graph_edge_source_node_id",
        "supply_chain_graph_edge",
        ["source_node_id"],
    )
    op.create_index(
        "ix_supply_chain_graph_edge_target_node_id",
        "supply_chain_graph_edge",
        ["target_node_id"],
    )

    op.create_table(
        "graph_official_source",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("publisher", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.Date(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("artifact_key", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('sec_filing', 'annual_report', 'ir_page', "
            "'official_press_release')",
            name="ck_graph_official_source_type",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["supply_chain_graph_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "content_hash",
            name="uq_graph_official_source_hash",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            "id",
            name="uq_graph_official_source_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_graph_official_source_snapshot_id",
        "graph_official_source",
        ["snapshot_id"],
    )

    op.create_table(
        "graph_edge_citation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("edge_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("excerpt", sa.String(length=1500), nullable=False),
        sa.Column("source_anchor", sa.String(length=500), nullable=False),
        sa.Column("support_role", sa.String(length=24), nullable=False),
        sa.CheckConstraint(
            "support_role IN ('primary', 'corroborating')",
            name="ck_graph_edge_citation_support_role",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["supply_chain_graph_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "edge_id"],
            [
                "supply_chain_graph_edge.snapshot_id",
                "supply_chain_graph_edge.id",
            ],
            name="fk_graph_edge_citation_edge_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "source_id"],
            [
                "graph_official_source.snapshot_id",
                "graph_official_source.id",
            ],
            name="fk_graph_edge_citation_source_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "edge_id",
            "source_id",
            "source_anchor",
            name="uq_graph_edge_citation_anchor",
        ),
    )
    op.create_index(
        "ix_graph_edge_citation_snapshot_id",
        "graph_edge_citation",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_graph_edge_citation_edge_id",
        "graph_edge_citation",
        ["edge_id"],
    )
    op.create_index(
        "ix_graph_edge_citation_source_id",
        "graph_edge_citation",
        ["source_id"],
    )

    with op.batch_alter_table("ingestion_job") as batch_op:
        batch_op.add_column(sa.Column("graph_snapshot_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_ingestion_job_graph_snapshot_id_supply_chain_graph_snapshot",
            "supply_chain_graph_snapshot",
            ["graph_snapshot_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_ingestion_job_graph_snapshot_id",
            ["graph_snapshot_id"],
        )

    op.create_table(
        "agent_quota_reservation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("principal_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("principal_daily_limit", sa.Integer(), nullable=False),
        sa.Column("ip_daily_limit", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "principal_daily_limit > 0",
            name="ck_agent_quota_reservation_principal_daily_limit",
        ),
        sa.CheckConstraint(
            "ip_daily_limit IS NULL OR ip_daily_limit > 0",
            name="ck_agent_quota_reservation_ip_daily_limit",
        ),
        sa.CheckConstraint(
            "state IN ('reserved', 'consumed', 'refunded')",
            name="ck_agent_quota_reservation_state",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["ingestion_job.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            name="uq_agent_quota_reservation_job_id",
        ),
    )
    op.create_index(
        "ix_agent_quota_reservation_job_id",
        "agent_quota_reservation",
        ["job_id"],
    )
    op.create_index(
        "ix_agent_quota_reservation_principal_hash",
        "agent_quota_reservation",
        ["principal_hash"],
    )
    op.create_index(
        "ix_agent_quota_reservation_ip_hash",
        "agent_quota_reservation",
        ["ip_hash"],
    )
    op.create_index(
        "ix_agent_quota_reservation_usage_date",
        "agent_quota_reservation",
        ["usage_date"],
    )
    op.create_index(
        "ix_agent_quota_reservation_state",
        "agent_quota_reservation",
        ["state"],
    )


def downgrade() -> None:
    op.drop_table("agent_quota_reservation")

    with op.batch_alter_table("ingestion_job") as batch_op:
        batch_op.drop_index("ix_ingestion_job_graph_snapshot_id")
        batch_op.drop_constraint(
            "fk_ingestion_job_graph_snapshot_id_supply_chain_graph_snapshot",
            type_="foreignkey",
        )
        batch_op.drop_column("graph_snapshot_id")

    op.drop_table("graph_edge_citation")
    op.drop_table("graph_official_source")
    op.drop_table("supply_chain_graph_edge")
    op.drop_table("supply_chain_graph_node")
    op.drop_table("supply_chain_graph_snapshot")
