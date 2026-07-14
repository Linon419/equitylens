import asyncio
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit


class GraphArtifactError(RuntimeError):
    """Base error with a stable, non-secret public message."""

    code = "GRAPH_ARTIFACT_ERROR"

    def __init__(self) -> None:
        super().__init__(self.code)


class GraphArtifactConflict(GraphArtifactError):
    code = "GRAPH_ARTIFACT_CONFLICT"


class GraphArtifactNotFound(GraphArtifactError):
    code = "GRAPH_ARTIFACT_NOT_FOUND"


class GraphArtifactProviderError(GraphArtifactError):
    code = "GRAPH_ARTIFACT_PROVIDER_ERROR"


def _require_text(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GraphArtifactError() from ValueError(f"{label} is required")
    return value.strip()


def _normalize_object_key(object_key: str, *, prefix: str = "") -> str:
    raw_key = _require_text(object_key, label="object_key")
    if "\\" in raw_key or any(character.isspace() for character in raw_key):
        raise GraphArtifactError()
    raw_parts = raw_key.split("/")
    if any(part in {".", ".."} for part in raw_parts):
        raise GraphArtifactError()
    parts = [part for part in raw_parts if part]
    prefix_parts: list[str] = []
    if prefix:
        raw_prefix = _require_text(prefix, label="prefix")
        if "\\" in raw_prefix or any(character.isspace() for character in raw_prefix):
            raise GraphArtifactError()
        split_prefix = raw_prefix.split("/")
        if any(part in {".", ".."} for part in split_prefix):
            raise GraphArtifactError()
        prefix_parts = [part for part in split_prefix if part]
    resolved = "/".join([*prefix_parts, *parts])
    if not resolved:
        raise GraphArtifactError()
    return resolved


def _validate_write_metadata(*, content_type: str, sha256: str) -> None:
    _require_text(content_type, label="content_type")
    _require_text(sha256, label="sha256")


def _error_details(error: Exception) -> tuple[str, int | None]:
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return "", None
    error_body = response.get("Error", {})
    metadata = response.get("ResponseMetadata", {})
    code = error_body.get("Code", "") if isinstance(error_body, dict) else ""
    status = metadata.get("HTTPStatusCode") if isinstance(metadata, dict) else None
    return str(code), status if isinstance(status, int) else None


def _is_precondition_failure(error: Exception) -> bool:
    code, status = _error_details(error)
    return code in {"PreconditionFailed", "ConditionalRequestConflict"} or status == 412


def _is_missing(error: Exception) -> bool:
    code, status = _error_details(error)
    return code in {"NoSuchKey", "NotFound", "404"} or status == 404


def _is_blob_conflict(error: Exception) -> bool:
    message = str(error).casefold()
    return any(
        marker in message
        for marker in ("already exists", "destination exists", "conflict", "overwrite")
    )


def _fully_unquote(value: str) -> str:
    decoded = value
    for _ in range(len(value) + 1):
        next_value = unquote(decoded)
        if next_value == decoded:
            return decoded
        decoded = next_value
    raise GraphArtifactError()


def _validate_vercel_artifact_key(artifact_key: str, *, prefix: str) -> str:
    raw_key = _require_text(artifact_key, label="artifact_key")
    parsed = urlsplit(raw_key)
    if parsed.scheme or parsed.netloc:
        try:
            port = parsed.port
        except ValueError as error:
            raise GraphArtifactError() from error
        hostname = parsed.hostname.casefold() if parsed.hostname else ""
        allowed_host = hostname == "blob.vercel-storage.com" or hostname.endswith(
            ".blob.vercel-storage.com"
        )
        if (
            parsed.scheme != "https"
            or not allowed_host
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or parsed.query
            or parsed.fragment
        ):
            raise GraphArtifactError()
        path = parsed.path
    else:
        path = raw_key
    decoded_path = _fully_unquote(path)
    normalized_path = _normalize_object_key(decoded_path)
    if normalized_path != prefix and not normalized_path.startswith(f"{prefix}/"):
        raise GraphArtifactError()
    return raw_key if parsed.scheme else normalized_path


@dataclass(frozen=True, slots=True)
class _MemoryArtifact:
    body: bytes
    content_type: str
    sha256: str


class InMemoryGraphArtifactStore:
    def __init__(self) -> None:
        self._artifacts: dict[str, _MemoryArtifact] = {}
        self._lock = asyncio.Lock()

    async def put(
        self,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> str:
        key = _normalize_object_key(object_key)
        _validate_write_metadata(content_type=content_type, sha256=sha256)
        artifact = _MemoryArtifact(bytes(body), content_type, sha256)
        async with self._lock:
            existing = self._artifacts.get(key)
            if existing is not None and existing != artifact:
                raise GraphArtifactConflict()
            self._artifacts.setdefault(key, artifact)
        return key

    async def get(self, *, artifact_key: str) -> bytes:
        key = _normalize_object_key(artifact_key)
        async with self._lock:
            artifact = self._artifacts.get(key)
        if artifact is None:
            raise GraphArtifactNotFound()
        return artifact.body


class S3GraphArtifactStore:
    def __init__(self, *, client: Any, bucket: str, prefix: str) -> None:
        self._client = client
        self._bucket = _require_text(bucket, label="bucket")
        self._prefix = _normalize_object_key(prefix)

    async def put(
        self,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> str:
        key = _normalize_object_key(object_key, prefix=self._prefix)
        _validate_write_metadata(content_type=content_type, sha256=sha256)
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Metadata={"sha256": sha256},
                IfNoneMatch="*",
            )
        except Exception as error:
            if _is_precondition_failure(error):
                return await self._resolve_existing(key=key, sha256=sha256)
            raise GraphArtifactProviderError() from error
        return key

    async def _resolve_existing(self, *, key: str, sha256: str) -> str:
        try:
            result = await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket,
                Key=key,
            )
        except Exception as error:
            if _is_missing(error):
                raise GraphArtifactNotFound() from error
            raise GraphArtifactProviderError() from error
        metadata = result.get("Metadata", {}) if isinstance(result, dict) else {}
        if isinstance(metadata, dict) and metadata.get("sha256") == sha256:
            return key
        raise GraphArtifactConflict()

    async def get(self, *, artifact_key: str) -> bytes:
        key = _normalize_object_key(artifact_key)
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket,
                Key=key,
            )
            body = response["Body"]
            content = await asyncio.to_thread(body.read)
        except Exception as error:
            if _is_missing(error):
                raise GraphArtifactNotFound() from error
            raise GraphArtifactProviderError() from error
        if not isinstance(content, bytes):
            raise GraphArtifactProviderError()
        return content


