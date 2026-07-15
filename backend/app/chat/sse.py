import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.chat.schemas import (
    AcceptedEvent,
    CitationPublic,
    CompleteEvent,
    ErrorEvent,
    SectionEvent,
    StageEvent,
)

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}

EventKind = Literal[
    "accepted",
    "stage",
    "section",
    "citation",
    "complete",
    "error",
]
EventPayload = (
    AcceptedEvent
    | StageEvent
    | SectionEvent
    | CitationPublic
    | CompleteEvent
    | ErrorEvent
)

_EVENT_TYPES: dict[str, type[BaseModel]] = {
    "accepted": AcceptedEvent,
    "stage": StageEvent,
    "section": SectionEvent,
    "citation": CitationPublic,
    "complete": CompleteEvent,
    "error": ErrorEvent,
}


@dataclass(frozen=True, slots=True)
class ChatStreamEvent:
    kind: EventKind
    payload: EventPayload


class SseEncoder:
    def __init__(self) -> None:
        self._last_event_id = 0

    def event(self, kind: str, payload: BaseModel) -> str:
        expected = _EVENT_TYPES.get(kind)
        if expected is None:
            raise ValueError("CHAT_SSE_EVENT_INVALID")
        if not isinstance(payload, expected):
            raise ValueError("CHAT_SSE_PAYLOAD_INVALID")
        self._last_event_id += 1
        body = payload.model_dump_json()
        return f"id: {self._last_event_id}\nevent: {kind}\ndata: {body}\n\n"

    @staticmethod
    def heartbeat() -> str:
        return ": heartbeat\n\n"


async def encode_sse_stream(
    events: AsyncIterator[ChatStreamEvent],
    *,
    heartbeat_seconds: float = 15.0,
) -> AsyncIterator[str]:
    if heartbeat_seconds <= 0:
        raise ValueError("heartbeat_seconds must be positive")
    encoder = SseEncoder()
    iterator = events.__aiter__()
    pending = asyncio.create_task(anext(iterator))
    try:
        while True:
            done, _ = await asyncio.wait(
                {pending},
                timeout=heartbeat_seconds,
            )
            if not done:
                yield encoder.heartbeat()
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            yield encoder.event(event.kind, event.payload)
            pending = asyncio.create_task(anext(iterator))
    finally:
        if not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        close = getattr(iterator, "aclose", None)
        if close is not None:
            await close()
