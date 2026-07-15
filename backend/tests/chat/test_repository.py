from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlmodel import select

from app.chat.repository import ConversationRepository
from app.models.chat_model import (
    ChatQuotaLedger,
    CompanyConversation,
    ConversationMessage,
    WebSearchTrace,
)
from app.quota.identity import RequestPrincipal

NOW = datetime(2026, 7, 15, 10, tzinfo=UTC)
GUEST = RequestPrincipal.guest("g" * 64, "i" * 64)
OTHER_GUEST = RequestPrincipal.guest("h" * 64, "j" * 64)
USER = RequestPrincipal.user(7, "q" * 32)
OTHER_USER = RequestPrincipal.user(8, "q" * 32)


def test_user_principal_retains_database_identity() -> None:
    assert USER.user_id == 7
    assert GUEST.user_id is None


def test_guest_reuses_one_active_conversation_per_company(chat_session) -> None:
    repository = ConversationRepository(chat_session)

    first = repository.create_or_get_guest(
        company_id=1,
        principal=GUEST,
        locale="en-US",
        title="Apple research",
        now=NOW,
        retention_days=7,
    )
    second = repository.create_or_get_guest(
        company_id=1,
        principal=GUEST,
        locale="zh-CN",
        title="Ignored replacement",
        now=NOW + timedelta(hours=1),
        retention_days=7,
    )
    chat_session.commit()

    assert second.id == first.id
    assert second.locale == "en-US"
    assert len(repository.list_for_company(1, GUEST, now=NOW)) == 1


def test_expired_guest_is_archived_before_replacement(chat_session) -> None:
    repository = ConversationRepository(chat_session)
    first = repository.create_or_get_guest(
        company_id=1,
        principal=GUEST,
        locale="en-US",
        title="Old research",
        now=NOW,
        retention_days=7,
    )
    replacement_time = NOW + timedelta(days=8)
    second = repository.create_or_get_guest(
        company_id=1,
        principal=GUEST,
        locale="en-US",
        title="Fresh research",
        now=replacement_time,
        retention_days=7,
    )
    chat_session.commit()
    chat_session.refresh(first)

    assert second.id != first.id
    assert first.archived_at is not None
    assert first.archived_at.replace(tzinfo=UTC) == replacement_time
    assert second.expires_at is not None
    assert second.expires_at.replace(tzinfo=UTC) == (
        replacement_time + timedelta(days=7)
    )


def test_authenticated_users_can_create_multiple_isolated_conversations(
    chat_session,
) -> None:
    repository = ConversationRepository(chat_session)
    first = repository.create_user(
        company_id=1,
        principal=USER,
        locale="en-US",
        title="Margins",
        now=NOW,
    )
    second = repository.create_user(
        company_id=1,
        principal=USER,
        locale="en-US",
        title="Supply chain",
        now=NOW + timedelta(seconds=1),
    )
    chat_session.commit()

    assert first.id != second.id
    assert [item.id for item in repository.list_for_company(1, USER, now=NOW)] == [
        second.id,
        first.id,
    ]
    assert repository.get_owned(first.id, OTHER_USER, now=NOW) is None
    assert repository.get_owned(first.id, USER, now=NOW, company_id=2) is None
    assert repository.get_owned(first.id, USER, now=NOW, company_id=1) is not None


def test_only_authenticated_owner_can_rename_and_archive(chat_session) -> None:
    repository = ConversationRepository(chat_session)
    user_conversation = repository.create_user(
        company_id=1,
        principal=USER,
        locale="en-US",
        title="Original",
        now=NOW,
    )
    guest_conversation = repository.create_or_get_guest(
        company_id=1,
        principal=GUEST,
        locale="en-US",
        title="Guest research",
        now=NOW,
        retention_days=7,
    )

    renamed = repository.rename_owned(
        user_conversation.id,
        USER,
        title="Renamed",
        now=NOW + timedelta(minutes=1),
    )
    assert renamed is not None and renamed.title == "Renamed"
    assert (
        repository.rename_owned(
            guest_conversation.id,
            GUEST,
            title="Forbidden",
            now=NOW,
        )
        is None
    )
    assert repository.archive_owned(user_conversation.id, OTHER_USER, now=NOW) is None
    assert repository.archive_owned(user_conversation.id, USER, now=NOW) is not None
    chat_session.commit()

    assert repository.get_owned(user_conversation.id, USER, now=NOW) is None
    assert repository.list_for_company(1, USER, now=NOW) == []


