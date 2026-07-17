import asyncio
import gzip
import hashlib
import re
import time
import zlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from typing import Any
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.core.errors import DomainError
from app.providers.contracts import OfficialSourceDiscoveryProvider
from app.providers.sec import FilingContent, FilingReference
from app.supply_chain.artifacts import GraphArtifactError
from app.supply_chain.contracts import GraphArtifactStore
from app.supply_chain.schemas import (
    CompanyIdentity,
    OfficialSourceDocument,
    OfficialSourceMetadata,
    SourceType,
)
from app.supply_chain.source_policy import (
    SEC_HOSTS,
    HostResolver,
    SourcePolicyError,
    SourceUrlPolicy,
    ValidatedSourceUrl,
)

SUPPORTED_SOURCE_TYPES = frozenset(
    {"sec_filing", "annual_report", "ir_page", "official_press_release"}
)
HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
TEXT_TYPES = frozenset({"text/plain"})
PDF_TYPES = frozenset({"application/pdf"})
ROBOTS_LIMIT = 64 * 1024
MAX_DISCOVERY_ANCHORS = 512


class SourceCollectionError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class _CollectedResponse:
    status_code: int
    headers: httpx.Headers
    content: bytes


@dataclass(slots=True)
class _SourceByteBudget:
    remaining: int


class OfficialSourceCollectorImpl:
    def __init__(
        self,
        *,
        sec_provider: OfficialSourceDiscoveryProvider,
        client: httpx.AsyncClient,
        artifact_store: GraphArtifactStore,
        resolver: HostResolver,
        user_agent: str,
        source_limit: int,
        per_source_bytes: int,
        total_source_bytes: int,
        max_model_chars: int = 300_000,
        max_decompression_ratio: float = 40.0,
        min_host_interval: float = 0.0,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        pdf_text_extractor: Callable[[bytes], str] | None = None,
    ) -> None:
        if not 1 <= source_limit <= 24:
            raise SourceCollectionError("SOURCE_LIMIT_INVALID")
        if per_source_bytes < 1 or total_source_bytes < 1:
            raise SourceCollectionError("SOURCE_BYTE_LIMIT_INVALID")
        if max_model_chars < 20:
            raise SourceCollectionError("SOURCE_TEXT_LIMIT_INVALID")
        if max_decompression_ratio < 1:
            raise SourceCollectionError("SOURCE_DECOMPRESSION_RATIO_INVALID")
        if min_host_interval < 0:
            raise SourceCollectionError("SOURCE_PACING_INVALID")
        self._sec_provider = sec_provider
        self._client = client
        self._artifact_store = artifact_store
        self._resolver = resolver
        self._user_agent = user_agent.strip()
        if not self._user_agent:
            raise SourceCollectionError("SOURCE_USER_AGENT_INVALID")
        self._source_limit = source_limit
        self._per_source_bytes = per_source_bytes
        self._total_source_bytes = total_source_bytes
        self._max_model_chars = max_model_chars
        self._max_decompression_ratio = max_decompression_ratio
        self._min_host_interval = min_host_interval
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._pdf_text_extractor = pdf_text_extractor

    async def prepare_catalog(
        self,
        *,
        company: CompanyIdentity,
    ) -> "PreparedOfficialSourceTools":
        failure = False
        submissions: dict[str, Any] = {}
        try:
            submissions = await self._sec_provider.get_submissions(company.cik)
        except Exception:
            failure = True
        if failure or not isinstance(submissions, dict):
            raise SourceCollectionError(
                "SOURCE_PROVIDER_UNAVAILABLE",
                retryable=True,
            )
        bootstrap_policy = SourceUrlPolicy(issuer_hosts=company.official_hosts)
        try:
            catalog, filings, discovery_ids = _build_catalog(
                company=company,
                submissions=submissions,
                policy=bootstrap_policy,
                limit=self._source_limit,
            )
        except (AttributeError, TypeError, ValueError):
            raise SourceCollectionError(
                "SOURCE_PROVIDER_INVALID",
                retryable=True,
            ) from None
        anchored_hosts = tuple(
            sorted(
                {
                    urlsplit(source.canonical_url).hostname
                    for source in catalog
                    if source.source_type != "sec_filing"
                    and urlsplit(source.canonical_url).hostname is not None
                }
            )
        )
        policy = SourceUrlPolicy(issuer_hosts=anchored_hosts)
        tools = PreparedOfficialSourceTools(
            company=company,
            catalog=catalog,
            filings=filings,
            discovery_ids=discovery_ids,
            sec_provider=self._sec_provider,
            client=self._client,
            artifact_store=self._artifact_store,
            resolver=self._resolver,
            policy=policy,
            user_agent=self._user_agent,
            source_limit=self._source_limit,
            per_source_bytes=self._per_source_bytes,
            total_source_bytes=self._total_source_bytes,
            max_model_chars=self._max_model_chars,
            max_decompression_ratio=self._max_decompression_ratio,
            min_host_interval=self._min_host_interval,
            monotonic=self._monotonic,
            sleeper=self._sleeper,
            pdf_text_extractor=self._pdf_text_extractor,
        )
        await tools.discover_issuer_documents()
        return tools


