import asyncio
import traceback
from hashlib import sha256
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from app.core.config import ObjectStorageProviderName
from app.supply_chain.artifacts import (
    GraphArtifactConflict,
    GraphArtifactError,
    GraphArtifactNotFound,
    GraphArtifactProviderError,
    InMemoryGraphArtifactStore,
    S3GraphArtifactStore,
    VercelBlobGraphArtifactStore,
)


class BytesBody:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content


class RecordingS3:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []
        self.head_calls: list[dict[str, object]] = []
        self.put_error: Exception | None = None
        self.get_error: Exception | None = None
        self.head_metadata: dict[str, str] = {}
        self.head_errors: list[Exception] = []
        self.body = b"stored"

    def put_object(self, **kwargs: object) -> object:
        self.put_calls.append(kwargs)
        if self.put_error is not None:
            raise self.put_error
        return object()

    def get_object(self, **kwargs: object) -> dict[str, object]:
        self.get_calls.append(kwargs)
        if self.get_error is not None:
            raise self.get_error
        return {"Body": BytesBody(self.body)}

    def head_object(self, **kwargs: object) -> dict[str, object]:
        self.head_calls.append(kwargs)
        if self.head_errors:
            raise self.head_errors.pop(0)
        return {"Metadata": self.head_metadata}


class RecordingBlob:
    def __init__(self) -> None:
        self.token = "vercel_blob_rw_store123_secret"
        self.put_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.get_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.put_error: Exception | None = None
        self.get_error: Exception | None = None
        self.put_url = (
            "https://store123.private.blob.vercel-storage.com/supply-chain/sha256/a.gz"
        )
        self.get_result: object | None = SimpleNamespace(
            status_code=200,
            content=b"stored",
            url=(
                "https://store123.private.blob.vercel-storage.com/"
                "supply-chain/sha256/a.gz"
            ),
        )

    async def put(self, *args: object, **kwargs: object) -> object:
        self.put_calls.append((args, kwargs))
        if self.put_error is not None:
            raise self.put_error
        return SimpleNamespace(url=self.put_url)

    async def get(self, *args: object, **kwargs: object) -> object | None:
        self.get_calls.append((args, kwargs))
        if self.get_error is not None:
            raise self.get_error
        return self.get_result


def s3_error(code: str, status: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": "provider detail"},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "PutObject",
    )


def digest(body: bytes) -> str:
    return sha256(body).hexdigest()


@pytest.mark.anyio
async def test_memory_store_round_trips_immutable_bytes() -> None:
    store = InMemoryGraphArtifactStore()
    body = b"official source body"
    body_digest = digest(body)

    key = await store.put(
        object_key="sha256/source.html.gz",
        body=body,
        content_type="application/gzip",
        sha256=body_digest,
    )

    assert key == "sha256/source.html.gz"
    assert await store.get(artifact_key=key) == body
    assert (
        await store.put(
            object_key=key,
            body=body,
            content_type="application/gzip",
            sha256=body_digest,
        )
        == key
    )


@pytest.mark.anyio
async def test_memory_store_rejects_conflicts_and_missing_keys() -> None:
    store = InMemoryGraphArtifactStore()
    first_digest = digest(b"first")
    await store.put(
        object_key="a.gz",
        body=b"first",
        content_type="application/gzip",
        sha256=first_digest,
    )

    with pytest.raises(GraphArtifactConflict):
        await store.put(
            object_key="a.gz",
            body=b"second",
            content_type="application/gzip",
            sha256=digest(b"second"),
        )
    with pytest.raises(GraphArtifactConflict):
        await store.put(
            object_key="a.gz",
            body=b"first",
            content_type="application/gzip",
            sha256=digest(b"other"),
        )
    with pytest.raises(GraphArtifactConflict):
        await store.put(
            object_key="a.gz",
            body=b"second",
            content_type="application/gzip",
            sha256=first_digest,
        )
    with pytest.raises(GraphArtifactNotFound):
        await store.get(artifact_key="missing.gz")


@pytest.mark.anyio
async def test_memory_store_serializes_concurrent_same_key_writes() -> None:
    store = InMemoryGraphArtifactStore()
    same_digest = digest(b"same")

    keys = await asyncio.gather(
        *(
            store.put(
                object_key="same.gz",
                body=b"same",
                content_type="application/gzip",
                sha256=same_digest,
            )
            for _ in range(8)
        )
    )

    assert keys == ["same.gz"] * 8


