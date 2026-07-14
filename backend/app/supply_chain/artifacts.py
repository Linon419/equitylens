import asyncio
import hashlib
import hmac
import re
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


def _validate_write(
    *,
    body: bytes,
    content_type: str,
    sha256: str,
) -> str:
    if not isinstance(body, bytes):
        raise GraphArtifactError()
    _require_text(content_type, label="content_type")
    supplied_digest = _require_text(sha256, label="sha256")
    if re.fullmatch(r"[0-9a-f]{64}", supplied_digest) is None:
        raise GraphArtifactError()
    actual_digest = hashlib.sha256(body).hexdigest()
    if not hmac.compare_digest(actual_digest, supplied_digest):
        raise GraphArtifactError()
    return actual_digest


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
    if code:
        return code in {
            "PreconditionFailed",
            "ConditionalRequestConflict",
            "412",
        }
    return status == 412


def _is_missing(error: Exception) -> bool:
    code, status = _error_details(error)
    if code:
        return code in {"NoSuchKey", "NotFound", "404"}
    return status == 404


def _fully_unquote(value: str) -> str:
    decoded = value
    for _ in range(len(value) + 1):
        next_value = unquote(decoded)
        if next_value == decoded:
            return decoded
        decoded = next_value
    raise GraphArtifactError()


def _normalize_prefixed_key(artifact_key: str, *, prefix: str) -> str:
    normalized = _normalize_object_key(artifact_key)
    if normalized != prefix and not normalized.startswith(f"{prefix}/"):
        raise GraphArtifactError()
    return normalized


def _vercel_private_hostname(token: str) -> str:
    parts = token.split("_")
    store_id = parts[3] if len(parts) > 3 else ""
    if re.fullmatch(r"[A-Za-z0-9-]+", store_id) is None:
        raise GraphArtifactError()
    return f"{store_id.casefold()}.private.blob.vercel-storage.com"


def _validate_vercel_artifact_key(
    artifact_key: str,
    *,
    prefix: str,
    expected_hostname: str,
) -> str:
    raw_key = _require_text(artifact_key, label="artifact_key")
    parsed = urlsplit(raw_key)
    if parsed.scheme or parsed.netloc:
        try:
            port = parsed.port
        except ValueError as error:
            raise GraphArtifactError() from error
        hostname = parsed.hostname.casefold() if parsed.hostname else ""
        if (
            parsed.scheme != "https"
            or hostname != expected_hostname
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
    return _normalize_prefixed_key(decoded_path, prefix=prefix)


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
        verified_digest = _validate_write(
            body=body,
            content_type=content_type,
            sha256=sha256,
        )
        artifact = _MemoryArtifact(bytes(body), content_type, verified_digest)
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
        verified_digest = _validate_write(
            body=body,
            content_type=content_type,
            sha256=sha256,
        )
        failure: Exception | None = None
        try:
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket,
                Key=key,
                Body=body,
                ContentType=content_type,
                Metadata={"sha256": verified_digest},
                IfNoneMatch="*",
            )
        except Exception as error:
            failure = error
        if failure is not None:
            if _is_precondition_failure(failure):
                return await self._resolve_existing(
                    key=key,
                    sha256=verified_digest,
                )
            raise GraphArtifactProviderError()
        return key

    async def _resolve_existing(self, *, key: str, sha256: str) -> str:
        for attempt in range(3):
            failure: Exception | None = None
            result: object | None = None
            try:
                result = await asyncio.to_thread(
                    self._client.head_object,
                    Bucket=self._bucket,
                    Key=key,
                )
            except Exception as error:
                failure = error
            if failure is None:
                metadata = (
                    result.get("Metadata", {}) if isinstance(result, dict) else {}
                )
                if isinstance(metadata, dict) and metadata.get("sha256") == sha256:
                    return key
                raise GraphArtifactConflict()
            if _is_missing(failure) and attempt < 2:
                await asyncio.sleep(0)
                continue
            raise GraphArtifactProviderError()
        raise GraphArtifactProviderError()

    async def get(self, *, artifact_key: str) -> bytes:
        key = _normalize_prefixed_key(artifact_key, prefix=self._prefix)
        failure: Exception | None = None
        content: object | None = None
        try:
            response = await asyncio.to_thread(
                self._client.get_object,
                Bucket=self._bucket,
                Key=key,
            )
            body = response["Body"]
            content = await asyncio.to_thread(body.read)
        except Exception as error:
            failure = error
        if failure is not None:
            if _is_missing(failure):
                raise GraphArtifactNotFound()
            raise GraphArtifactProviderError()
        if not isinstance(content, bytes):
            raise GraphArtifactProviderError()
        return content