class PreparedOfficialSourceTools:
    def __init__(
        self,
        *,
        company: CompanyIdentity,
        catalog: list[OfficialSourceMetadata],
        filings: dict[str, FilingReference],
        discovery_ids: tuple[str, ...],
        sec_provider: OfficialSourceDiscoveryProvider,
        client: httpx.AsyncClient,
        artifact_store: GraphArtifactStore,
        resolver: HostResolver,
        policy: SourceUrlPolicy,
        user_agent: str,
        source_limit: int,
        per_source_bytes: int,
        total_source_bytes: int,
        max_model_chars: int,
        max_decompression_ratio: float,
        min_host_interval: float,
        monotonic: Callable[[], float],
        sleeper: Callable[[float], Awaitable[None]],
        pdf_text_extractor: Callable[[bytes], str] | None,
    ) -> None:
        self._company = company
        self._catalog = {source.source_id: source for source in catalog}
        self._filings = filings
        self._discovery_ids = discovery_ids
        self._sec_provider = sec_provider
        self._client = client
        self._artifact_store = artifact_store
        self._resolver = resolver
        self._policy = policy
        self._user_agent = user_agent
        self._per_source_bytes = per_source_bytes
        self._total_source_bytes = total_source_bytes
        self._max_model_chars = max_model_chars
        self._max_decompression_ratio = max_decompression_ratio
        self._min_host_interval = min_host_interval
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._pdf_text_extractor = pdf_text_extractor
        self._source_limit = source_limit
        self._fetched: dict[str, OfficialSourceDocument] = {}
        self._remaining_total = total_source_bytes
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last_request: dict[str, float] = {}
        self._pace_lock = asyncio.Lock()
        self._fetch_lock = asyncio.Lock()

    async def discover_issuer_documents(self) -> None:
        for source_id in self._discovery_ids:
            try:
                document = await self.fetch_official_source(source_id=source_id)
                if document.content_type not in HTML_TYPES:
                    continue
                compressed = await self._artifact_store.get(
                    artifact_key=document.artifact_key
                )
                body = await asyncio.to_thread(
                    _decompress_artifact,
                    compressed,
                    byte_limit=self._per_source_bytes,
                )
            except (GraphArtifactError, OSError, SourceCollectionError):
                continue
            discovered = await asyncio.to_thread(
                _discover_issuer_links,
                body,
                index=document,
                company=self._company,
                policy=self._policy,
                limit=self._source_limit,
            )
            existing_urls = {source.canonical_url for source in self._catalog.values()}
            for metadata in discovered:
                if metadata.canonical_url in existing_urls:
                    continue
                self._catalog[metadata.source_id] = metadata
                existing_urls.add(metadata.canonical_url)
        self._trim_catalog()

    def _trim_catalog(self) -> None:
        selected = _select_catalog_sources(
            tuple(self._catalog.values()),
            limit=self._source_limit,
            discovery_ids=self._discovery_ids,
        )
        self._catalog = {source.source_id: source for source in selected}
        self._filings = {
            source_id: filing
            for source_id, filing in self._filings.items()
            if source_id in self._catalog
        }

    async def list_official_sources(
        self,
        *,
        company: CompanyIdentity,
        query: str,
        source_types: tuple[SourceType, ...],
    ) -> list[OfficialSourceMetadata]:
        if (
            company.company_id != self._company.company_id
            or company.cik != self._company.cik
        ):
            raise SourceCollectionError("SOURCE_COMPANY_MISMATCH")
        requested_types = set(source_types)
        if not requested_types or not requested_types <= SUPPORTED_SOURCE_TYPES:
            raise SourceCollectionError("SOURCE_TYPE_UNSUPPORTED")
        terms = tuple(term.casefold() for term in re.findall(r"[A-Za-z0-9]+", query))

        def score(source: OfficialSourceMetadata) -> tuple[int, int, str]:
            haystack = (
                f"{source.title} {source.publisher} {source.source_type}".casefold()
            )
            matches = sum(term in haystack for term in terms)
            type_rank = {
                "sec_filing": 0,
                "annual_report": 1,
                "ir_page": 2,
                "official_press_release": 3,
            }[source.source_type]
            return (-matches, type_rank, source.source_id)

        selected = [
            source
            for source in self._catalog.values()
            if source.source_type in requested_types
        ]
        return sorted(selected, key=score)

    async def fetch_official_source(
        self,
        *,
        source_id: str,
    ) -> OfficialSourceDocument:
        async with self._fetch_lock:
            return await self._fetch_official_source(source_id)

    async def _fetch_official_source(
        self,
        source_id: str,
    ) -> OfficialSourceDocument:
        existing = self._fetched.get(source_id)
        if existing is not None:
            return existing
        metadata = self._catalog.get(source_id)
        if metadata is None:
            raise SourceCollectionError("SOURCE_NOT_IN_CATALOG")
        if self._remaining_total <= 0:
            raise SourceCollectionError("SOURCE_RUN_BYTE_BUDGET_EXCEEDED")
        budget = _SourceByteBudget(self._per_source_bytes)
        validated = await self._authorize(metadata.canonical_url)
        filing = self._filings.get(source_id)
        if filing is None:
            body, content_type = await self._download(
                validated,
                budget=budget,
            )
        else:
            body, content_type = await self._download_sec_filing(
                filing,
                expected=validated,
                budget=budget,
            )
        text = (
            await asyncio.to_thread(
                extract_official_text,
                body,
                content_type=content_type,
                pdf_text_extractor=self._pdf_text_extractor,
            )
        )[: self._max_model_chars]
        if len(text.strip()) < 20:
            raise SourceCollectionError("SOURCE_TEXT_EMPTY")
        digest, compressed, compressed_digest = await asyncio.to_thread(
            _prepare_artifact,
            body,
        )
        try:
            artifact_key = await self._artifact_store.put(
                object_key=f"sha256/{digest}.gz",
                body=compressed,
                content_type="application/gzip",
                sha256=compressed_digest,
            )
        except GraphArtifactError:
            raise SourceCollectionError(
                "SOURCE_ARTIFACT_UNAVAILABLE",
                retryable=True,
            ) from None
        document = OfficialSourceDocument(
            **metadata.model_dump(),
            content_hash=digest,
            artifact_key=artifact_key,
            content_type=content_type,
            body_text=text,
        )
        self._fetched[source_id] = document
        return document

    def selected_documents(
        self,
        source_ids: Sequence[str],
    ) -> list[OfficialSourceDocument]:
        documents: list[OfficialSourceDocument] = []
        for source_id in source_ids:
            document = self._fetched.get(source_id)
            if document is None:
                if source_id not in self._catalog:
                    raise SourceCollectionError("SOURCE_NOT_IN_CATALOG")
                raise SourceCollectionError("SOURCE_NOT_FETCHED")
            documents.append(document)
        return documents

    async def _authorize(self, url: str) -> ValidatedSourceUrl:
        try:
            return await self._policy.authorize(url, self._resolver)
        except SourcePolicyError as error:
            raise SourceCollectionError(error.code) from None

    async def _download(
        self,
        initial: ValidatedSourceUrl,
        *,
        budget: _SourceByteBudget,
    ) -> tuple[bytes, str]:
        _, response, _ = await self._request_with_redirects(
            initial,
            budget=budget,
            budget_code="SOURCE_BYTE_BUDGET_EXCEEDED",
            enforce_robots=True,
        )
        _raise_for_status(response.status_code)
        content_type = _normalized_content_type(response.headers.get("content-type"))
        decoded_limit = len(response.content) + min(
            budget.remaining,
            self._remaining_total,
        )
        body = await asyncio.to_thread(
            _decode_http_content,
            response.content,
            content_encoding=response.headers.get("content-encoding", ""),
            byte_limit=decoded_limit,
            max_ratio=self._max_decompression_ratio,
        )
        self._consume_bytes(
            budget,
            max(0, len(body) - len(response.content)),
            budget_code="SOURCE_BYTE_BUDGET_EXCEEDED",
        )
        return body, content_type

    async def _download_sec_filing(
        self,
        filing: FilingReference,
        *,
        expected: ValidatedSourceUrl,
        budget: _SourceByteBudget,
    ) -> tuple[bytes, str]:
        max_bytes = min(budget.remaining, self._remaining_total)
        global_limit = self._remaining_total <= budget.remaining
        await self._pace(expected.hostname)
        try:
            content = await self._sec_provider.download_official_filing(
                filing,
                max_bytes=max_bytes,
            )
        except Exception as error:
            if isinstance(error, DomainError) and error.code == "FILING_TOO_LARGE":
                self._consume_bytes(
                    budget,
                    max_bytes,
                    budget_code="SOURCE_BYTE_BUDGET_EXCEEDED",
                )
                code = (
                    "SOURCE_RUN_BYTE_BUDGET_EXCEEDED"
                    if global_limit
                    else "SOURCE_BYTE_BUDGET_EXCEEDED"
                )
                raise SourceCollectionError(code) from None
            retryable = isinstance(error, DomainError) and (
                error.status_code >= 500 or bool((error.details or {}).get("retryable"))
            )
            raise SourceCollectionError(
                "SOURCE_FETCH_UNAVAILABLE",
                retryable=retryable,
            ) from None
        if not isinstance(content, FilingContent):
            raise SourceCollectionError(
                "SOURCE_PROVIDER_INVALID",
                retryable=True,
            )
        returned = await self._authorize(content.source_url)
        if (
            returned.hostname not in SEC_HOSTS
            or returned.normalized_url != expected.normalized_url
        ):
            raise SourceCollectionError("SOURCE_PROVIDER_INVALID", retryable=True)
        self._consume_bytes(
            budget,
            len(content.body),
            budget_code="SOURCE_BYTE_BUDGET_EXCEEDED",
        )
        return content.body, _normalized_content_type(content.content_type)

    async def _request_with_redirects(
        self,
        initial: ValidatedSourceUrl,
        *,
        budget: _SourceByteBudget,
        budget_code: str,
        enforce_robots: bool,
        request_limit: int | None = None,
    ) -> tuple[ValidatedSourceUrl, _CollectedResponse, int | None]:
        current = initial
        remaining_limit = request_limit
        for redirect_count in range(4):
            if enforce_robots and current.hostname not in SEC_HOSTS:
                await self._require_robots_allowed(current, budget)
            await self._pace(current.hostname)
            effective_limit = budget.remaining
            if remaining_limit is not None:
                effective_limit = min(effective_limit, remaining_limit)
            response = await self._request(
                current.normalized_url,
                budget=budget,
                request_limit=effective_limit,
                budget_code=budget_code,
            )
            if remaining_limit is not None:
                remaining_limit -= len(response.content)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if redirect_count >= 3 or location is None:
                    raise SourceCollectionError("SOURCE_REDIRECT_LIMIT")
                try:
                    current = await self._policy.authorize_redirect(
                        current=current,
                        location=location,
                        redirect_count=redirect_count + 1,
                        resolver=self._resolver,
                    )
                except SourcePolicyError as error:
                    raise SourceCollectionError(error.code) from None
                continue
            return current, response, remaining_limit
        raise SourceCollectionError("SOURCE_REDIRECT_LIMIT")

    async def _request(
        self,
        url: str,
        *,
        budget: _SourceByteBudget,
        request_limit: int,
        budget_code: str,
    ) -> _CollectedResponse:
        failure: Exception | None = None
        response: _CollectedResponse | None = None
        try:
            async with self._client.stream(
                "GET",
                url,
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "text/html,text/plain,application/pdf;q=0.9",
                },
                follow_redirects=False,
            ) as streamed:
                chunks: list[bytes] = []
                remaining_limit = request_limit
                if streamed.is_stream_consumed:
                    content = streamed.content
                    if len(content) > remaining_limit:
                        self._consume_bytes(
                            budget,
                            remaining_limit,
                            budget_code=budget_code,
                        )
                        raise SourceCollectionError(budget_code)
                    self._consume_bytes(
                        budget,
                        len(content),
                        budget_code=budget_code,
                    )
                    chunks.append(content)
                else:
                    async for chunk in streamed.aiter_raw():
                        if len(chunk) > remaining_limit:
                            self._consume_bytes(
                                budget,
                                remaining_limit,
                                budget_code=budget_code,
                            )
                            raise SourceCollectionError(budget_code)
                        self._consume_bytes(
                            budget,
                            len(chunk),
                            budget_code=budget_code,
                        )
                        remaining_limit -= len(chunk)
                        chunks.append(chunk)
                response = _CollectedResponse(
                    status_code=streamed.status_code,
                    headers=streamed.headers,
                    content=b"".join(chunks),
                )
        except SourceCollectionError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as error:
            failure = error
        if failure is not None or response is None:
            raise SourceCollectionError(
                "SOURCE_FETCH_UNAVAILABLE",
                retryable=True,
            )
        return response

    def _consume_bytes(
        self,
        budget: _SourceByteBudget,
        size: int,
        *,
        budget_code: str,
    ) -> None:
        if size <= 0:
            return
        if size > self._remaining_total:
            consumed = self._remaining_total
            self._remaining_total = 0
            budget.remaining = max(0, budget.remaining - consumed)
            raise SourceCollectionError("SOURCE_RUN_BYTE_BUDGET_EXCEEDED")
        if size > budget.remaining:
            self._remaining_total -= budget.remaining
            budget.remaining = 0
            raise SourceCollectionError(budget_code)
        self._remaining_total -= size
        budget.remaining -= size

    async def _require_robots_allowed(
        self,
        source: ValidatedSourceUrl,
        budget: _SourceByteBudget,
    ) -> None:
        rules = self._robots.get(source.hostname)
        if rules is None:
            robots_url = f"https://{source.hostname}/robots.txt"
            validated = await self._authorize(robots_url)
            _, response, remaining_limit = await self._request_with_redirects(
                validated,
                budget=budget,
                budget_code="SOURCE_ROBOTS_TOO_LARGE",
                enforce_robots=False,
                request_limit=ROBOTS_LIMIT,
            )
            if response.status_code == 404:
                lines: list[str] = []
            else:
                _raise_for_status(response.status_code)
                assert remaining_limit is not None
                decoded_limit = len(response.content) + min(
                    remaining_limit,
                    budget.remaining,
                    self._remaining_total,
                )
                robots_body = await asyncio.to_thread(
                    _decode_http_content,
                    response.content,
                    content_encoding=response.headers.get("content-encoding", ""),
                    byte_limit=decoded_limit,
                    max_ratio=self._max_decompression_ratio,
                )
                self._consume_bytes(
                    budget,
                    max(0, len(robots_body) - len(response.content)),
                    budget_code="SOURCE_ROBOTS_TOO_LARGE",
                )
                lines = robots_body.decode("utf-8", errors="replace").splitlines()
            rules = robotparser.RobotFileParser()
            rules.set_url(robots_url)
            rules.parse(lines)
            self._robots[source.hostname] = rules
        if not rules.can_fetch(self._user_agent, source.normalized_url):
            raise SourceCollectionError("SOURCE_ROBOTS_DISALLOWED")

    async def _pace(self, hostname: str) -> None:
        if self._min_host_interval == 0:
            return
        async with self._pace_lock:
            now = self._monotonic()
            previous = self._last_request.get(hostname)
            if previous is not None:
                delay = self._min_host_interval - (now - previous)
                if delay > 0:
                    await self._sleeper(delay)
                    now = self._monotonic()
            self._last_request[hostname] = now