@pytest.mark.anyio
async def test_artifact_keys_reject_path_escape_and_blank_metadata() -> None:
    store = InMemoryGraphArtifactStore()

    for object_key in ("", "../secret", "safe/../secret", "."):
        with pytest.raises(GraphArtifactError):
            await store.put(
                object_key=object_key,
                body=b"body",
                content_type="application/gzip",
                sha256=digest(b"body"),
            )
    with pytest.raises(GraphArtifactError):
        await store.put(
            object_key="safe.gz",
            body=b"body",
            content_type=" ",
            sha256=digest(b"body"),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "supplied_digest",
    ["abc", "A" * 64, digest(b"different")],
)
async def test_artifact_store_requires_verified_canonical_sha256(
    supplied_digest: str,
) -> None:
    client = RecordingS3()
    store = S3GraphArtifactStore(
        client=client, bucket="research", prefix="supply-chain"
    )

    with pytest.raises(GraphArtifactError):
        await store.put(
            object_key="a.gz",
            body=b"payload",
            content_type="application/gzip",
            sha256=supplied_digest,
        )

    assert client.put_calls == []


@pytest.mark.anyio
async def test_s3_store_writes_private_immutable_content() -> None:
    client = RecordingS3()
    store = S3GraphArtifactStore(
        client=client,
        bucket="research",
        prefix="/supply-chain/",
    )

    body = b"payload"
    body_digest = digest(body)
    key = await store.put(
        object_key="/sha256/a.gz",
        body=body,
        content_type="application/gzip",
        sha256=body_digest,
    )

    assert key == "supply-chain/sha256/a.gz"
    assert client.put_calls == [
        {
            "Bucket": "research",
            "Key": key,
            "Body": body,
            "ContentType": "application/gzip",
            "Metadata": {"sha256": body_digest},
            "IfNoneMatch": "*",
        }
    ]


@pytest.mark.anyio
async def test_s3_store_reads_streaming_body() -> None:
    client = RecordingS3()
    client.body = b"exact bytes"
    store = S3GraphArtifactStore(
        client=client, bucket="research", prefix="supply-chain"
    )

    result = await store.get(artifact_key="supply-chain/a.gz")

    assert result == b"exact bytes"
    assert client.get_calls == [{"Bucket": "research", "Key": "supply-chain/a.gz"}]


@pytest.mark.anyio
async def test_s3_store_rejects_reads_outside_configured_prefix() -> None:
    client = RecordingS3()
    store = S3GraphArtifactStore(
        client=client, bucket="research", prefix="supply-chain"
    )

    with pytest.raises(GraphArtifactError):
        await store.get(artifact_key="other-service/private")

    assert client.get_calls == []


@pytest.mark.anyio
async def test_s3_precondition_is_idempotent_only_for_matching_hash() -> None:
    client = RecordingS3()
    client.put_error = s3_error("PreconditionFailed", 412)
    body = b"payload"
    body_digest = digest(body)
    client.head_metadata = {"sha256": body_digest}
    store = S3GraphArtifactStore(
        client=client, bucket="research", prefix="supply-chain"
    )

    key = await store.put(
        object_key="a.gz",
        body=body,
        content_type="application/gzip",
        sha256=body_digest,
    )

    assert key == "supply-chain/a.gz"
    assert client.head_calls == [{"Bucket": "research", "Key": key}]

    client.head_metadata = {"sha256": "other"}
    with pytest.raises(GraphArtifactConflict):
        await store.put(
            object_key="a.gz",
            body=body,
            content_type="application/gzip",
            sha256=body_digest,
        )


@pytest.mark.anyio
async def test_s3_precondition_retries_transient_head_visibility() -> None:
    client = RecordingS3()
    body = b"payload"
    body_digest = digest(body)
    client.put_error = s3_error("PreconditionFailed", 412)
    client.head_errors = [s3_error("NoSuchKey", 404)]
    client.head_metadata = {"sha256": body_digest}
    store = S3GraphArtifactStore(
        client=client, bucket="research", prefix="supply-chain"
    )

    key = await store.put(
        object_key="a.gz",
        body=body,
        content_type="application/gzip",
        sha256=body_digest,
    )

    assert key == "supply-chain/a.gz"
    assert len(client.head_calls) == 2


@pytest.mark.anyio
async def test_s3_precondition_maps_persistent_missing_to_not_found() -> None:
    client = RecordingS3()
    client.put_error = s3_error("PreconditionFailed", 412)
    client.head_errors = [s3_error("NoSuchKey", 404)] * 3
    store = S3GraphArtifactStore(
        client=client,
        bucket="research",
        prefix="supply-chain",
    )

    with pytest.raises(GraphArtifactNotFound):
        await store.put(
            object_key="a.gz",
            body=b"payload",
            content_type="application/gzip",
            sha256=digest(b"payload"),
        )

    assert len(client.head_calls) == 3


