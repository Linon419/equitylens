import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.chat.schemas import (
    AcceptedEvent,
    ChatQuotaStatus,
    CitationPublic,
    CompleteEvent,
    ErrorEvent,
    MessagePublic,
    SectionEvent,
    StageEvent,
)
from app.chat.sse import (
    SSE_HEADERS,
    ChatStreamEvent,
    SseEncoder,
    encode_sse_stream,
)

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)


def accepted_event() -> AcceptedEvent:
    return AcceptedEvent(
        user_message_id=uuid4(),
        assistant_message_id=uuid4(),
        conversation_id=uuid4(),
        quota=ChatQuotaStatus(
            limit=2,
            used=1,
            remaining=1,
            resets_at=datetime(2026, 7, 16, tzinfo=UTC),
        ),
    )


def citation() -> CitationPublic:
    return CitationPublic(
        id=uuid4(),
        ordinal=0,
        source_kind="filing",
        source_id="item-1",
        title="Form 10-K",
        source_url="https://www.sec.gov/example",
        source_anchor="item-1",
        excerpt="Revenue evidence.",
        published_at=NOW,
        retrieved_at=NOW,
        source_tier="primary",
        verification="verified",
    )


def complete_event() -> CompleteEvent:
    accepted = accepted_event()
    source = citation()
    message = MessagePublic(
        id=accepted.assistant_message_id,
        conversation_id=accepted.conversation_id,
        reply_to_message_id=accepted.user_message_id,
        role="assistant",
        state="completed",
        content="Supported answer.",
        locale="en-US",
        evidence_coverage="complete",
        error_code=None,
        attempt_count=0,
        created_at=NOW,
        completed_at=NOW,
        citations=[source],
    )
    return CompleteEvent(
        message=message,
        citations=[source],
        evidence_coverage="complete",
        quota=accepted.quota,
    )


def test_sse_encoder_emits_monotonic_closed_events() -> None:
    encoder = SseEncoder()
    accepted = encoder.event("accepted", accepted_event())
    stage = encoder.event(
        "stage",
        StageEvent(stage="retrieval", status_key="chat.stage.retrieval"),
    )

    assert accepted.startswith("id: 1\nevent: accepted\ndata: ")
    assert stage.startswith("id: 2\nevent: stage\ndata: ")
    assert encoder.heartbeat() == ": heartbeat\n\n"
    assert SSE_HEADERS == {
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
    }
    with pytest.raises(ValueError, match="CHAT_SSE_EVENT_INVALID"):
        encoder.event("unknown", accepted_event())
    with pytest.raises(ValueError, match="CHAT_SSE_PAYLOAD_INVALID"):
        encoder.event("stage", accepted_event())


def test_sse_json_is_single_line_and_unicode_safe() -> None:
    encoder = SseEncoder()
    encoded = encoder.event(
        "stage",
        StageEvent(stage="web", status_key="网页\n检索"),
    )
    data_line = next(line for line in encoded.splitlines() if line.startswith("data: "))
    payload = json.loads(data_line.removeprefix("data: "))

    assert payload == {"stage": "web", "status_key": "网页\n检索"}
    assert "\\n" in data_line


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("accepted", accepted_event()),
        ("stage", StageEvent(stage="retrieval", status_key="chat.stage.retrieval")),
        ("section", SectionEvent(section="direct_conclusion", delta="Answer")),
        ("citation", citation()),
        ("complete", complete_event()),
        (
            "error",
            ErrorEvent(
                code="CHAT_RETRIEVAL_FAILED",
                retryable=True,
                assistant_message_id=uuid4(),
                quota=accepted_event().quota,
            ),
        ),
    ],
)
def test_sse_encoder_accepts_every_declared_event(kind, payload) -> None:
    assert f"event: {kind}\n" in SseEncoder().event(kind, payload)


@pytest.mark.asyncio
async def test_stream_emits_heartbeat_while_waiting_for_next_event() -> None:
    async def delayed_events():
        await asyncio.sleep(0.03)
        yield ChatStreamEvent(
            "stage",
            StageEvent(stage="compose", status_key="chat.stage.compose"),
        )

    chunks = [
        chunk
        async for chunk in encode_sse_stream(
            delayed_events(),
            heartbeat_seconds=0.01,
        )
    ]

    assert chunks[0] == ": heartbeat\n\n"
    assert any("event: stage" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_closing_encoded_stream_closes_source_iterator() -> None:
    closed = False

    async def source():
        nonlocal closed
        try:
            yield ChatStreamEvent(
                "stage",
                StageEvent(stage="retrieval", status_key="chat.stage.retrieval"),
            )
            await asyncio.Event().wait()
        finally:
            closed = True

    stream = encode_sse_stream(source())
    await anext(stream)
    await stream.aclose()

    assert closed is True