def _build_catalog(
    *,
    company: CompanyIdentity,
    submissions: dict[str, Any],
    policy: SourceUrlPolicy,
    limit: int,
) -> tuple[
    list[OfficialSourceMetadata],
    dict[str, FilingReference],
    tuple[str, ...],
]:
    candidates: list[OfficialSourceMetadata] = []
    filings: dict[str, FilingReference] = {}
    discovery_ids: list[str] = []
    recent = submissions.get("filings", {}).get("recent", {})
    if isinstance(recent, dict):
        columns = (
            recent.get("accessionNumber", []),
            recent.get("filingDate", []),
            recent.get("reportDate", []),
            recent.get("form", []),
            recent.get("primaryDocument", []),
        )
        for accession, filing_date, report_date, form, primary_document in zip(
            *columns,
            strict=False,
        ):
            candidate = _filing_candidate(
                company=company,
                accession=str(accession),
                filing_date=str(filing_date),
                report_date=str(report_date),
                form=str(form),
                primary_document=str(primary_document),
            )
            if candidate is not None:
                metadata, filing = candidate
                candidates.append(metadata)
                filings[metadata.source_id] = filing
    issuer_values = (
        (submissions.get("website"), "Official website", False),
        (
            submissions.get("investorWebsite"),
            "Investor relations",
            True,
        ),
    )
    for url, title, discover in issuer_values:
        if not isinstance(url, str) or not url:
            continue
        try:
            canonical_url = policy.validate_url(url).normalized_url
        except SourcePolicyError:
            continue
        url_hash = hashlib.sha256(canonical_url.encode()).hexdigest()[:20]
        metadata = OfficialSourceMetadata(
            source_id=f"issuer:{url_hash}",
            source_key=f"issuer:{company.cik}:{url_hash}",
            source_type="ir_page",
            publisher=company.legal_name,
            title=f"{company.legal_name} {title}",
            canonical_url=canonical_url,
            published_at=None,
        )
        candidates.append(metadata)
        if discover:
            discovery_ids.append(metadata.source_id)
    unique: dict[str, OfficialSourceMetadata] = {}
    for candidate in candidates:
        unique.setdefault(candidate.canonical_url, candidate)
    selected = _select_catalog_sources(
        tuple(unique.values()),
        limit=limit,
        discovery_ids=tuple(discovery_ids),
    )
    return (
        selected,
        {
            source.source_id: filings[source.source_id]
            for source in selected
            if source.source_id in filings
        },
        tuple(
            source_id
            for source_id in discovery_ids
            if any(source.source_id == source_id for source in selected)
        ),
    )