@pytest.mark.anyio
async def test_s3_maps_missing_and_provider_errors_safely() -> None:
    client = RecordingS3()
    store = S3GraphArtifactStore(
        client=client, bucket="research", prefix="supply-chain"
    )
    client.get_error = s3_error("NoSuchKey", 404)
    with pytest.raises(GraphArtifactNotFound):
        await store.get(artifact_key="supply-chain/missing.gz")

    client.get_error = RuntimeError("token=super-secret")
    with pytest.raises(GraphArtifactProviderError) as raised:
        await store.get(artifact_key="supply-chain/a.gz")
    assert "super-secret" not in str(raised.value)
    assert "super-secret" not in "".join(traceback.format_exception(raised.value))
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("code", "status"),
    [("NoSuchBucket", 404), ("AccessDenied", 404)],
)
async def test_s3_does_not_misclassify_provider_failures_as_missing(
    code: str,
    status: int,
) -> None:
    client = RecordingS3()
    client.get_error = s3_error(code, status)
    store = S3GraphArtifactStore(
        client=client, bucket="research", prefix="supply-chain"
    )

    with pytest.raises(GraphArtifactProviderError):
        await store.get(artifact_key="supply-chain/a.gz")


@pytest.mark.anyio
async def test_s3_does_not_misclassify_access_denied_as_precondition() -> None:
    client = RecordingS3()
    client.put_error = s3_error("AccessDenied", 412)
    store = S3GraphArtifactStore(
        client=client, bucket="research", prefix="supply-chain"
    )

    with pytest.raises(GraphArtifactProviderError):
        await store.put(
            object_key="a.gz",
            body=b"payload",
            content_type="application/gzip",
            sha256=digest(b"payload"),
        )

    assert client.head_calls == []


@pytest.mark.anyio
async def test_vercel_store_uses_private_immutable_options_and_reads_content() -> None:
    client = RecordingBlob()
    store = VercelBlobGraphArtifactStore(client=client, prefix="supply-chain")
    body = b"payload"

    key = await store.put(
        object_key="sha256/a.gz",
        body=body,
        content_type="application/gzip",
        sha256=digest(body),
    )
    content = await store.get(artifact_key=key)

    assert key == client.put_url
    assert client.put_calls == [
        (
            ("supply-chain/sha256/a.gz", body),
            {
                "access": "private",
                "add_random_suffix": False,
                "overwrite": False,
                "content_type": "application/gzip",
            },
        )
    ]
    assert client.get_calls == [
        (("supply-chain/sha256/a.gz",), {"access": "private", "use_cache": True})
    ]
    assert content == b"stored"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "result", [None, SimpleNamespace(status_code=404, content=b"")]
)
async def test_vercel_store_maps_missing_results(result: object | None) -> None:
    client = RecordingBlob()
    client.get_result = result
    store = VercelBlobGraphArtifactStore(client=client, prefix="supply-chain")

    with pytest.raises(GraphArtifactNotFound):
        await store.get(artifact_key="supply-chain/missing")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "artifact_key",
    [
        "../secret",
        "supply-chain/%2e%2e/secret",
        "https://example.com/supply-chain/a.gz",
        "https://blob.vercel-storage.com/other/a.gz",
        "https://other.private.blob.vercel-storage.com/supply-chain/a.gz",
        "https://store123.public.blob.vercel-storage.com/supply-chain/a.gz",
        "https://blob.vercel-storage.com/supply-chain/%252e%252e/secret",
        "supply-chain/%2525252e%2525252e/secret",
        ("https://blob.vercel-storage.com/supply-chain/%2525252e%2525252e/secret"),
        "https://user:secret@blob.vercel-storage.com/supply-chain/a.gz",
    ],
)
async def test_vercel_store_rejects_unsafe_identifiers_before_sdk_call(
    artifact_key: str,
) -> None:
    client = RecordingBlob()
    store = VercelBlobGraphArtifactStore(client=client, prefix="supply-chain")

    with pytest.raises(GraphArtifactError):
        await store.get(artifact_key=artifact_key)

    assert client.get_calls == []


@pytest.mark.anyio
async def test_vercel_store_binds_urls_to_token_store_and_passes_pathname() -> None:
    client = RecordingBlob()
    store = VercelBlobGraphArtifactStore(client=client, prefix="supply-chain")
    url = "https://store123.private.blob.vercel-storage.com/supply-chain/sha256/a.gz"

    content = await store.get(artifact_key=url)

    assert content == b"stored"
    assert client.get_calls == [
        (("supply-chain/sha256/a.gz",), {"access": "private", "use_cache": True})
    ]


