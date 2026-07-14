import asyncio
import gzip
import hashlib
import re
import time
import zlib
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Any
from urllib import robotparser

import httpx
from bs4 import BeautifulSoup

from app.providers.contracts import OfficialSourceDiscoveryProvider
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
        policy = SourceUrlPolicy(issuer_hosts=company.official_hosts)
        catalog = _build_catalog(
            company=company,
            submissions=submissions,
            policy=policy,
            limit=self._source_limit,
        )
        return PreparedOfficialSourceTools(
            company=company,
            catalog=catalog,
            client=self._client,
            artifact_store=self._artifact_store,
            resolver=self._resolver,
            policy=policy,
            user_agent=self._user_agent,
            per_source_bytes=self._per_source_bytes,
            total_source_bytes=self._total_source_bytes,
            max_model_chars=self._max_model_chars,
            max_decompression_ratio=self._max_decompression_ratio,
            min_host_interval=self._min_host_interval,
            monotonic=self._monotonic,
            sleeper=self._sleeper,
            pdf_text_extractor=self._pdf_text_extractor,
        )


class PreparedOfficialSourceTools:
    def __init__(
        self,
        *,
        company: CompanyIdentity,
        catalog: list[OfficialSourceMetadata],
        client: httpx.AsyncClient,
        artifact_store: GraphArtifactStore,
        resolver: HostResolver,
        policy: SourceUrlPolicy,
        user_agent: str,
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
        self._fetched: dict[str, OfficialSourceDocument] = {}
        self._total_bytes = 0
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._last_request: dict[str, float] = {}
        self._pace_lock = asyncio.Lock()

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
        existing = self._fetched.get(source_id)
        if existing is not None:
            return existing
        metadata = self._catalog.get(source_id)
        if metadata is None:
            raise SourceCollectionError("SOURCE_NOT_IN_CATALOG")
        validated = await self._authorize(metadata.canonical_url)
        if validated.hostname not in SEC_HOSTS:
            await self._require_robots_allowed(validated)
        remaining = self._total_source_bytes - self._total_bytes
        if remaining <= 0:
            raise SourceCollectionError("SOURCE_RUN_BYTE_BUDGET_EXCEEDED")
        byte_limit = min(self._per_source_bytes, remaining)
        budget_code = (
            "SOURCE_RUN_BYTE_BUDGET_EXCEEDED"
            if remaining < self._per_source_bytes
            else "SOURCE_BYTE_BUDGET_EXCEEDED"
        )
        body, content_type = await self._download(
            validated,
            byte_limit=byte_limit,
            budget_code=budget_code,
        )
        if len(body) > remaining:
            raise SourceCollectionError("SOURCE_RUN_BYTE_BUDGET_EXCEEDED")
        self._total_bytes += len(body)
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
        digest = hashlib.sha256(body).hexdigest()
        compressed = gzip.compress(body, compresslevel=6, mtime=0)
        try:
            artifact_key = await self._artifact_store.put(
                object_key=f"sha256/{digest}.gz",
                body=compressed,
                content_type="application/gzip",
                sha256=hashlib.sha256(compressed).hexdigest(),
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
        byte_limit: int,
        budget_code: str,
    ) -> tuple[bytes, str]:
        _, response = await self._request_with_redirects(
            initial,
            byte_limit=byte_limit,
            budget_code=budget_code,
        )
        _raise_for_status(response.status_code)
        content_type = _normalized_content_type(response.headers.get("content-type"))
        body = _decode_http_content(
            response.content,
            content_encoding=response.headers.get("content-encoding", ""),
            byte_limit=byte_limit,
            max_ratio=self._max_decompression_ratio,
        )
        return body, content_type

    async def _request_with_redirects(
        self,
        initial: ValidatedSourceUrl,
        *,
        byte_limit: int,
        budget_code: str,
    ) -> tuple[ValidatedSourceUrl, _CollectedResponse]:
        current = initial
        for redirect_count in range(4):
            await self._pace(current.hostname)
            response = await self._request(
                current.normalized_url,
                byte_limit,
                budget_code=budget_code,
            )
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
            return current, response
        raise SourceCollectionError("SOURCE_REDIRECT_LIMIT")

    async def _request(
        self,
        url: str,
        byte_limit: int,
        *,
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
                size = 0
                if streamed.is_stream_consumed:
                    chunks.append(streamed.content)
                    size = len(streamed.content)
                    if size > byte_limit:
                        raise SourceCollectionError(budget_code)
                else:
                    async for chunk in streamed.aiter_raw():
                        size += len(chunk)
                        if size > byte_limit:
                            raise SourceCollectionError(budget_code)
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

    async def _require_robots_allowed(self, source: ValidatedSourceUrl) -> None:
        rules = self._robots.get(source.hostname)
        if rules is None:
            robots_url = f"https://{source.hostname}/robots.txt"
            validated = await self._authorize(robots_url)
            _, response = await self._request_with_redirects(
                validated,
                byte_limit=ROBOTS_LIMIT,
                budget_code="SOURCE_ROBOTS_TOO_LARGE",
            )
            if response.status_code == 404:
                lines: list[str] = []
            else:
                _raise_for_status(response.status_code)
                lines = response.content.decode("utf-8", errors="replace").splitlines()
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
) -> list[OfficialSourceMetadata]:
    candidates: list[OfficialSourceMetadata] = []
    recent = submissions.get("filings", {}).get("recent", {})
    if isinstance(recent, dict):
        columns = (
            recent.get("accessionNumber", []),
            recent.get("filingDate", []),
            recent.get("form", []),
            recent.get("primaryDocument", []),
        )
        for accession, filing_date, form, primary_document in zip(
            *columns,
            strict=False,
        ):
            metadata = _filing_metadata(
                company=company,
                accession=str(accession),
                filing_date=str(filing_date),
                form=str(form),
                primary_document=str(primary_document),
            )
            if metadata is not None:
                candidates.append(metadata)
    issuer_values = (
        (submissions.get("website"), "ir_page", "Investor relations"),
        (
            submissions.get("investorWebsite"),
            "official_press_release",
            "Official newsroom",
        ),
    )
    for url, source_type, title in issuer_values:
        if not isinstance(url, str) or not url:
            continue
        try:
            canonical_url = policy.validate_url(url).normalized_url
        except SourcePolicyError:
            continue
        url_hash = hashlib.sha256(canonical_url.encode()).hexdigest()[:20]
        candidates.append(
            OfficialSourceMetadata(
                source_id=f"issuer:{url_hash}",
                source_key=f"issuer:{company.cik}:{url_hash}",
                source_type=source_type,
                publisher=company.legal_name,
                title=f"{company.legal_name} {title}",
                canonical_url=canonical_url,
                published_at=None,
            )
        )
    unique: dict[str, OfficialSourceMetadata] = {}
    for candidate in candidates:
        unique.setdefault(candidate.canonical_url, candidate)
    return sorted(unique.values(), key=lambda item: item.source_id)[:limit]


def _filing_metadata(
    *,
    company: CompanyIdentity,
    accession: str,
    filing_date: str,
    form: str,
    primary_document: str,
) -> OfficialSourceMetadata | None:
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
    return OfficialSourceMetadata(
        source_id=f"sec:{compact_accession}:{primary_document}",
        source_key=f"sec:{company.cik}:{normalized_form.casefold()}:{compact_accession}",
        source_type="sec_filing",
        publisher="U.S. Securities and Exchange Commission",
        title=f"{company.legal_name} {normalized_form} filed {filing_date}",
        canonical_url=url,
        published_at=published_at,
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
        extractor = pdf_text_extractor or _extract_pdf_text
        return extractor(body)
    if content_type not in HTML_TYPES:
        raise SourceCollectionError("SOURCE_CONTENT_TYPE_UNSUPPORTED")
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup.find_all(
        ["script", "style", "noscript", "nav", "svg", "template", "ix:hidden"]
    ):
        tag.decompose()
    lines: list[str] = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "tr", "li"]):
        value = " ".join(element.get_text(" ", strip=True).split())
        if value and (not lines or value != lines[-1]):
            lines.append(value)
    if not lines:
        fallback = " ".join(soup.get_text(" ", strip=True).split())
        if fallback:
            lines.append(fallback)
    return "\n".join(lines)


def _extract_pdf_text(body: bytes) -> str:
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