def _discover_issuer_links(
    body: bytes,
    *,
    index: OfficialSourceDocument,
    company: CompanyIdentity,
    policy: SourceUrlPolicy,
    limit: int,
) -> list[OfficialSourceMetadata]:
    soup = BeautifulSoup(body, "html.parser")
    discovered: dict[str, OfficialSourceMetadata] = {}
    for anchor in soup.find_all("a", href=True, limit=MAX_DISCOVERY_ANCHORS):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        try:
            target = policy.validate_url(
                urljoin(index.canonical_url, href)
            ).normalized_url
        except SourcePolicyError:
            continue
        if target == index.canonical_url:
            continue
        title = " ".join(anchor.get_text(" ", strip=True).split())
        source_type = _classify_issuer_link(target, title)
        if source_type is None:
            continue
        digest = hashlib.sha256(target.encode()).hexdigest()[:20]
        fallback_title = urlsplit(target).path.rstrip("/").rsplit("/", 1)[-1]
        metadata = OfficialSourceMetadata(
            source_id=f"issuer-doc:{digest}",
            source_key=f"issuer:{company.cik}:{digest}",
            source_type=source_type,
            publisher=company.legal_name,
            title=(title or fallback_title or "Official document")[:500],
            canonical_url=target,
            published_at=None,
        )
        discovered.setdefault(target, metadata)
        if len(discovered) >= limit:
            break
    return sorted(discovered.values(), key=lambda source: source.source_id)


