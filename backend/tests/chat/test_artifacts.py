from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.chat.artifacts import (
    ChatArtifactError,
    S3ChatArtifactStore,
    VercelBlobChatArtifactStore,
    WebArtifactArchive,
    WebArtifactPage,
)

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)


class RecordingStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.puts: list[dict] = []
        self.deletes: list[str] = []

    async def put(self, **kwargs) -> str:
        self.puts.append(kwargs)
        key = kwargs["object_key"]
        body = kwargs["body"]
        assert kwargs["content_type"] == "application/gzip"
        assert kwargs["sha256"] == sha256(body).hexdigest()
        existing = self.objects.get(key)
        if existing is not None and existing != body:
            raise RuntimeError("collision")
        self.objects[key] = body
        return key

    async def get(self, *, artifact_key: str) -> bytes:
        return self.objects[artifact_key]

    async def delete(self, *, artifact_key: str) -> None:
        self.deletes.append(artifact_key)
        self.objects.pop(artifact_key, None)


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, str]]] = {}

    def put_object(self, **kwargs) -> None:
        key = kwargs["Key"]
        if key in self.objects:
            raise RuntimeError("precondition failed")
        self.objects[key] = (kwargs["Body"], kwargs["Metadata"])

    def head_object(self, **kwargs) -> dict:
        return {"Metadata": self.objects[kwargs["Key"]][1]}

    def get_object(self, **kwargs) -> dict:
        return {"Body": BytesIO(self.objects[kwargs["Key"]][0])}

    def delete_object(self, **kwargs) -> None:
        self.objects.pop(kwargs["Key"], None)


class FakeBlobClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, path: str, body: bytes, **kwargs):
        if path in self.objects:
            raise RuntimeError("already exists")
        self.objects[path] = body
        return SimpleNamespace(url=f"https://private.example/{path}")

    async def get(self, path: str, **kwargs):
        return SimpleNamespace(status_code=200, content=self.objects[path])

    async def delete(self, path: str) -> None:
        self.objects.pop(path, None)


def page() -> WebArtifactPage:
    return WebArtifactPage(
        url="https://www.sec.gov/example",
        title="SEC filing update",
        body_text="Verified source text for a current company event.",
        source_tier="primary",
        published_at=NOW,
        retrieved_at=NOW,
    )


@pytest.mark.asyncio
async def test_web_artifact_round_trip_has_scoped_immutable_key() -> None:
    store = RecordingStore()
    archive = WebArtifactArchive(store, prefix="chat-web")
    conversation_id = uuid4()
    message_id = uuid4()

    stored = await archive.store(
        principal_scope="guest-abc123",
        conversation_id=conversation_id,
        message_id=message_id,
        ordinal=0,
        page=page(),
    )

    assert stored.artifact_key == (
        f"chat-web/guest-abc123/{conversation_id}/{message_id}/"
        f"0-{stored.payload_sha256}.json.gz"
    )
    assert len(stored.payload_sha256) == 64
    assert await archive.load(stored) == page()
    assert (
        await archive.store(
            principal_scope="guest-abc123",
            conversation_id=conversation_id,
            message_id=message_id,
            ordinal=0,
            page=page(),
        )
        == stored
    )


@pytest.mark.asyncio
async def test_web_artifact_verifies_hash_and_deletes_exact_returned_key() -> None:
    store = RecordingStore()
    archive = WebArtifactArchive(store)
    stored = await archive.store(
        principal_scope="user-7",
        conversation_id=uuid4(),
        message_id=uuid4(),
        ordinal=2,
        page=page(),
    )
    store.objects[stored.artifact_key] = b"tampered"

    with pytest.raises(ChatArtifactError, match="CHAT_WEB_ARTIFACT_INVALID"):
        await archive.load(stored)

    await archive.delete(stored.artifact_key)
    assert store.deletes == [stored.artifact_key]


@pytest.mark.asyncio
async def test_web_artifact_rejects_unsafe_scope_and_collision() -> None:
    store = RecordingStore()
    archive = WebArtifactArchive(store)

    with pytest.raises(ChatArtifactError):
        await archive.store(
            principal_scope="../guest",
            conversation_id=uuid4(),
            message_id=uuid4(),
            ordinal=0,
            page=page(),
        )

    conversation_id = uuid4()
    message_id = uuid4()
    stored = await archive.store(
        principal_scope="guest-safe",
        conversation_id=conversation_id,
        message_id=message_id,
        ordinal=0,
        page=page(),
    )
    store.objects[stored.artifact_key] = b"conflicting stored bytes"
    with pytest.raises(ChatArtifactError, match="CHAT_WEB_ARTIFACT_INVALID"):
        await archive.store(
            principal_scope="guest-safe",
            conversation_id=conversation_id,
            message_id=message_id,
            ordinal=0,
            page=page(),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["s3", "vercel_blob"])
async def test_production_artifact_stores_keep_exact_private_key(provider: str) -> None:
    key = "chat-web/guest-safe/conversation/message/0-page.json.gz"
    body = b"compressed artifact"
    digest = sha256(body).hexdigest()
    if provider == "s3":
        client = FakeS3Client()
        store = S3ChatArtifactStore(client, bucket="filings", prefix="chat-web")
    else:
        client = FakeBlobClient()
        store = VercelBlobChatArtifactStore(client, prefix="chat-web")

    first = await store.put(
        object_key=key,
        body=body,
        content_type="application/gzip",
        sha256=digest,
    )
    replay = await store.put(
        object_key=key,
        body=body,
        content_type="application/gzip",
        sha256=digest,
    )

    assert first == replay == key
    assert await store.get(artifact_key=key) == body
    await store.delete(artifact_key=key)
