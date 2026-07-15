"""Add company research chat persistence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260714_0005"
down_revision: str | None = "20260714_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _create_conversation_table()
    _create_message_table()
    _add_summary_checkpoint_foreign_key()
    _create_conversation_indexes()
    _create_citation_table()
    _create_filing_chunk_table()
    _create_web_search_trace_table()
    _create_chat_quota_table()
    _create_postgres_retrieval_indexes()


def downgrade() -> None:
    _drop_postgres_retrieval_indexes()
    op.drop_table("chat_quota_ledger")
    op.drop_table("web_search_trace")
    op.drop_table("message_citation")
    op.drop_table("filing_chunk")
    _drop_summary_checkpoint_foreign_key()
    op.drop_table("conversation_message")
    op.drop_table("company_conversation")


def _create_conversation_table() -> None:
    op.create_table(
        "company_conversation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("guest_principal_hash", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_through_message_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND guest_principal_hash IS NULL) OR "
            "(user_id IS NULL AND guest_principal_hash IS NOT NULL)",
            name="ck_company_conversation_exactly_one_owner",
        ),
        sa.CheckConstraint(
            "locale IN ('en-US', 'zh-CN')",
            name="ck_company_conversation_locale",
        ),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND expires_at IS NULL) OR "
            "(guest_principal_hash IS NOT NULL AND expires_at IS NOT NULL)",
            name="ck_company_conversation_owner_expiration",
        ),
        sa.CheckConstraint(
            "length(title) BETWEEN 1 AND 120",
            name="ck_company_conversation_title_length",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_message_table() -> None:
    op.create_table(
        "conversation_message",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("reply_to_message_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False),
        sa.Column("client_request_id", sa.Uuid(), nullable=True),
        sa.Column("context_selection", sa.JSON(), nullable=False),
        sa.Column("answer_plan", sa.JSON(), nullable=True),
        sa.Column("model_id", sa.String(length=128), nullable=True),
        sa.Column("evidence_coverage", sa.String(length=16), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_conversation_message_role",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'planning', 'completed', 'failed')",
            name="ck_conversation_message_state",
        ),
        sa.CheckConstraint(
            "locale IN ('en-US', 'zh-CN')",
            name="ck_conversation_message_locale",
        ),
        sa.CheckConstraint(
            "(role = 'user' AND client_request_id IS NOT NULL) OR "
            "(role = 'assistant' AND client_request_id IS NULL)",
            name="ck_conversation_message_request_owner",
        ),
        sa.CheckConstraint(
            "(role = 'assistant') OR length(content) BETWEEN 1 AND 2000",
            name="ck_conversation_message_content_length",
        ),
        sa.CheckConstraint(
            "evidence_coverage IS NULL OR evidence_coverage IN "
            "('complete', 'partial', 'insufficient')",
            name="ck_conversation_message_evidence_coverage",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_conversation_message_attempt_count",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["company_conversation.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_message_id"],
            ["conversation_message.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "client_request_id",
            name="uq_conversation_message_request",
        ),
    )


def _add_summary_checkpoint_foreign_key() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("company_conversation") as batch:
            batch.create_foreign_key(
                "fk_company_conversation_summary_message",
                "conversation_message",
                ["summary_through_message_id"],
                ["id"],
                ondelete="SET NULL",
            )
        return
    op.create_foreign_key(
        "fk_company_conversation_summary_message",
        "company_conversation",
        "conversation_message",
        ["summary_through_message_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _create_conversation_indexes() -> None:
    op.create_index(
        "ix_company_conversation_company_id",
        "company_conversation",
        ["company_id"],
    )
    op.create_index(
        "ix_company_conversation_user_id",
        "company_conversation",
        ["user_id"],
    )
    op.create_index(
        "ix_company_conversation_guest_principal_hash",
        "company_conversation",
        ["guest_principal_hash"],
    )
    active_guest = sa.text(
        "archived_at IS NULL AND guest_principal_hash IS NOT NULL"
    )
    op.create_index(
        "uq_company_conversation_active_guest",
        "company_conversation",
        ["company_id", "guest_principal_hash"],
        unique=True,
        postgresql_where=active_guest,
        sqlite_where=active_guest,
    )
    op.create_index(
        "ix_conversation_message_conversation_id",
        "conversation_message",
        ["conversation_id"],
    )
    op.create_index(
        "ix_conversation_message_reply_to_message_id",
        "conversation_message",
        ["reply_to_message_id"],
    )
    op.create_index(
        "ix_conversation_message_state",
        "conversation_message",
        ["state"],
    )


def _create_citation_table() -> None:
    op.create_table(
        "message_citation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_anchor", sa.String(length=255), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_tier", sa.String(length=24), nullable=False),
        sa.Column("verification", sa.String(length=16), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="ck_message_citation_ordinal"),
        sa.CheckConstraint(
            "source_kind IN ('filing', 'financial', 'intelligence', 'graph', 'web')",
            name="ck_message_citation_source_kind",
        ),
        sa.CheckConstraint(
            "source_tier IN ('primary', 'trusted_secondary', 'derived')",
            name="ck_message_citation_source_tier",
        ),
        sa.CheckConstraint(
            "verification IN ('verified', 'supporting')",
            name="ck_message_citation_verification",
        ),
        sa.CheckConstraint(
            "length(excerpt) >= 1 AND "
            "((source_kind = 'web' AND length(excerpt) <= 600) OR "
            "(source_kind <> 'web' AND length(excerpt) <= 1000))",
            name="ck_message_citation_excerpt_length",
        ),
        sa.CheckConstraint(
            "substr(source_url, 1, 8) = 'https://'",
            name="ck_message_citation_https_url",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["conversation_message.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id",
            "ordinal",
            name="uq_message_citation_ordinal",
        ),
    )
    op.create_index(
        "ix_message_citation_message_id",
        "message_citation",
        ["message_id"],
    )


def _create_filing_chunk_table() -> None:
    op.create_table(
        "filing_chunk",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("filing_id", sa.Uuid(), nullable=False),
        sa.Column("section_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("chunk_schema_version", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(1_536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="ck_filing_chunk_ordinal"),
        sa.CheckConstraint(
            "token_count > 0",
            name="ck_filing_chunk_token_count",
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64",
            name="ck_filing_chunk_content_hash",
        ),
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
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["filing_section.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "filing_id",
            "section_id",
            "ordinal",
            "chunk_schema_version",
            "embedding_model",
            name="uq_filing_chunk_version",
        ),
    )
    for column in ("company_id", "filing_id", "section_id"):
        op.create_index(
            f"ix_filing_chunk_{column}",
            "filing_chunk",
            [column],
        )


def _create_web_search_trace_table() -> None:
    op.create_table(
        "web_search_trace",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assistant_message_id", sa.Uuid(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("search_decision", sa.String(length=32), nullable=False),
        sa.Column("search_reason", sa.String(length=64), nullable=False),
        sa.Column("candidate_results", sa.JSON(), nullable=False),
        sa.Column("selected_result_ids", sa.JSON(), nullable=False),
        sa.Column("artifact_key", sa.String(length=1024), nullable=True),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=True),
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("tool_ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "search_decision IN "
            "('required_current', 'required_low_evidence', 'agent_requested')",
            name="ck_web_search_trace_decision",
        ),
        sa.CheckConstraint(
            "duration_ms >= 0",
            name="ck_web_search_trace_duration",
        ),
        sa.CheckConstraint(
            "tool_ordinal >= 0",
            name="ck_web_search_trace_tool_ordinal",
        ),
        sa.CheckConstraint(
            "(artifact_key IS NULL AND artifact_sha256 IS NULL) OR "
            "(artifact_key IS NOT NULL AND artifact_sha256 IS NOT NULL)",
            name="ck_web_search_trace_artifact_pair",
        ),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            ["conversation_message.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_web_search_trace_assistant_message_id",
        "web_search_trace",
        ["assistant_message_id"],
    )


def _create_chat_quota_table() -> None:
    op.create_table(
        "chat_quota_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("principal_key", sa.String(length=128), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("user_message_id", sa.Uuid(), nullable=True),
        sa.Column("assistant_message_id", sa.Uuid(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("refund_reason", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "principal_type IN ('guest', 'user')",
            name="ck_chat_quota_ledger_principal_type",
        ),
        sa.CheckConstraint(
            "attempt_number >= 0",
            name="ck_chat_quota_ledger_attempt_number",
        ),
        sa.CheckConstraint(
            "state IN ('reserved', 'consumed', 'refunded')",
            name="ck_chat_quota_ledger_state",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["company_conversation.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_message_id"],
            ["conversation_message.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"],
            ["conversation_message.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id",
            name="uq_chat_quota_ledger_request_id",
        ),
    )
    op.create_index(
        "ix_chat_quota_ledger_conversation_id",
        "chat_quota_ledger",
        ["conversation_id"],
    )
    op.create_index(
        "ix_chat_quota_ledger_state",
        "chat_quota_ledger",
        ["state"],
    )
    op.create_index(
        "ix_chat_quota_ledger_principal_date",
        "chat_quota_ledger",
        ["principal_type", "principal_key", "usage_date"],
    )


def _create_postgres_retrieval_indexes() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "CREATE INDEX ix_filing_chunk_embedding_hnsw "
        "ON filing_chunk USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_filing_chunk_fts "
        "ON filing_chunk USING gin (to_tsvector('english', text))"
    )


def _drop_postgres_retrieval_indexes() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_filing_chunk_fts")
    op.execute("DROP INDEX IF EXISTS ix_filing_chunk_embedding_hnsw")


def _drop_summary_checkpoint_foreign_key() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("company_conversation") as batch:
            batch.drop_constraint(
                "fk_company_conversation_summary_message",
                type_="foreignkey",
            )
        return
    op.drop_constraint(
        "fk_company_conversation_summary_message",
        "company_conversation",
        type_="foreignkey",
    )