@pytest.mark.anyio
async def test_vercel_store_rejects_mismatched_put_result_url() -> None:
    client = RecordingBlob()
    client.put_url = (
        "https://other.private.blob.vercel-storage.com/supply-chain/sha256/a.gz"
    )
    store = VercelBlobGraphArtifactStore(client=client, prefix="supply-chain")

    with pytest.raises(GraphArtifactProviderError):
        await store.put(
            object_key="sha256/a.gz",
            body=b"payload",
            content_type="application/gzip",
            sha256=digest(b"payload"),
        )


@pytest.mark.anyio
async def test_vercel_failed_put_reconciles_existing_content_by_hash() -> None:
    client = RecordingBlob()
    client.put_error = RuntimeError("unknown provider response")
    client.get_result = SimpleNamespace(
        status_code=200,
        content=b"payload",
        url=(
            "https://store123.private.blob.vercel-storage.com/supply-chain/sha256/a.gz"
        ),
    )
    store = VercelBlobGraphArtifactStore(client=client, prefix="supply-chain")

    key = await store.put(
        object_key="sha256/a.gz",
        body=b"payload",
        content_type="application/gzip",
        sha256=digest(b"payload"),
    )

    assert key == client.get_result.url
    assert client.get_calls == [
        (("supply-chain/sha256/a.gz",), {"access": "private", "use_cache": True})
    ]

    client.get_result.content = b"different"
    with pytest.raises(GraphArtifactConflict):
        await store.put(
            object_key="sha256/a.gz",
            body=b"payload",
            content_type="application/gzip",
            sha256=digest(b"payload"),
        )


@pytest.mark.anyio
async def test_vercel_store_maps_conflict_and_provider_errors_safely() -> None:
    client = RecordingBlob()
    store = VercelBlobGraphArtifactStore(client=client, prefix="supply-chain")
    client.get_result = SimpleNamespace(
        status_code=200,
        content=b"different",
        url=("https://store123.private.blob.vercel-storage.com/supply-chain/a.gz"),
    )
    client.put_error = RuntimeError("blob already exists for token=super-secret")

    with pytest.raises(GraphArtifactConflict) as conflict:
        await store.put(
            object_key="a.gz",
            body=b"payload",
            content_type="application/gzip",
            sha256=digest(b"payload"),
        )
    assert "super-secret" not in str(conflict.value)

    client.put_error = RuntimeError("token=super-secret")
    client.get_result = None
    with pytest.raises(GraphArtifactProviderError) as provider:
        await store.put(
            object_key="b.gz",
            body=b"payload",
            content_type="application/gzip",
            sha256=digest(b"payload"),
        )
    assert "super-secret" not in str(provider.value)
    assert "super-secret" not in "".join(traceback.format_exception(provider.value))
    assert provider.value.__cause__ is None
    assert provider.value.__context__ is None


def test_dependency_selects_s3_without_eager_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import deps

    client = RecordingS3()
    calls: list[tuple[str, str, str, str]] = []

    def build(endpoint: str, access: str, secret: str, region: str) -> RecordingS3:
        calls.append((endpoint, access, secret, region))
        return client

    monkeypatch.setattr(deps, "_get_s3_graph_client", build)
    monkeypatch.setattr(
        deps.settings, "OBJECT_STORAGE_PROVIDER", ObjectStorageProviderName.S3
    )
    monkeypatch.setattr(deps.settings, "S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setattr(deps.settings, "S3_BUCKET", "research")
    monkeypatch.setattr(deps.settings, "S3_ACCESS_KEY_ID", "access")
    monkeypatch.setattr(deps.settings, "S3_SECRET_ACCESS_KEY", "secret")

    store = deps.get_graph_artifact_store()

    assert isinstance(store, S3GraphArtifactStore)
    assert calls == [("http://minio:9000", "access", "secret", "us-east-1")]
    assert client.put_calls == []


def test_dependency_selects_vercel_without_eager_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import deps

    client = RecordingBlob()
    calls: list[str] = []

    def build(token: str) -> RecordingBlob:
        calls.append(token)
        return client

    monkeypatch.setattr(deps, "_get_vercel_blob_client", build)
    monkeypatch.setattr(
        deps.settings,
        "OBJECT_STORAGE_PROVIDER",
        ObjectStorageProviderName.VERCEL_BLOB,
    )
    monkeypatch.setattr(deps.settings, "BLOB_READ_WRITE_TOKEN", "blob-token")

    store = deps.get_graph_artifact_store()

    assert isinstance(store, VercelBlobGraphArtifactStore)
    assert calls == ["blob-token"]
    assert client.put_calls == []