def _select_catalog_sources(
    sources: Sequence[OfficialSourceMetadata],
    *,
    limit: int,
    discovery_ids: tuple[str, ...],
) -> list[OfficialSourceMetadata]:
    sec_sources = sorted(
        (source for source in sources if source.source_type == "sec_filing"),
        key=lambda source: (
            -(source.published_at.toordinal() if source.published_at else 0),
            source.source_id,
        ),
    )
    issuer_sources = sorted(
        (source for source in sources if source.source_type != "sec_filing"),
        key=lambda source: (
            source.source_id not in discovery_ids,
            source.source_type,
            source.source_id,
        ),
    )
    issuer_limit = min(len(issuer_sources), max(1, limit // 2))
    if sec_sources:
        issuer_limit = min(issuer_limit, max(0, limit - 1))
    selected = [
        *issuer_sources[:issuer_limit],
        *sec_sources[: limit - issuer_limit],
    ]
    if len(selected) < limit:
        remaining = limit - len(selected)
        selected.extend(issuer_sources[issuer_limit : issuer_limit + remaining])
    return selected


def _prepare_artifact(body: bytes) -> tuple[str, bytes, str]:
    digest = hashlib.sha256(body).hexdigest()
    compressed = gzip.compress(body, compresslevel=6, mtime=0)
    return digest, compressed, hashlib.sha256(compressed).hexdigest()


def _decompress_artifact(content: bytes, *, byte_limit: int) -> bytes:
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        decoded = decoder.decompress(content, byte_limit + 1)
        if decoder.unconsumed_tail or len(decoded) > byte_limit:
            raise SourceCollectionError("SOURCE_ARTIFACT_TOO_LARGE")
        decoded += decoder.flush(byte_limit + 1 - len(decoded))
    except zlib.error:
        raise SourceCollectionError("SOURCE_ARTIFACT_INVALID") from None
    if len(decoded) > byte_limit or not decoder.eof:
        raise SourceCollectionError("SOURCE_ARTIFACT_TOO_LARGE")
    return decoded


def _classify_issuer_link(url: str, title: str) -> SourceType | None:
    haystack = f"{url} {title}".casefold()
    if urlsplit(url).path.casefold().endswith(".pdf") or "annual report" in haystack:
        return "annual_report"
    if any(marker in haystack for marker in ("newsroom", "press", "release", "news/")):
        return "official_press_release"
    if any(
        marker in haystack
        for marker in (
            "investor",
            "financial-results",
            "earnings",
            "supplier",
            "supply-chain",
            "manufacturing",
        )
    ):
        return "ir_page"
    return None


def _filing_candidate(
    *,
    company: CompanyIdentity,
    accession: str,
    filing_date: str,
    report_date: str,
    form: str,
    primary_document: str,
) -> tuple[OfficialSourceMetadata, FilingReference] | None:
    compact_accession = re.sub(r"[^0-9]", "", accession)
    if not compact_accession or not primary_document or "/" in primary_document:
        return None
    try:
        published_at = date.fromisoformat(filing_date)
    except ValueError:
        return None
    cik_number = str(int(company.cik))
    url = (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_number}/{compact_accession}/{primary_document}"
    )
    normalized_form = form.strip().upper() or "FILING"
    metadata = OfficialSourceMetadata(
        source_id=f"sec:{compact_accession}:{primary_document}",
        source_key=f"sec:{company.cik}:{normalized_form.casefold()}:{compact_accession}",
        source_type="sec_filing",
        publisher="U.S. Securities and Exchange Commission",
        title=f"{company.legal_name} {normalized_form} filed {filing_date}",
        canonical_url=url,
        published_at=published_at,
    )
    return metadata, FilingReference(
        accession_number=accession,
        form=normalized_form,
        filed_at=datetime.combine(published_at, datetime.min.time(), tzinfo=UTC),
        report_date=report_date,
        primary_document=primary_document,
        source_url=url,
    )


def _raise_for_status(status_code: int) -> None:
    if status_code == 429 or status_code >= 500:
        raise SourceCollectionError("SOURCE_FETCH_UNAVAILABLE", retryable=True)
    if status_code >= 400:
        raise SourceCollectionError("SOURCE_FETCH_REJECTED")


def _normalized_content_type(value: str | None) -> str:
    content_type = (value or "").split(";", 1)[0].strip().casefold()
    if content_type not in HTML_TYPES | TEXT_TYPES | PDF_TYPES:
        raise SourceCollectionError("SOURCE_CONTENT_TYPE_UNSUPPORTED")
    return content_type


def _decode_http_content(
    content: bytes,
    *,
    content_encoding: str,
    byte_limit: int,
    max_ratio: float,
) -> bytes:
    encoding = content_encoding.strip().casefold()
    if encoding in {"", "identity"}:
        return content
    if encoding not in {"gzip", "x-gzip", "deflate"}:
        raise SourceCollectionError("SOURCE_CONTENT_ENCODING_UNSUPPORTED")
    wrapper = 16 + zlib.MAX_WBITS if encoding in {"gzip", "x-gzip"} else zlib.MAX_WBITS
    decoder = zlib.decompressobj(wrapper)
    limit = min(byte_limit, max(int(len(content) * max_ratio), 1))
    try:
        decoded = decoder.decompress(content, limit + 1)
        if decoder.unconsumed_tail or len(decoded) > limit:
            raise SourceCollectionError("SOURCE_DECOMPRESSION_LIMIT")
        decoded += decoder.flush(limit + 1 - len(decoded))
    except zlib.error:
        raise SourceCollectionError("SOURCE_DECOMPRESSION_INVALID") from None
    if len(decoded) > limit:
        raise SourceCollectionError("SOURCE_DECOMPRESSION_LIMIT")
    return decoded


def extract_official_text(
    body: bytes,
    *,
    content_type: str,
    pdf_text_extractor: Callable[[bytes], str] | None = None,
) -> str:
    if content_type in TEXT_TYPES:
        return "\n".join(
            line.strip()
            for line in body.decode("utf-8", errors="replace").splitlines()
            if line.strip()
        )
    if content_type in PDF_TYPES:
        extractor = pdf_text_extractor or extract_pdf_text
        return extractor(body)
    if content_type not in HTML_TYPES:
        raise SourceCollectionError("SOURCE_CONTENT_TYPE_UNSUPPORTED")
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup.find_all(
        ["script", "style", "noscript", "nav", "svg", "template", "ix:hidden"]
    ):
        tag.decompose()
    block_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "tr", "li", "div"]
    lines: list[str] = []
    for element in soup.find_all([*block_tags, "a"]):
        if element.name == "div" and element.find(block_tags) is not None:
            continue
        if element.name == "a" and element.find_parent(block_tags) is not None:
            continue
        value = " ".join(element.get_text(" ", strip=True).split())
        if value and (not lines or value != lines[-1]):
            lines.append(value)
    if not lines:
        fallback = " ".join(soup.get_text(" ", strip=True).split())
        if fallback:
            lines.append(fallback)
    return "\n".join(lines)


def extract_pdf_text(body: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(body))
        return "\n".join(
            text
            for page in reader.pages
            if (text := (page.extract_text() or "").strip())
        )
    except Exception:
        raise SourceCollectionError("SOURCE_PDF_PARSE_FAILED") from None
