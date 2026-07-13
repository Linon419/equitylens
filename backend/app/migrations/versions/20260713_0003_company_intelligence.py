"""Add company intelligence, evidence, job, and quota schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260713_0003"
down_revision: str | None = "20260713_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "profile_fetched_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_company_symbol", "company", ["symbol"], unique=True)
    op.create_index("ix_company_cik", "company", ["cik"], unique=True)
    op.create_index("ix_company_name", "company", ["name"])

    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "company_id",
            name="uq_watchlist_user_company",
        ),
    )
    op.create_index("ix_watchlist_user_id", "watchlist", ["user_id"])
    op.create_index("ix_watchlist_company_id", "watchlist", ["company_id"])

    op.create_table(
        "market_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(30, 8), nullable=True),
        sa.Column("previous_close", sa.Numeric(30, 8), nullable=True),
        sa.Column("price_change", sa.Numeric(30, 8), nullable=True),
        sa.Column("price_change_percent", sa.Numeric(30, 8), nullable=True),
        sa.Column("market_cap", sa.Numeric(30, 8), nullable=True),
        sa.Column("trailing_eps", sa.Numeric(30, 8), nullable=True),
        sa.Column("trailing_pe", sa.Numeric(30, 8), nullable=True),
        sa.Column("forward_pe", sa.Numeric(30, 8), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "missing_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_market_snapshot_company_id",
        "market_snapshot",
        ["company_id"],
    )
    op.create_index(
        "ix_market_snapshot_fetched_at",
        "market_snapshot",
        ["fetched_at"],
    )

    op.create_table(
        "financial_metric",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(length=64), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.String(length=8), nullable=False),
        sa.Column("period_key", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(30, 4), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("taxonomy_tag", sa.String(length=255), nullable=False),
        sa.Column("accession_number", sa.String(length=20), nullable=False),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "metric_key",
            "period_key",
            "accession_number",
            name="uq_financial_metric_source_period",
        ),
    )
    op.create_index(
        "ix_financial_metric_company_id",
        "financial_metric",
        ["company_id"],
    )
    op.create_index(
        "ix_financial_metric_metric_key",
        "financial_metric",
        ["metric_key"],
    )

    op.create_table(
        "filing",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("accession_number", sa.String(length=20), nullable=False),
        sa.Column("form", sa.String(length=16), nullable=False),
        sa.Column("fiscal_period", sa.String(length=32), nullable=True),
        sa.Column("filed_at", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("primary_document", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "accession_number",
            name="uq_filing_company_accession",
        ),
    )
    op.create_index("ix_filing_company_id", "filing", ["company_id"])
    op.create_index(
        "ix_filing_accession_number",
        "filing",
        ["accession_number"],
    )

    op.create_table(
        "filing_artifact",
        sa.Column("filing_id", sa.Uuid(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("compressed_body", postgresql.BYTEA(), nullable=False),
        sa.Column("compressed_size", sa.Integer(), nullable=False),
        sa.Column("uncompressed_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "compressed_size >= 0",
            name="ck_filing_artifact_compressed_size",
        ),
        sa.CheckConstraint(
            "uncompressed_size >= 0",
            name="ck_filing_artifact_uncompressed_size",
        ),
        sa.ForeignKeyConstraint(
            ["filing_id"],
            ["filing.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("filing_id"),
    )

    op.create_table(
        "filing_section",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filing_id", sa.Uuid(), nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=False),
        sa.Column("source_anchor", sa.String(length=255), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["filing_id"],
            ["filing.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "filing_id",
            "ordinal",
            name="uq_filing_section_filing_ordinal",
        ),
    )
    op.create_index(
        "ix_filing_section_filing_id",
        "filing_section",
        ["filing_id"],
    )

    op.create_table(
        "company_intelligence_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("filing_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence_coverage", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column(
            "content_en",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "content_zh",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("overall_confidence", sa.String(length=16), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["filing_id"],
            ["filing.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "filing_id",
            "schema_version",
            "prompt_version",
            "model_id",
            name="uq_company_intelligence_snapshot_version",
        ),
    )
    op.create_index(
        "ix_company_intelligence_snapshot_company_id",
        "company_intelligence_snapshot",
        ["company_id"],
    )
    op.create_index(
        "ix_company_intelligence_snapshot_filing_id",
        "company_intelligence_snapshot",
        ["filing_id"],
    )
    op.create_index(
        "ix_company_intelligence_snapshot_status",
        "company_intelligence_snapshot",
        ["status"],
    )

    op.create_table(
        "evidence_citation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("filing_id", sa.Uuid(), nullable=False),
        sa.Column("section_label", sa.String(length=255), nullable=False),
        sa.Column("source_anchor", sa.String(length=255), nullable=False),
        sa.Column("excerpt", sa.String(length=1000), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("verification_verdict", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["company_intelligence_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["filing_id"],
            ["filing.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evidence_citation_snapshot_id",
        "evidence_citation",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_evidence_citation_filing_id",
        "evidence_citation",
        ["filing_id"],
    )

    op.create_table(
        "ingestion_job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_type", sa.String(length=16), nullable=False),
        sa.Column("requested_by_hash", sa.String(length=64), nullable=False),
        sa.Column("deduplication_key", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.String(length=32), nullable=False),
        sa.Column("provider_run_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("retry_eligible", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["company_intelligence_snapshot.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deduplication_key",
            name="uq_ingestion_job_deduplication",
        ),
    )
    op.create_index(
        "ix_ingestion_job_company_id",
        "ingestion_job",
        ["company_id"],
    )
    op.create_index(
        "ix_ingestion_job_requested_by_hash",
        "ingestion_job",
        ["requested_by_hash"],
    )
    op.create_index("ix_ingestion_job_state", "ingestion_job", ["state"])

    op.create_table(
        "agent_daily_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("principal_hash", sa.String(length=64), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "accepted_count >= 0",
            name="ck_agent_usage_nonnegative",
        ),
        sa.CheckConstraint(
            "accepted_count <= daily_limit",
            name="ck_agent_usage_limit",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "principal_type",
            "principal_hash",
            "usage_date",
            name="uq_agent_daily_usage_principal_date",
        ),
    )
    op.create_index(
        "ix_agent_daily_usage_principal_type",
        "agent_daily_usage",
        ["principal_type"],
    )
    op.create_index(
        "ix_agent_daily_usage_principal_hash",
        "agent_daily_usage",
        ["principal_hash"],
    )
    op.create_index(
        "ix_agent_daily_usage_usage_date",
        "agent_daily_usage",
        ["usage_date"],
    )


def downgrade() -> None:
    op.drop_table("evidence_citation")
    op.drop_table("filing_section")
    op.drop_table("filing_artifact")
    op.drop_table("ingestion_job")
    op.drop_table("company_intelligence_snapshot")
    op.drop_table("financial_metric")
    op.drop_table("market_snapshot")
    op.drop_table("watchlist")
    op.drop_table("agent_daily_usage")
    op.drop_table("filing")
    op.drop_table("company")