class VercelBlobGraphArtifactStore:
    def __init__(self, *, client: Any, prefix: str) -> None:
        self._client = client
        self._prefix = _normalize_object_key(prefix)

    async def put(
        self,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> str:
        path = _normalize_object_key(object_key, prefix=self._prefix)
        _validate_write_metadata(content_type=content_type, sha256=sha256)
        try:
            result = await self._client.put(
                path,
                body,
                access="private",
                add_random_suffix=False,
                overwrite=False,
                content_type=content_type,
            )
            url = result.url
        except Exception as error:
            if _is_blob_conflict(error):
                raise GraphArtifactConflict() from error
            raise GraphArtifactProviderError() from error
        if not isinstance(url, str) or not url:
            raise GraphArtifactProviderError()
        return url

    async def get(self, *, artifact_key: str) -> bytes:
        key = _validate_vercel_artifact_key(artifact_key, prefix=self._prefix)
        try:
            result = await self._client.get(key, access="private", use_cache=True)
        except Exception as error:
            if error.__class__.__name__ == "BlobNotFoundError":
                raise GraphArtifactNotFound() from error
            raise GraphArtifactProviderError() from error
        if result is None or getattr(result, "status_code", None) != 200:
            raise GraphArtifactNotFound()
        content = getattr(result, "content", None)
        if not isinstance(content, bytes):
            raise GraphArtifactProviderError()
        return content
