from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlmodel import Field, SQLModel

from app.models.user_model import utc_now


class CompanyConversation(SQLModel, table=True):
    __tablename__ = "company_conversation"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND guest_principal_hash IS NULL) OR "
            "(user_id IS NULL AND guest_principal_hash IS NOT NULL)",
            name="ck_company_conversation_exactly_one_owner",
        ),
        CheckConstraint(
            "locale IN ('en-US', 'zh-CN')",
            name="ck_company_conversation_locale",
        ),
        CheckConstraint(
            "(user_id IS NOT NULL AND expires_at IS NULL) OR "
            "(guest_principal_hash IS NOT NULL AND expires_at IS NOT NULL)",
            name="ck_company_conversation_owner_expiration",
        ),
        CheckConstraint(
            "length(title) BETWEEN 1 AND 120",
            name="ck_company_conversation_title_length",
        ),
        Index(
            "uq_company_conversation_active_guest",
            "company_id",
            "guest_principal_hash",
            unique=True,
            postgresql_where=sql_text(
                "archived_at IS NULL AND guest_principal_hash IS NOT NULL"
            ),
            sqlite_where=sql_text(
                "archived_at IS NULL AND guest_principal_hash IS NOT NULL"
            ),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    user_id: int | None = Field(
        default=None,
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
    )
    guest_principal_hash: str | None = Field(
        default=None,
        max_length=64,
        index=True,
    )
    title: str = Field(min_length=1, max_length=120)
    locale: str = Field(max_length=5)
    summary: str | None = Field(
        default=None,
        sa_column=Column(Text(), nullable=True),
    )
    summary_through_message_id: UUID | None = Field(
        default=None,
        foreign_key="conversation_message.id",
        ondelete="SET NULL",
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    archived_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversation_message"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "client_request_id",
            name="uq_conversation_message_request",
        ),
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_conversation_message_role",
        ),
        CheckConstraint(
            "state IN ('pending', 'planning', 'completed', 'failed')",
            name="ck_conversation_message_state",
        ),
        CheckConstraint(
            "locale IN ('en-US', 'zh-CN')",
            name="ck_conversation_message_locale",
        ),
        CheckConstraint(
            "(role = 'user' AND client_request_id IS NOT NULL) OR "
            "(role = 'assistant' AND client_request_id IS NULL)",
            name="ck_conversation_message_request_owner",
        ),
        CheckConstraint(
            "(role = 'assistant') OR length(content) BETWEEN 1 AND 2000",
            name="ck_conversation_message_content_length",
        ),
        CheckConstraint(
            "evidence_coverage IS NULL OR evidence_coverage IN "
            "('complete', 'partial', 'insufficient')",
            name="ck_conversation_message_evidence_coverage",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_conversation_message_attempt_count",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    conversation_id: UUID = Field(
        foreign_key="company_conversation.id",
        ondelete="CASCADE",
        index=True,
    )
    reply_to_message_id: UUID | None = Field(
        default=None,
        foreign_key="conversation_message.id",
        ondelete="SET NULL",
        index=True,
    )
    role: str = Field(max_length=16)
    state: str = Field(max_length=16, index=True)
    content: str = Field(sa_column=Column(Text(), nullable=False))
    locale: str = Field(max_length=5)
    client_request_id: UUID | None = Field(default=None)
    context_selection: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    model_id: str | None = Field(default=None, max_length=128)
    evidence_coverage: str | None = Field(default=None, max_length=16)
    error_code: str | None = Field(default=None, max_length=64)
    attempt_count: int = 0
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class MessageCitation(SQLModel, table=True):
    __tablename__ = "message_citation"
    __table_args__ = (
        UniqueConstraint(
            "message_id",
            "ordinal",
            name="uq_message_citation_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ck_message_citation_ordinal"),
        CheckConstraint(
            "source_kind IN ('filing', 'financial', 'intelligence', 'graph', 'web')",
            name="ck_message_citation_source_kind",
        ),
        CheckConstraint(
            "source_tier IN ('primary', 'trusted_secondary', 'derived')",
            name="ck_message_citation_source_tier",
        ),
        CheckConstraint(
            "verification IN ('verified', 'supporting')",
            name="ck_message_citation_verification",
        ),
        CheckConstraint(
            "length(excerpt) >= 1 AND "
            "((source_kind = 'web' AND length(excerpt) <= 600) OR "
            "(source_kind <> 'web' AND length(excerpt) <= 1000))",
            name="ck_message_citation_excerpt_length",
        ),
        CheckConstraint(
            "substr(source_url, 1, 8) = 'https://'",
            name="ck_message_citation_https_url",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    message_id: UUID = Field(
        foreign_key="conversation_message.id",
        ondelete="CASCADE",
        index=True,
    )
    ordinal: int
    source_kind: str = Field(max_length=16)
    source_id: str | None = Field(default=None, max_length=255)
    title: str = Field(max_length=255)
    source_url: str = Field(sa_column=Column(Text(), nullable=False))
    source_anchor: str | None = Field(default=None, max_length=255)
    excerpt: str = Field(sa_column=Column(Text(), nullable=False))
    published_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    retrieved_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    source_tier: str = Field(max_length=24)
    verification: str = Field(max_length=16)


class FilingChunk(SQLModel, table=True):
    __tablename__ = "filing_chunk"
    __table_args__ = (
        UniqueConstraint(
            "filing_id",
            "section_id",
            "ordinal",
            "chunk_schema_version",
            "embedding_model",
            name="uq_filing_chunk_version",
        ),
        CheckConstraint("ordinal >= 0", name="ck_filing_chunk_ordinal"),
        CheckConstraint(
            "token_count > 0",
            name="ck_filing_chunk_token_count",
        ),
        CheckConstraint(
            "length(content_hash) = 64",
            name="ck_filing_chunk_content_hash",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    filing_id: UUID = Field(
        foreign_key="filing.id",
        ondelete="CASCADE",
        index=True,
    )
    section_id: UUID = Field(
        foreign_key="filing_section.id",
        ondelete="CASCADE",
        index=True,
    )
    ordinal: int
    text: str = Field(sa_column=Column(Text(), nullable=False))
    token_count: int
    content_hash: str = Field(max_length=64)
    chunk_schema_version: str = Field(max_length=64)
    embedding_model: str = Field(max_length=128)
    embedding: list[float] = Field(
        sa_column=Column(Vector(1_536), nullable=False),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class WebSearchTrace(SQLModel, table=True):
    __tablename__ = "web_search_trace"
    __table_args__ = (
        CheckConstraint(
            "search_decision IN "
            "('required_current', 'required_low_evidence', 'agent_requested')",
            name="ck_web_search_trace_decision",
        ),
        CheckConstraint(
            "duration_ms >= 0",
            name="ck_web_search_trace_duration",
        ),
        CheckConstraint(
            "tool_ordinal >= 0",
            name="ck_web_search_trace_tool_ordinal",
        ),
        CheckConstraint(
            "(artifact_key IS NULL AND artifact_sha256 IS NULL) OR "
            "(artifact_key IS NOT NULL AND artifact_sha256 IS NOT NULL)",
            name="ck_web_search_trace_artifact_pair",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    assistant_message_id: UUID = Field(
        foreign_key="conversation_message.id",
        ondelete="CASCADE",
        index=True,
    )
    normalized_query: str = Field(sa_column=Column(Text(), nullable=False))
    search_decision: str = Field(max_length=32)
    search_reason: str = Field(max_length=64)
    candidate_results: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    selected_result_ids: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    artifact_key: str | None = Field(default=None, max_length=1024)
    artifact_sha256: str | None = Field(default=None, max_length=64)
    provider_request_id: str | None = Field(default=None, max_length=255)
    duration_ms: int
    tool_ordinal: int
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ChatQuotaLedger(SQLModel, table=True):
    __tablename__ = "chat_quota_ledger"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            name="uq_chat_quota_ledger_request_id",
        ),
        CheckConstraint(
            "principal_type IN ('guest', 'user')",
            name="ck_chat_quota_ledger_principal_type",
        ),
        CheckConstraint(
            "attempt_number >= 0",
            name="ck_chat_quota_ledger_attempt_number",
        ),
        CheckConstraint(
            "state IN ('reserved', 'consumed', 'refunded')",
            name="ck_chat_quota_ledger_state",
        ),
        Index(
            "ix_chat_quota_ledger_principal_date",
            "principal_type",
            "principal_key",
            "usage_date",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    request_id: UUID
    principal_type: str = Field(max_length=16)
    principal_key: str = Field(max_length=128)
    usage_date: date
    conversation_id: UUID | None = Field(
        default=None,
        foreign_key="company_conversation.id",
        ondelete="SET NULL",
        index=True,
    )
    user_message_id: UUID | None = Field(
        default=None,
        foreign_key="conversation_message.id",
        ondelete="SET NULL",
    )
    assistant_message_id: UUID | None = Field(
        default=None,
        foreign_key="conversation_message.id",
        ondelete="SET NULL",
    )
    attempt_number: int = 0
    state: str = Field(max_length=16, index=True)
    refund_reason: str | None = Field(default=None, max_length=64)
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
