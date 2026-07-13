from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class JobState(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class UploadIntent:
    object_key: str
    upload_url: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class JobSubmission:
    job_id: str
    state: JobState


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str


class ObjectStorageProvider(Protocol):
    async def create_upload_intent(
        self, *, object_key: str, content_type: str
    ) -> UploadIntent: ...

    async def open(self, *, object_key: str) -> AsyncIterator[bytes]: ...

    async def delete(self, *, object_key: str) -> None: ...


class JobBackend(Protocol):
    async def enqueue(
        self, *, job_type: str, payload: dict[str, str]
    ) -> JobSubmission: ...

    async def get_state(self, *, job_id: str) -> JobState: ...


class CacheProvider(Protocol):
    async def get(self, *, key: str) -> bytes | None: ...

    async def set(self, *, key: str, value: bytes, ttl_seconds: int) -> None: ...


class DocumentParser(Protocol):
    async def parse(self, *, object_key: str) -> list[ParsedPage]: ...
