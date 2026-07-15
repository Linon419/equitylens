from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import SQLModel

from app.models.chat_model import (
    ChatQuotaLedger,
    CompanyConversation,
    ConversationMessage,
    FilingChunk,
    MessageCitation,
    WebSearchTrace,
)

NOW = datetime(2026, 7, 15, 10, tzinfo=UTC)


def constraint_names(model: type[SQLModel], kind: type) -> set[str | None]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, kind)
    }


def foreign_key_target(
    model: type[SQLModel],
    column_name: str,
) -> tuple[str, str | None]:
    foreign_key = next(iter(model.__table__.columns[column_name].foreign_keys))
    return foreign_key.target_fullname, foreign_key.ondelete


def test_chat_models_have_uuid_identities_and_expected_tables() -> None:
    conversation_id = uuid4()
    user_message_id = uuid4()
    assistant_message_id = uuid4()
    identities = {
        CompanyConversation(
            company_id=1,
            user_id=7,
            title="Margin research",
            locale="en-US",
        ).id,
        ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            state="completed",
            content="Why did margins rise?",
            locale="en-US",
            client_request_id=uuid4(),
        ).id,
        MessageCitation(
            message_id=assistant_message_id,
            ordinal=0,
            source_kind="filing",
            source_id=str(uuid4()),
            title="Apple 2025 Form 10-K",
            source_url="https://www.sec.gov/example",
            excerpt="Products gross margin increased year over year.",
            retrieved_at=NOW,
            source_tier="primary",
            verification="verified",
        ).id,
        FilingChunk(
            company_id=1,
            filing_id=uuid4(),
            section_id=uuid4(),
            ordinal=0,
            text="Item 1. Business",
            token_count=4,
            content_hash="a" * 64,
            chunk_schema_version="filing-chunk.v1",
            embedding_model="text-embedding-3-small",
            embedding=[0.0] * 1_536,
        ).id,
        WebSearchTrace(
            assistant_message_id=assistant_message_id,
            normalized_query="Apple latest antitrust development",
            search_decision="required_current",
            search_reason="current_intent",
            candidate_results=[],
            selected_result_ids=[],
            provider_request_id="resp_123",
            duration_ms=25,
            tool_ordinal=0,
        ).id,
        ChatQuotaLedger(
            request_id=uuid4(),
            principal_type="guest",
            principal_key="g" * 64,
            usage_date=date(2026, 7, 15),
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            attempt_number=0,
            state="reserved",
        ).id,
    }

    assert all(isinstance(identity, UUID) for identity in identities)
    assert {
        CompanyConversation.__tablename__,
        ConversationMessage.__tablename__,
        MessageCitation.__tablename__,
        FilingChunk.__tablename__,
        WebSearchTrace.__tablename__,
        ChatQuotaLedger.__tablename__,
    } == {
        "company_conversation",
        "conversation_message",
        "message_citation",
        "filing_chunk",
        "web_search_trace",
        "chat_quota_ledger",
    }


def test_conversation_constraints_lock_owner_locale_and_guest_lifecycle() -> None:
    names = constraint_names(CompanyConversation, CheckConstraint)
    indexes = {index.name: index for index in CompanyConversation.__table__.indexes}

    assert {
        "ck_company_conversation_exactly_one_owner",
        "ck_company_conversation_locale",
        "ck_company_conversation_owner_expiration",
        "ck_company_conversation_title_length",
    } <= names
    assert indexes["uq_company_conversation_active_guest"].unique is True
    assert indexes["ix_company_conversation_company_id"].unique is False
    assert foreign_key_target(CompanyConversation, "company_id") == (
        "company.id",
        "CASCADE",
    )
    assert foreign_key_target(CompanyConversation, "user_id") == (
        "user.id",
        "CASCADE",
    )
    assert foreign_key_target(
        CompanyConversation,
        "summary_through_message_id",
    ) == ("conversation_message.id", "SET NULL")

    guest = CompanyConversation(
        company_id=1,
        guest_principal_hash="g" * 64,
        title="Apple research",
        locale="zh-CN",
        expires_at=NOW + timedelta(days=7),
    )
    assert guest.user_id is None
    assert guest.expires_at == NOW + timedelta(days=7)


def test_message_constraints_lock_roles_states_and_idempotency() -> None:
    checks = constraint_names(ConversationMessage, CheckConstraint)
    uniques = constraint_names(ConversationMessage, UniqueConstraint)

    assert {
        "ck_conversation_message_role",
        "ck_conversation_message_state",
        "ck_conversation_message_locale",
        "ck_conversation_message_request_owner",
        "ck_conversation_message_content_length",
        "ck_conversation_message_evidence_coverage",
        "ck_conversation_message_attempt_count",
    } <= checks
    assert "uq_conversation_message_request" in uniques
    assert foreign_key_target(ConversationMessage, "conversation_id") == (
        "company_conversation.id",
        "CASCADE",
    )
    assert foreign_key_target(ConversationMessage, "reply_to_message_id") == (
        "conversation_message.id",
        "SET NULL",
    )


def test_citation_chunk_trace_and_quota_constraints_are_named() -> None:
    assert {
        "ck_message_citation_ordinal",
        "ck_message_citation_source_kind",
        "ck_message_citation_source_tier",
        "ck_message_citation_verification",
        "ck_message_citation_excerpt_length",
        "ck_message_citation_https_url",
    } <= constraint_names(MessageCitation, CheckConstraint)
    assert "uq_message_citation_ordinal" in constraint_names(
        MessageCitation,
        UniqueConstraint,
    )
    assert {
        "ck_filing_chunk_ordinal",
        "ck_filing_chunk_token_count",
        "ck_filing_chunk_content_hash",
    } <= constraint_names(FilingChunk, CheckConstraint)
    assert "uq_filing_chunk_version" in constraint_names(
        FilingChunk,
        UniqueConstraint,
    )
    assert isinstance(FilingChunk.__table__.columns.embedding.type, Vector)
    assert FilingChunk.__table__.columns.embedding.type.dim == 1_536

    assert {
        "ck_web_search_trace_decision",
        "ck_web_search_trace_duration",
        "ck_web_search_trace_tool_ordinal",
        "ck_web_search_trace_artifact_pair",
    } <= constraint_names(WebSearchTrace, CheckConstraint)
    assert {
        "ck_chat_quota_ledger_principal_type",
        "ck_chat_quota_ledger_attempt_number",
        "ck_chat_quota_ledger_state",
    } <= constraint_names(ChatQuotaLedger, CheckConstraint)
    assert "uq_chat_quota_ledger_request_id" in constraint_names(
        ChatQuotaLedger,
        UniqueConstraint,
    )


def test_child_rows_use_cleanup_safe_foreign_keys() -> None:
    assert foreign_key_target(MessageCitation, "message_id") == (
        "conversation_message.id",
        "CASCADE",
    )
    assert foreign_key_target(WebSearchTrace, "assistant_message_id") == (
        "conversation_message.id",
        "CASCADE",
    )
    assert foreign_key_target(ChatQuotaLedger, "conversation_id") == (
        "company_conversation.id",
        "SET NULL",
    )
    assert foreign_key_target(ChatQuotaLedger, "user_message_id") == (
        "conversation_message.id",
        "SET NULL",
    )
    assert foreign_key_target(ChatQuotaLedger, "assistant_message_id") == (
        "conversation_message.id",
        "SET NULL",
    )
