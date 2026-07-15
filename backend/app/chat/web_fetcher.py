import asyncio
import time
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from app.chat.web_discovery import canonicalize_url
from app.supply_chain.collector import SourceCollectionError, extract_official_text
from app.supply_chain.source_policy import (
    HostResolver,
    PinnedDnsTransport,
    PinningHostResolver,
    SourcePolicyError,
    SourceUrlPolicy,
    ValidatedSourceUrl,
)

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_SUPPORTED_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain"})


class WebFetchError(RuntimeError):
    code = "CHAT_WEB_FETCH_FAILED"

    def __init__(self) -> None:
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class FetchedWebPage:
    url: str
    title: str
    body_text: str
    published_at: datetime | None
    retrieved_at: datetime


class PinnedWebPageFetcher:
    def __init__(
        self,
        client: httpx.AsyncClient,
        resolver: PinningHostResolver,
        *,
        user_agent: str = "EquityLens research evidence collector",
        max_bytes: int = 1_500_000,
        max_model_chars: int = 40_000,
        max_decompression_ratio: float = 50.0,
        min_host_interval: float = 0.25,
        monotonic: Callable[[], float] | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._resolver = resolver
        self._user_agent = user_agent
        self._max_bytes = max_bytes
        self._max_model_chars = max_model_chars
        self._max_decompression_ratio = max_decompression_ratio
        self._min_host_interval = min_host_interval
        self._monotonic = monotonic or time.monotonic
        self._sleeper = sleeper
        self._now = now or (lambda: datetime.now(UTC))
        self._last_request: dict[str, float] = {}
        self._pace_lock = asyncio.Lock()

    @classmethod
    def create(
        cls,
        *,
        resolver: HostResolver | None = None,
        timeout_seconds: float = 15.0,
        user_agent: str = "EquityLens research evidence collector",
        max_bytes: int = 1_500_000,
        max_model_chars: int = 40_000,
        max_decompression_ratio: float = 50.0,
        min_host_interval: float = 0.25,
    ) -> "PinnedWebPageFetcher":
        pinning = PinningHostResolver(resolver)
        client = httpx.AsyncClient(
            transport=PinnedDnsTransport(pinning),
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(timeout_seconds),
        )
        return cls(
            client,
            pinning,
            user_agent=user_agent,
            max_bytes=max_bytes,
            max_model_chars=max_model_chars,
            max_decompression_ratio=max_decompression_ratio,
            min_host_interval=min_host_interval,
        )

    async def fetch(self, url: str) -> FetchedWebPage:
        try:
            policy, current = await self._authorize_initial(url)
            for redirect_count in range(4):
                result = await self._request(current)
                if isinstance(result, FetchedWebPage):
                    return result
                current = await policy.authorize_redirect(
                    current=current,
                    location=result,
                    redirect_count=redirect_count + 1,
                    resolver=self._resolver,
                )
        except WebFetchError:
            raise
        except (httpx.HTTPError, SourceCollectionError, SourcePolicyError):
            raise WebFetchError() from None
        raise WebFetchError()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _authorize_initial(
        self,
        url: str,
    ) -> tuple[SourceUrlPolicy, ValidatedSourceUrl]:
        canonical = canonicalize_url(url)
        if canonical is None:
            raise WebFetchError()
        hostname = urlsplit(canonical).hostname
        if hostname is None:
            raise WebFetchError()
        initial_policy = SourceUrlPolicy(issuer_hosts=(hostname,))
        initial = initial_policy.validate_url(canonical)
        allowed_hosts = tuple(
            dict.fromkeys(
                (
                    hostname,
                    initial.registrable_domain,
                    f"www.{initial.registrable_domain}",
                )
            )
        )
        policy = SourceUrlPolicy(issuer_hosts=allowed_hosts)
        return policy, await policy.authorize(canonical, self._resolver)

    async def _request(self, source: ValidatedSourceUrl) -> FetchedWebPage | str:
        await self._pace(source.hostname)
        async with self._client.stream(
            "GET",
            source.normalized_url,
            headers={"User-Agent": self._user_agent, "Accept": "text/html,text/plain"},
            follow_redirects=False,
        ) as response:
            if response.status_code in _REDIRECT_STATUSES:
                location = response.headers.get("location")
                if not location:
                    raise WebFetchError()
                return location
            if response.status_code == 429 or response.status_code >= 500:
                raise WebFetchError()
            if response.status_code >= 400:
                raise WebFetchError()
            content_type = _content_type(response.headers.get("content-type"))
            body = await _bounded_body(
                response,
                self._max_bytes,
                max_decompression_ratio=self._max_decompression_ratio,
            )
            text = extract_official_text(body, content_type=content_type)
            if not text.strip():
                raise WebFetchError()
            title = _extract_title(body, content_type, source.hostname)
            return FetchedWebPage(
                url=source.normalized_url,
                title=title,
                body_text=text[: self._max_model_chars],
                published_at=_published_at(response.headers),
                retrieved_at=self._now(),
            )

    async def _pace(self, hostname: str) -> None:
        async with self._pace_lock:
            now = self._monotonic()
            previous = self._last_request.get(hostname)
            if previous is not None:
                delay = self._min_host_interval - (now - previous)
                if delay > 0:
                    await self._sleeper(delay)
            self._last_request[hostname] = self._monotonic()


async def _bounded_body(
    response: httpx.Response,
    limit: int,
    *,
    max_decompression_ratio: float,
) -> bytes:
    chunks: list[bytes] = []
    size = 0
    if response.is_stream_consumed:
        chunks.append(response.content)
        size = len(response.content)
    else:
        async for chunk in response.aiter_raw():
            size += len(chunk)
            if size > limit:
                raise WebFetchError()
            chunks.append(chunk)
    if size > limit:
        raise WebFetchError()
    return _decode_body(
        b"".join(chunks),
        encoding=response.headers.get("content-encoding", ""),
        limit=limit,
        max_ratio=max_decompression_ratio,
    )


def _decode_body(
    body: bytes,
    *,
    encoding: str,
    limit: int,
    max_ratio: float,
) -> bytes:
    normalized = encoding.strip().casefold()
    if normalized in {"", "identity"}:
        return body
    if normalized not in {"gzip", "x-gzip", "deflate"}:
        raise WebFetchError()
    wrapper = (
        16 + zlib.MAX_WBITS if normalized in {"gzip", "x-gzip"} else zlib.MAX_WBITS
    )
    decoder = zlib.decompressobj(wrapper)
    ratio_limit = max(int(len(body) * max_ratio), 1)
    output_limit = min(limit, ratio_limit)
    try:
        decoded = decoder.decompress(body, output_limit + 1)
        if decoder.unconsumed_tail or len(decoded) > output_limit:
            raise WebFetchError()
        decoded += decoder.flush(output_limit + 1 - len(decoded))
    except zlib.error:
        raise WebFetchError() from None
    if len(decoded) > output_limit:
        raise WebFetchError()
    return decoded


def _content_type(value: str | None) -> str:
    normalized = (value or "").split(";", 1)[0].strip().casefold()
    if normalized not in _SUPPORTED_TYPES:
        raise WebFetchError()
    return normalized


def _extract_title(body: bytes, content_type: str, fallback: str) -> str:
    if content_type in {"text/html", "application/xhtml+xml"}:
        title = BeautifulSoup(body, "html.parser").title
        if title is not None:
            value = " ".join(title.get_text(" ", strip=True).split())
            if value:
                return value[:255]
    return fallback[:255]


def _published_at(headers: httpx.Headers) -> datetime | None:
    value = headers.get("last-modified") or headers.get("date")
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)
