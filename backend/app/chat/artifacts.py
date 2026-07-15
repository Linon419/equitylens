import gzip
import hashlib
import hmac
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from io import BytesIO
from typing import Protocol
from uuid import UUID


class ChatArtifactError(RuntimeError):
    """Stable public error for invalid or unavailable web artifacts."""

    code = "CHAT_WEB_ARTIFACT_INVALID"

    def __init__(self) -> None:
        super().__init__(self.code)


class ChatArtifactStore(Protocol):
    async def put(
        self,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> str: ...

    async def get(self, *, artifact_key: str) -> bytes: ...

    async def delete(self, *, artifact_key: str) -> None: ...


@dataclass(frozen=True, slots=True)
class WebArtifactPage:
    url: str
    title: str
    body_text: str
    source_tier: str
    published_at: datetime | None
    retrieved_at: datetime

    def __post_init__(self) -> None:
        if (
            not self.url.startswith("https://")
            or not self.title.strip()
            or not self.body_text.strip()
            or self.source_tier not in {"primary", "trusted_secondary"}
            or self.retrieved_at.tzinfo is None
            or (self.published_at is not None and self.published_at.tzinfo is None)
        ):
            raise ValueError("invalid web artifact page")


@dataclass(frozen=True, slots=True)
class StoredWebArtifact:
    artifact_key: str
    artifact_sha256: str
    payload_sha256: str


class WebArtifactArchive:
    def __init__(
        self,
        store: ChatArtifactStore,
        *,
        prefix: str = "chat-web",
        max_payload_bytes: int = 2_000_000,
    ) -> None:
        self._store = store
        self._prefix = _safe_segment(prefix)
        self._max_payload_bytes = max_payload_bytes

    async def store(
        self,
        *,
        principal_scope: str,
        conversation_id: UUID,
        message_id: UUID,
        ordinal: int,
        page: WebArtifactPage,
    ) -> StoredWebArtifact:
        scope = _safe_segment(principal_scope)
        if ordinal < 0:
            raise ChatArtifactError()
        payload = _serialize_page(page)
        if len(payload) > self._max_payload_bytes:
            raise ChatArtifactError()
        payload_sha256 = hashlib.sha256(payload).hexdigest()
        compressed = gzip.compress(payload, mtime=0)
        artifact_sha256 = hashlib.sha256(compressed).hexdigest()
        key = (
            f"{self._prefix}/{scope}/{conversation_id}/{message_id}/"
            f"{ordinal}-{payload_sha256}.json.gz"
        )
        try:
            returned_key = await self._store.put(
                object_key=key,
                body=compressed,
                content_type="application/gzip",
                sha256=artifact_sha256,
            )
        except Exception:
            raise ChatArtifactError() from None
        if returned_key != key:
            raise ChatArtifactError()
        return StoredWebArtifact(key, artifact_sha256, payload_sha256)

    async def load(self, stored: StoredWebArtifact) -> WebArtifactPage:
        try:
            compressed = await self._store.get(artifact_key=stored.artifact_key)
            actual_artifact_hash = hashlib.sha256(compressed).hexdigest()
            if not hmac.compare_digest(actual_artifact_hash, stored.artifact_sha256):
                raise ChatArtifactError()
            payload = _bounded_decompress(compressed, self._max_payload_bytes)
            actual_payload_hash = hashlib.sha256(payload).hexdigest()
            if not hmac.compare_digest(actual_payload_hash, stored.payload_sha256):
                raise ChatArtifactError()
            return _deserialize_page(payload)
        except ChatArtifactError:
            raise
        except Exception:
            raise ChatArtifactError() from None

    async def delete(self, artifact_key: str) -> None:
        _validate_artifact_key(artifact_key, prefix=self._prefix)
        try:
            await self._store.delete(artifact_key=artifact_key)
        except Exception:
            raise ChatArtifactError() from None


_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _safe_segment(value: str) -> str:
    if not isinstance(value, str) or _SAFE_SEGMENT.fullmatch(value) is None:
        raise ChatArtifactError()
    return value


def _validate_artifact_key(value: str, *, prefix: str) -> None:
    if not isinstance(value, str) or "\\" in value:
        raise ChatArtifactError()
    parts = value.split("/")
    unsafe_part = any(part in {"", ".", ".."} for part in parts)
    if not parts or parts[0] != prefix or unsafe_part:
        raise ChatArtifactError()


def _serialize_page(page: WebArtifactPage) -> bytes:
    data = asdict(page)
    data["published_at"] = (
        page.published_at.isoformat() if page.published_at is not None else None
    )
    data["retrieved_at"] = page.retrieved_at.isoformat()
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _deserialize_page(payload: bytes) -> WebArtifactPage:
    try:
        value = json.loads(payload)
        expected = {
            "url",
            "title",
            "body_text",
            "source_tier",
            "published_at",
            "retrieved_at",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError
        string_fields = ("url", "title", "body_text", "source_tier", "retrieved_at")
        if any(not isinstance(value[field], str) for field in string_fields):
            raise ValueError
        published = value["published_at"]
        if published is not None and not isinstance(published, str):
            raise ValueError
        return WebArtifactPage(
            url=value["url"],
            title=value["title"],
            body_text=value["body_text"],
            source_tier=value["source_tier"],
            published_at=(
                datetime.fromisoformat(published) if published is not None else None
            ),
            retrieved_at=datetime.fromisoformat(value["retrieved_at"]),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        raise ChatArtifactError() from None


def _bounded_decompress(compressed: bytes, limit: int) -> bytes:
    try:
        with gzip.GzipFile(fileobj=BytesIO(compressed)) as decompressor:
            payload = decompressor.read(limit + 1)
    except (OSError, EOFError):
        raise ChatArtifactError() from None
    if len(payload) > limit:
        raise ChatArtifactError()
    return payload