class VercelBlobGraphArtifactStore:
    def __init__(self, *, client: Any, prefix: str) -> None:
        self._client = client
        self._prefix = _normalize_object_key(prefix)
        token = getattr(client, "token", None)
        if not isinstance(token, str):
            raise GraphArtifactError()
        self._expected_hostname = _vercel_private_hostname(token)

    async def put(
        self,
        *,
        object_key: str,
        body: bytes,
        content_type: str,
        sha256: str,
    ) -> str:
        path = _normalize_object_key(object_key, prefix=self._prefix)
        verified_digest = _validate_write(
            body=body,
            content_type=content_type,
            sha256=sha256,
        )
        failure: Exception | None = None
        result: object | None = None
        try:
            result = await self._client.put(
                path,
                body,
                access="private",
                add_random_suffix=False,
                overwrite=False,
                content_type=content_type,
            )
        except Exception as error:
            failure = error
        if failure is not None:
            return await self._reconcile_failed_put(
                path=path,
                sha256=verified_digest,
            )
        url = getattr(result, "url", None)
        if not isinstance(url, str) or not url:
            raise GraphArtifactProviderError()
        valid_result = True
        try:
            returned_path = _validate_vercel_artifact_key(
                url,
                prefix=self._prefix,
                expected_hostname=self._expected_hostname,
            )
        except GraphArtifactError:
            valid_result = False
            returned_path = ""
        if not valid_result or returned_path != path:
            raise GraphArtifactProviderError()
        return url

    async def get(self, *, artifact_key: str) -> bytes:
        path = _validate_vercel_artifact_key(
            artifact_key,
            prefix=self._prefix,
            expected_hostname=self._expected_hostname,
        )
        failure: Exception | None = None
        result: object | None = None
        try:
            result = await self._client.get(path, access="private", use_cache=True)
        except Exception as error:
            failure = error
        if failure is not None:
            if failure.__class__.__name__ == "BlobNotFoundError":
                raise GraphArtifactNotFound()
            raise GraphArtifactProviderError()
        if result is None or getattr(result, "status_code", None) != 200:
            raise GraphArtifactNotFound()
        content = getattr(result, "content", None)
        if not isinstance(content, bytes):
            raise GraphArtifactProviderError()
        if not self._result_matches_path(result=result, path=path):
            raise GraphArtifactProviderError()
        return content

    async def _reconcile_failed_put(self, *, path: str, sha256: str) -> str:
        for attempt in range(3):
            failure: Exception | None = None
            result: object | None = None
            try:
                result = await self._client.get(
                    path,
                    access="private",
                    use_cache=True,
                )
            except Exception as error:
                failure = error
            missing = (
                (
                    failure is not None
                    and failure.__class__.__name__ == "BlobNotFoundError"
                )
                or result is None
                or getattr(result, "status_code", None) != 200
            )
            if missing and attempt < 2:
                await asyncio.sleep(0)
                continue
            if failure is not None or missing:
                raise GraphArtifactProviderError()
            content = getattr(result, "content", None)
            if not isinstance(content, bytes) or not self._result_matches_path(
                result=result,
                path=path,
            ):
                raise GraphArtifactProviderError()
            if hmac.compare_digest(hashlib.sha256(content).hexdigest(), sha256):
                return result.url
            raise GraphArtifactConflict()
        raise GraphArtifactProviderError()

    def _result_matches_path(self, *, result: object, path: str) -> bool:
        url = getattr(result, "url", None)
        if not isinstance(url, str):
            return False
        try:
            returned_path = _validate_vercel_artifact_key(
                url,
                prefix=self._prefix,
                expected_hostname=self._expected_hostname,
            )
        except GraphArtifactError:
            return False
        return returned_path == path