def test_messages_are_idempotent_and_cursor_paginated(chat_session) -> None:
    repository = ConversationRepository(chat_session)
    conversation = repository.create_user(
        company_id=1,
        principal=USER,
        locale="en-US",
        title="Pagination",
        now=NOW,
    )
    request_ids = [uuid4() for _ in range(5)]
    messages = [
        repository.add_user_message(
            conversation_id=conversation.id,
            request_id=request_ids[index],
            content=f"Question {index}",
            locale="en-US",
            context_selection=[],
            created_at=NOW + timedelta(seconds=index),
        )
        for index in range(5)
    ]
    chat_session.commit()

    assert repository.message_by_request(conversation.id, request_ids[2]).id == (
        messages[2].id
    )
    first, cursor = repository.list_messages(conversation.id, limit=2)
    second, cursor = repository.list_messages(
        conversation.id,
        limit=2,
        cursor=cursor,
    )
    third, cursor = repository.list_messages(
        conversation.id,
        limit=2,
        cursor=cursor,
    )

    assert [item.content for item in first] == ["Question 0", "Question 1"]
    assert [item.content for item in second] == ["Question 2", "Question 3"]
    assert [item.content for item in third] == ["Question 4"]
    assert cursor is None


def test_cleanup_deletes_expired_evidence_and_retains_quota_aggregate(
    chat_session,
) -> None:
    repository = ConversationRepository(chat_session)
    conversation = repository.create_or_get_guest(
        company_id=1,
        principal=GUEST,
        locale="en-US",
        title="Temporary",
        now=NOW - timedelta(days=8),
        retention_days=7,
    )
    user_message = repository.add_user_message(
        conversation_id=conversation.id,
        request_id=uuid4(),
        content="Question",
        locale="en-US",
        context_selection=[],
        created_at=NOW - timedelta(days=8),
    )
    assistant = ConversationMessage(
        conversation_id=conversation.id,
        reply_to_message_id=user_message.id,
        role="assistant",
        state="completed",
        content="{}",
        locale="en-US",
        completed_at=NOW - timedelta(days=8),
    )
    chat_session.add(assistant)
    chat_session.flush()
    trace = WebSearchTrace(
        assistant_message_id=assistant.id,
        normalized_query="old query",
        search_decision="agent_requested",
        search_reason="agent_tool",
        candidate_results=[],
        selected_result_ids=[],
        artifact_key="chat-web/old.json.gz",
        artifact_sha256="a" * 64,
        duration_ms=12,
        tool_ordinal=0,
    )
    ledger = ChatQuotaLedger(
        request_id=uuid4(),
        principal_type="guest",
        principal_key=GUEST.principal_hash,
        usage_date=NOW.date(),
        conversation_id=conversation.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant.id,
        state="consumed",
    )
    chat_session.add_all([trace, ledger])
    chat_session.commit()
    conversation_id = conversation.id
    assistant_id = assistant.id
    trace_id = trace.id

    artifact_keys = repository.cleanup_expired_guests(now=NOW)
    chat_session.commit()
    stored_ledger = chat_session.exec(select(ChatQuotaLedger)).one()

    assert artifact_keys == ["chat-web/old.json.gz"]
    assert chat_session.get(CompanyConversation, conversation_id) is None
    assert chat_session.get(ConversationMessage, assistant_id) is None
    assert chat_session.get(WebSearchTrace, trace_id) is None
    assert stored_ledger.conversation_id is None
    assert stored_ledger.user_message_id is None
    assert stored_ledger.assistant_message_id is None


def test_guest_ownership_isolated_by_hash_and_company(chat_session) -> None:
    repository = ConversationRepository(chat_session)
    conversation = repository.create_or_get_guest(
        company_id=1,
        principal=GUEST,
        locale="en-US",
        title="Private",
        now=NOW,
        retention_days=7,
    )
    chat_session.commit()

    assert repository.get_owned(conversation.id, OTHER_GUEST, now=NOW) is None
    assert repository.get_owned(conversation.id, GUEST, now=NOW, company_id=2) is None
    assert (
        repository.get_owned(conversation.id, GUEST, now=NOW, company_id=1)
        is not None
    )
