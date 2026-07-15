import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine, select

from app.chat.quota import (
    ChatQuotaExceeded,
    ChatQuotaRequestConflict,
    ChatQuotaService,
    SqlChatQuotaRepository,
)
from app.chat.repository import ConversationRepository
from app.models.chat_model import ChatQuotaLedger, ConversationMessage
from app.models.company_model import Company
from app.models.job_model import AgentDailyUsage
from app.models.user_model import User
from app.quota.identity import RequestPrincipal

NOW = datetime(2026, 7, 15, 10, tzinfo=UTC)
GUEST = RequestPrincipal.guest("g" * 64, "i" * 64)
USER = RequestPrincipal.user(7, "q" * 32)


def build_service(chat_session, principal=GUEST):
    conversations = ConversationRepository(chat_session)
    if principal.principal_type == "guest":
        conversation = conversations.create_or_get_guest(
            company_id=1,
            principal=principal,
            locale="en-US",
            title="Quota research",
            now=NOW,
            retention_days=7,
        )
    else:
        conversation = conversations.create_user(
            company_id=1,
            principal=principal,
            locale="en-US",
            title="Quota research",
            now=NOW,
        )
    return (
        ChatQuotaService(SqlChatQuotaRepository(chat_session)),
        conversation,
    )


def test_guest_receives_two_independent_daily_messages(chat_session) -> None:
    service, conversation = build_service(chat_session)

    first = service.reserve(uuid4(), GUEST, conversation.id, now=NOW)
    second = service.reserve(uuid4(), GUEST, conversation.id, now=NOW)

    assert first.status.remaining == 1
    assert second.status.remaining == 0
    with pytest.raises(ChatQuotaExceeded) as error:
        service.reserve(uuid4(), GUEST, conversation.id, now=NOW)
    assert error.value.code == "CHAT_DAILY_QUOTA_EXCEEDED"
    assert error.value.status_code == 429


def test_user_limit_resets_on_next_utc_day(chat_session) -> None:
    service, conversation = build_service(chat_session, USER)
    for _ in range(10):
        service.reserve(uuid4(), USER, conversation.id, now=NOW)

    assert service.status(USER, now=NOW).remaining == 0
    next_day = NOW + timedelta(days=1)
    assert service.status(USER, now=next_day).remaining == 10
    retry = service.reserve(uuid4(), USER, conversation.id, now=next_day)
    assert retry.status.used == 1


def test_chat_quota_is_independent_from_agent_analysis_usage(chat_session) -> None:
    service, conversation = build_service(chat_session)
    chat_session.add(
        AgentDailyUsage(
            principal_type="guest",
            principal_hash=GUEST.principal_hash,
            usage_date=NOW.date(),
            accepted_count=2,
            daily_limit=2,
        )
    )
    chat_session.flush()

    lease = service.reserve(uuid4(), GUEST, conversation.id, now=NOW)

    assert lease.status.remaining == 1


def test_request_replay_is_idempotent_and_owner_scoped(chat_session) -> None:
    service, conversation = build_service(chat_session)
    request_id = uuid4()

    first = service.reserve(request_id, GUEST, conversation.id, now=NOW)
    replay = service.reserve(request_id, GUEST, conversation.id, now=NOW)

    assert replay.ledger_id == first.ledger_id
    assert replay.status.used == 1
    with pytest.raises(ChatQuotaRequestConflict):
        service.reserve(
            request_id,
            RequestPrincipal.guest("x" * 64, "i" * 64),
            conversation.id,
            now=NOW,
        )


def test_refund_is_idempotent_and_restores_allowance(chat_session) -> None:
    service, conversation = build_service(chat_session)
    lease = service.reserve(uuid4(), GUEST, conversation.id, now=NOW)

    assert service.refund(lease.ledger_id, "CHAT_RETRIEVAL_FAILED", now=NOW)
    assert not service.refund(
        lease.ledger_id,
        "CHAT_RETRIEVAL_FAILED",
        now=NOW,
    )
    assert service.status(GUEST, now=NOW).remaining == 2


@pytest.mark.parametrize("coverage", ["complete", "partial", "insufficient"])
def test_terminal_answer_consumes_one_message(
    chat_session,
    coverage: str,
) -> None:
    service, conversation = build_service(chat_session)
    lease = service.reserve(uuid4(), GUEST, conversation.id, now=NOW)

    assert service.consume(lease.ledger_id, coverage, now=NOW)
    assert not service.consume(lease.ledger_id, coverage, now=NOW)
    assert not service.refund(lease.ledger_id, "LATE_FAILURE", now=NOW)
    assert service.status(GUEST, now=NOW).used == 1


def test_refunded_attempt_can_use_fresh_retry_request(chat_session) -> None:
    service, conversation = build_service(chat_session)
    first = service.reserve(uuid4(), GUEST, conversation.id, now=NOW)
    service.refund(first.ledger_id, "CHAT_ANSWER_GENERATION_FAILED", now=NOW)

    retry = service.reserve(
        uuid4(),
        GUEST,
        conversation.id,
        now=NOW,
        attempt_number=1,
    )
    service.consume(retry.ledger_id, "complete", now=NOW)

    assert retry.attempt_number == 1
    assert service.status(GUEST, now=NOW).used == 1


def test_ledger_attaches_message_ids_after_reservation(chat_session) -> None:
    service, conversation = build_service(chat_session)
    request_id = uuid4()
    lease = service.reserve(request_id, GUEST, conversation.id, now=NOW)
    user_message = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        state="completed",
        content="Question",
        locale="en-US",
        client_request_id=request_id,
        completed_at=NOW,
    )
    assistant_message = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        state="pending",
        content="",
        locale="en-US",
        reply_to_message_id=user_message.id,
    )
    chat_session.add_all([user_message, assistant_message])
    chat_session.flush()

    service.attach_messages(
        lease.ledger_id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
    )
    row = chat_session.exec(
        select(ChatQuotaLedger).where(ChatQuotaLedger.id == lease.ledger_id)
    ).one()

    assert row.user_message_id == user_message.id
    assert row.assistant_message_id == assistant_message.id


def test_status_uses_utc_reset_boundary(chat_session) -> None:
    service, _conversation = build_service(chat_session)

    status = service.status(GUEST, now=NOW)

    assert status.resets_at == datetime(2026, 7, 16, tzinfo=UTC)
    assert status.limit == 2
    assert status.used == 0
    assert status.remaining == 2


def test_user_ledger_stores_stable_user_key(chat_session) -> None:
    service, conversation = build_service(chat_session, USER)

    lease = service.reserve(uuid4(), USER, conversation.id, now=NOW)
    row = chat_session.get(ChatQuotaLedger, lease.ledger_id)

    assert row is not None
    assert row.principal_type == "user"
    assert row.principal_key == "7"
    assert row.usage_date == date(2026, 7, 15)


@pytest.mark.postgres
def test_concurrent_postgres_reservations_stop_at_guest_limit() -> None:
    database_url = os.getenv("TEST_POSTGRES_URL")
    if database_url is None:
        pytest.skip("TEST_POSTGRES_URL is not configured")
    sync_url = make_url(database_url).set(drivername="postgresql+psycopg2")
    admin_engine = create_engine(sync_url)
    schema = f"chat_quota_{uuid4().hex}"
    schema_engine = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_engine = create_engine(
            sync_url,
            connect_args={"options": f"-csearch_path={schema},public"},
        )
        SQLModel.metadata.create_all(schema_engine)
        with Session(schema_engine) as session:
            session.add_all(
                [
                    Company(
                        id=1,
                        symbol="AAPL",
                        cik="0000320193",
                        name="Apple Inc.",
                    ),
                    User(id=7, email="concurrency@example.com"),
                ]
            )
            conversation = ConversationRepository(
                session
            ).create_or_get_guest(
                company_id=1,
                principal=GUEST,
                locale="en-US",
                title="Concurrent quota",
                now=NOW,
                retention_days=7,
            )
            conversation_id = conversation.id
            session.commit()

        def reserve_once(_index: int) -> bool:
            assert schema_engine is not None
            with Session(schema_engine) as session:
                service = ChatQuotaService(SqlChatQuotaRepository(session))
                try:
                    service.reserve(
                        uuid4(),
                        GUEST,
                        conversation_id,
                        now=NOW,
                    )
                    session.commit()
                    return True
                except ChatQuotaExceeded:
                    session.rollback()
                    return False

        with ThreadPoolExecutor(max_workers=12) as pool:
            accepted = list(pool.map(reserve_once, range(12)))

        assert sum(accepted) == 2
    finally:
        if schema_engine is not None:
            schema_engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
