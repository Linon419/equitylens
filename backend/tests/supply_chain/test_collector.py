import asyncio
import gzip
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from app.api import deps
from app.core.errors import DomainError
from app.providers.contracts import OfficialSourceDiscoveryProvider
from app.providers.sec import FilingContent, FilingReference
from app.supply_chain.artifacts import (
    GraphArtifactProviderError,
    InMemoryGraphArtifactStore,
)
from app.supply_chain.collector import (
    OfficialSourceCollectorImpl,
    SourceCollectionError,
    extract_official_text,
)
from app.supply_chain.schemas import CompanyIdentity
from app.supply_chain.source_policy import PinnedDnsTransport, PinningHostResolver


@dataclass
class SubmissionsProvider:
    payload: dict[str, Any]
    error: Exception | None = None
    calls: int = 0
    client: httpx.AsyncClient | None = None
    download_calls: list[FilingReference] = field(default_factory=list)

    async def get_submissions(self, cik: str) -> dict[str, Any]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.payload

    async def download_official_filing(
        self,
        filing: FilingReference,
        *,
        max_bytes: int,
    ) -> FilingContent:
        self.download_calls.append(filing)
        if self.client is None:
            raise DomainError("SEC_DATA_UNAVAILABLE", 503, {"retryable": True})
        try:
            async with self.client.stream(
                "GET",
                filing.source_url,
                headers={"User-Agent": "EquityLens test admin@example.com"},
            ) as response:
                if response.status_code >= 300:
                    raise DomainError(
                        "SEC_DATA_UNAVAILABLE",
                        503,
                        {"retryable": True},
                    )
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise DomainError("FILING_TOO_LARGE", 413)
                    chunks.append(chunk)
        except httpx.HTTPError:
            raise DomainError(
                "SEC_DATA_UNAVAILABLE",
                503,
                {"retryable": True},
            ) from None
        return FilingContent(
            body=b"".join(chunks),
            content_type=response.headers.get("content-type", ""),
            source_url=str(response.url),
        )


class PublicResolver:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def resolve(self, hostname: str) -> tuple[str, ...]:
        self.calls.append(hostname)
        return ("93.184.216.34",)


def company(*hosts: str) -> CompanyIdentity:
    return CompanyIdentity(
        company_id=1,
        symbol="AAPL",
        cik="0000320193",
        legal_name="Apple Inc.",
        exchange="Nasdaq",
        official_hosts=hosts or ("apple.example.com",),
    )


def submissions(
    *,
    rows: int = 1,
    website: str | None = None,
    investor_website: str | None = None,
) -> dict[str, Any]:
    accessions = [f"0000320193-25-{index + 1:06d}" for index in range(rows)]
    payload: dict[str, Any] = {
        "cik": "0000320193",
        "name": "Apple Inc.",
        "filings": {
            "recent": {
                "accessionNumber": accessions,
                "filingDate": [f"2025-07-{index + 1:02d}" for index in range(rows)],
                "reportDate": ["2025-06-30"] * rows,
                "form": ["10-K" if index == 0 else "8-K" for index in range(rows)],
                "primaryDocument": [f"aapl-{index + 1}.htm" for index in range(rows)],
            }
        },
    }
    if website is not None:
        payload["website"] = website
    if investor_website is not None:
        payload["investorWebsite"] = investor_website
    return payload


def response_handler(
    bodies: dict[str, tuple[bytes, str]],
    *,
    seen: list[httpx.Request] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                headers={"content-type": "text/plain"},
                request=request,
            )
        body, content_type = bodies[str(request.url)]
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": content_type},
            request=request,
        )

    return handler


async def prepared_tools(
    *,
    payload: dict[str, Any],
    handler: Callable[[httpx.Request], httpx.Response],
    hosts: tuple[str, ...] = ("apple.example.com",),
    source_limit: int = 24,
    per_source_bytes: int = 100_000,
    total_source_bytes: int = 300_000,
    max_model_chars: int = 500_000,
    max_decompression_ratio: float = 40.0,
    min_host_interval: float = 0.0,
    monotonic: Callable[[], float] | None = None,
    sleeper: Callable[[float], Any] | None = None,
    pdf_text_extractor: Callable[[bytes], str] | None = None,
):
    store = InMemoryGraphArtifactStore()
    resolver = PublicResolver()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=1)
    provider = SubmissionsProvider(payload, client=client)
    collector_kwargs: dict[str, Any] = {}
    if monotonic is not None:
        collector_kwargs["monotonic"] = monotonic
    if sleeper is not None:
        collector_kwargs["sleeper"] = sleeper
    collector = OfficialSourceCollectorImpl(
        sec_provider=provider,
        client=client,
        artifact_store=store,
        resolver=resolver,
        user_agent="EquityLens test admin@example.com",
        source_limit=source_limit,
        per_source_bytes=per_source_bytes,
        total_source_bytes=total_source_bytes,
        max_model_chars=max_model_chars,
        max_decompression_ratio=max_decompression_ratio,
        min_host_interval=min_host_interval,
        pdf_text_extractor=pdf_text_extractor,
        **collector_kwargs,
    )
    tools = await collector.prepare_catalog(company=company(*hosts))
    return tools, client, store, resolver, provider


@pytest.mark.anyio
async def test_prepare_list_and_fetch_three_official_sources() -> None:
    payload = submissions(
        website="https://apple.example.com/investor/overview",
        investor_website="https://apple.example.com/newsroom/releases",
    )
    filing_url = (
        "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/aapl-1.htm"
    )
    bodies = {
        filing_url: (
            b"<html><body><h1>Supply Chain</h1><table><tr><th>Supplier</th>"
            b"<th>Part</th></tr><tr><td>TSMC</td><td>Chips</td></tr></table>"
            b"</body></html>",
            "text/html; charset=utf-8",
        ),
        "https://apple.example.com/investor/overview": (
            b"Investor relations supply chain overview for official evidence.",
            "text/plain",
        ),
        "https://apple.example.com/newsroom/releases": (
            b'<html><body><h2>Newsroom</h2><a href="/newsroom/supplier-update">'
            b"Official supplier press release</a></body></html>",
            "text/html",
        ),
        "https://apple.example.com/newsroom/supplier-update": (
            b"Official supplier manufacturing update with enough evidence.",
            "text/plain",
        ),
    }
    tools, client, store, _, provider = await prepared_tools(
        payload=payload,
        handler=response_handler(bodies),
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="supply chain",
            source_types=(
                "sec_filing",
                "ir_page",
                "official_press_release",
            ),
        )
        documents = [
            await tools.fetch_official_source(source_id=source.source_id)
            for source in listed
        ]

        assert provider.calls == 1
        assert len(provider.download_calls) == 1
        assert len(listed) == 4
        assert {source.source_type for source in listed} == {
            "sec_filing",
            "ir_page",
            "official_press_release",
        }
        assert all(len(document.content_hash) == 64 for document in documents)
        assert all(document.body_text for document in documents)
        for document in documents:
            stored = await store.get(artifact_key=document.artifact_key)
            assert document.artifact_key.endswith(f"sha256/{document.content_hash}.gz")
            assert gzip.decompress(stored) == bodies[document.canonical_url][0]
            assert hashlib.sha256(stored).hexdigest() != document.content_hash
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_catalog_deduplicates_canonical_urls_and_selection_is_deterministic() -> (
    None
):
    payload = submissions(rows=2)
    recent = payload["filings"]["recent"]
    recent["accessionNumber"][1] = recent["accessionNumber"][0]
    recent["primaryDocument"][1] = recent["primaryDocument"][0]
    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=response_handler({}),
    )
    try:
        first = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="form",
            source_types=("sec_filing",),
        )
        second = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="form",
            source_types=("sec_filing",),
        )

        assert len(first) == 1
        assert [item.source_id for item in first] == [item.source_id for item in second]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_catalog_keeps_the_most_recent_sec_filings_before_pruning() -> None:
    payload = submissions(rows=4)
    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=response_handler({}),
        source_limit=2,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )

        assert sorted(
            (source.published_at.isoformat() for source in listed),
            reverse=True,
        ) == [
            "2025-07-04",
            "2025-07-03",
        ]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_catalog_discovers_official_documents_from_sec_index() -> None:
    payload = submissions(
        investor_website="https://investor.apple.example.com/investor",
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                headers={"content-type": "text/plain"},
                request=request,
            )
        return httpx.Response(
            200,
            content=(
                b'<html><a href="/annual-report-2025.pdf">Annual Report 2025</a>'
                b'<a href="/newsroom/supplier-update">Supplier press release</a>'
                b'<a href="https://attacker.example/report">External report</a></html>'
            ),
            headers={"content-type": "text/html"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=handler,
        hosts=("apple.example.com",),
        source_limit=6,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="annual supplier",
            source_types=(
                "ir_page",
                "annual_report",
                "official_press_release",
            ),
        )
        by_url = {source.canonical_url: source.source_type for source in listed}

        assert by_url["https://investor.apple.example.com/investor"] == "ir_page"
        assert (
            by_url["https://investor.apple.example.com/annual-report-2025.pdf"]
            == "annual_report"
        )
        assert (
            by_url["https://investor.apple.example.com/newsroom/supplier-update"]
            == "official_press_release"
        )
        assert all("attacker.example" not in source.canonical_url for source in listed)
        assert len(listed) <= 6
        assert [request.url.path for request in seen] == [
            "/robots.txt",
            "/investor",
        ]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_per_source_budget_stops_stream_before_overflow() -> None:
    payload = submissions()
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/aapl-1.htm"
    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=response_handler({url: (b"x" * 101, "text/plain")}),
        per_source_bytes=100,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)

        assert error.value.code == "SOURCE_BYTE_BUDGET_EXCEEDED"
        assert error.value.retryable is False
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_total_run_budget_is_enforced_across_sources() -> None:
    payload = submissions(rows=2)
    urls = [
        "https://www.sec.gov/Archives/edgar/data/320193/"
        f"{accession.replace('-', '')}/{document}"
        for accession, document in zip(
            payload["filings"]["recent"]["accessionNumber"],
            payload["filings"]["recent"]["primaryDocument"],
            strict=True,
        )
    ]
    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=response_handler(
            {
                url: (b"official source body with enough text", "text/plain")
                for url in urls
            }
        ),
        total_source_bytes=60,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        await tools.fetch_official_source(source_id=listed[0].source_id)
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[1].source_id)

        assert error.value.code == "SOURCE_RUN_BYTE_BUDGET_EXCEEDED"
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_total_run_budget_stops_stream_at_remaining_bytes() -> None:
    payload = submissions(rows=2)
    urls = [
        "https://www.sec.gov/Archives/edgar/data/320193/"
        f"{accession.replace('-', '')}/{document}"
        for accession, document in zip(
            payload["filings"]["recent"]["accessionNumber"],
            payload["filings"]["recent"]["primaryDocument"],
            strict=True,
        )
    ]
    yielded_chunks: list[int] = []

    class RemainingBudgetStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for index in range(4):
                yielded_chunks.append(index)
                yield b"12345678"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == urls[0]:
            return httpx.Response(
                200,
                content=b"Official source body with enough text.",
                headers={"content-type": "text/plain"},
                request=request,
            )
        return httpx.Response(
            200,
            stream=RemainingBudgetStream(),
            headers={"content-type": "text/plain"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=handler,
        total_source_bytes=50,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        await tools.fetch_official_source(source_id=listed[0].source_id)
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[1].source_id)

        assert error.value.code == "SOURCE_RUN_BYTE_BUDGET_EXCEEDED"
        assert yielded_chunks == [0, 1]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_concurrent_fetches_share_one_total_byte_budget() -> None:
    payload = submissions(rows=2)

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(0)
            yield b"Official source body with forty bytes!!"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=SlowStream(),
            headers={"content-type": "text/plain"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=handler,
        total_source_bytes=60,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        results = await asyncio.gather(
            *(tools.fetch_official_source(source_id=item.source_id) for item in listed),
            return_exceptions=True,
        )

        documents = [item for item in results if not isinstance(item, Exception)]
        errors = [item for item in results if isinstance(item, SourceCollectionError)]
        assert len(documents) == 1
        assert [error.code for error in errors] == ["SOURCE_RUN_BYTE_BUDGET_EXCEEDED"]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_content_length_is_advisory_and_stream_limit_wins() -> None:
    payload = submissions()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"y" * 101,
            headers={"content-type": "text/plain", "content-length": "1"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=handler,
        per_source_bytes=100,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)

        assert error.value.code == "SOURCE_BYTE_BUDGET_EXCEEDED"
    finally:
        await client.aclose()


def test_source_limit_above_schema_bound_is_rejected() -> None:
    with pytest.raises(SourceCollectionError) as error:
        OfficialSourceCollectorImpl(
            sec_provider=SubmissionsProvider(submissions()),
            client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: None)),
            artifact_store=InMemoryGraphArtifactStore(),
            resolver=PublicResolver(),
            user_agent="EquityLens test admin@example.com",
            source_limit=25,
            per_source_bytes=100,
            total_source_bytes=100,
        )

    assert error.value.code == "SOURCE_LIMIT_INVALID"


def test_official_source_discovery_boundary_is_a_protocol() -> None:
    assert OfficialSourceDiscoveryProvider._is_protocol is True


@pytest.mark.anyio
async def test_dependency_wires_bounded_collector_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SubmissionsProvider(submissions())
    store = InMemoryGraphArtifactStore()
    monkeypatch.setattr(deps.settings, "SUPPLY_CHAIN_GRAPH_SOURCE_LIMIT", 12)
    monkeypatch.setattr(deps.settings, "SUPPLY_CHAIN_GRAPH_SOURCE_BYTES", 4096)
    monkeypatch.setattr(deps.settings, "MAX_FILING_BYTES", 2048)
    monkeypatch.setattr(
        deps.settings,
        "SEC_USER_AGENT",
        "EquityLens dependency admin@example.com",
    )

    def pdf_extractor(body: bytes) -> str:
        return "Configured PDF text"

    dependency = deps.get_official_source_collector(
        provider,
        store,
        pdf_extractor,
    )
    collector = await anext(dependency)
    try:
        assert isinstance(collector, OfficialSourceCollectorImpl)
        assert collector._sec_provider is provider
        assert collector._artifact_store is store
        assert collector._source_limit == 12
        assert collector._per_source_bytes == 2048
        assert collector._total_source_bytes == 4096
        assert collector._user_agent == "EquityLens dependency admin@example.com"
        assert collector._min_host_interval == 0.1
        assert collector._client.follow_redirects is False
        assert isinstance(collector._resolver, PinningHostResolver)
        assert isinstance(collector._client._transport, PinnedDnsTransport)
        assert collector._pdf_text_extractor is pdf_extractor
    finally:
        await dependency.aclose()

    assert collector._client.is_closed is True


@pytest.mark.anyio
async def test_unknown_and_unfetched_source_ids_are_safe_errors() -> None:
    tools, client, _, _, _ = await prepared_tools(
        payload=submissions(),
        handler=response_handler({}),
    )
    try:
        with pytest.raises(SourceCollectionError) as unknown:
            await tools.fetch_official_source(source_id="unknown")
        assert unknown.value.code == "SOURCE_NOT_IN_CATALOG"

        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        with pytest.raises(SourceCollectionError) as unfetched:
            tools.selected_documents([listed[0].source_id])
        assert unfetched.value.code == "SOURCE_NOT_FETCHED"
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_provider_error_maps_to_retryable_safe_code() -> None:
    provider = SubmissionsProvider(
        {},
        DomainError("SEC_DATA_UNAVAILABLE", 503, {"retryable": True}),
    )
    collector = OfficialSourceCollectorImpl(
        sec_provider=provider,
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: None)),
        artifact_store=InMemoryGraphArtifactStore(),
        resolver=PublicResolver(),
        user_agent="EquityLens test admin@example.com",
        source_limit=24,
        per_source_bytes=100,
        total_source_bytes=100,
    )
    try:
        with pytest.raises(SourceCollectionError) as error:
            await collector.prepare_catalog(company=company("apple.example.com"))
        assert error.value.code == "SOURCE_PROVIDER_UNAVAILABLE"
        assert error.value.retryable is True
        assert "SEC_DATA" not in str(error.value)
    finally:
        await collector._client.aclose()


@pytest.mark.anyio
async def test_malformed_provider_payload_maps_to_retryable_safe_code() -> None:
    collector = OfficialSourceCollectorImpl(
        sec_provider=SubmissionsProvider({"filings": []}),
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: None)),
        artifact_store=InMemoryGraphArtifactStore(),
        resolver=PublicResolver(),
        user_agent="EquityLens test admin@example.com",
        source_limit=24,
        per_source_bytes=100,
        total_source_bytes=100,
    )
    try:
        with pytest.raises(SourceCollectionError) as error:
            await collector.prepare_catalog(company=company("apple.example.com"))

        assert error.value.code == "SOURCE_PROVIDER_INVALID"
        assert error.value.retryable is True
        assert error.value.__cause__ is None
    finally:
        await collector._client.aclose()


@pytest.mark.anyio
async def test_rejects_unsupported_content_type() -> None:
    payload = submissions()
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/aapl-1.htm"
    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=response_handler({url: (b'{"fixture": true}', "application/json")}),
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)
        assert error.value.code == "SOURCE_CONTENT_TYPE_UNSUPPORTED"
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_rejects_compressed_response_bomb() -> None:
    payload = submissions(website="https://apple.example.com/investor/report")

    class CompressedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield gzip.compress(b"x" * 10_000)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                headers={"content-type": "text/plain"},
                request=request,
            )
        if request.url.path == "/newsroom/releases":
            return httpx.Response(
                200,
                content=(
                    b'<html><a href="/newsroom/supplier-update">'
                    b"Official supplier press release</a></html>"
                ),
                headers={"content-type": "text/html"},
                request=request,
            )
        return httpx.Response(
            200,
            stream=CompressedStream(),
            headers={
                "content-type": "text/plain",
                "content-encoding": "gzip",
            },
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=handler,
        per_source_bytes=20_000,
        max_decompression_ratio=2,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)
        assert error.value.code == "SOURCE_DECOMPRESSION_LIMIT"
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_timeout_maps_to_retryable_fetch_error() -> None:
    payload = submissions(website="https://apple.example.com/investor/report")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                headers={"content-type": "text/plain"},
                request=request,
            )
        raise httpx.ReadTimeout("fixture timeout", request=request)

    tools, client, _, _, _ = await prepared_tools(payload=payload, handler=handler)
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)
        assert error.value.code == "SOURCE_FETCH_UNAVAILABLE"
        assert error.value.retryable is True
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_issuer_robots_rules_are_enforced_and_cached() -> None:
    payload = submissions(
        website="https://apple.example.com/investor/overview",
        investor_website="https://apple.example.com/newsroom/releases",
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /investor\nAllow: /newsroom",
                headers={"content-type": "text/plain"},
                request=request,
            )
        if request.url.path == "/newsroom/releases":
            return httpx.Response(
                200,
                content=(
                    b'<html><a href="/newsroom/supplier-update">'
                    b"Official supplier press release</a></html>"
                ),
                headers={"content-type": "text/html"},
                request=request,
            )
        return httpx.Response(
            200,
            text="Official newsroom fixture content with enough text.",
            headers={"content-type": "text/plain"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(payload=payload, handler=handler)
    try:
        sources = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page", "official_press_release"),
        )
        investor_page = next(
            source
            for source in sources
            if source.canonical_url.endswith("/investor/overview")
        )
        press_release = next(
            source
            for source in sources
            if source.source_type == "official_press_release"
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=investor_page.source_id)
        assert error.value.code == "SOURCE_ROBOTS_DISALLOWED"
        await tools.fetch_official_source(source_id=press_release.source_id)
        assert [request.url.path for request in seen].count("/robots.txt") == 1
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_compressed_robots_rules_are_decoded_before_enforcement() -> None:
    payload = submissions(website="https://apple.example.com/investor/overview")
    seen: list[httpx.Request] = []

    class CompressedRobotsStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield gzip.compress(b"User-agent: *\nDisallow: /investor")

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                stream=CompressedRobotsStream(),
                headers={
                    "content-type": "text/plain",
                    "content-encoding": "gzip",
                },
                request=request,
            )
        return httpx.Response(
            200,
            text="Official issuer content with enough text.",
            headers={"content-type": "text/plain"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(payload=payload, handler=handler)
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)

        assert error.value.code == "SOURCE_ROBOTS_DISALLOWED"
        assert [request.url.path for request in seen] == ["/robots.txt"]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_requests_are_paced_per_host_and_send_sec_user_agent() -> None:
    payload = submissions(rows=2)
    urls = [
        "https://www.sec.gov/Archives/edgar/data/320193/"
        f"{accession.replace('-', '')}/{document}"
        for accession, document in zip(
            payload["filings"]["recent"]["accessionNumber"],
            payload["filings"]["recent"]["primaryDocument"],
            strict=True,
        )
    ]
    seen: list[httpx.Request] = []
    now = [0.0]
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=response_handler(
            {
                url: (b"Official SEC fixture body with enough text.", "text/plain")
                for url in urls
            },
            seen=seen,
        ),
        min_host_interval=1.0,
        monotonic=lambda: now[0],
        sleeper=sleep,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        for source in listed:
            await tools.fetch_official_source(source_id=source.source_id)
        assert sleeps == [1.0]
        assert all(
            request.headers["user-agent"] == "EquityLens test admin@example.com"
            for request in seen
        )
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_redirect_target_is_revalidated_before_second_request() -> None:
    payload = submissions(website="https://apple.example.com/investor/report")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                headers={"content-type": "text/plain"},
                request=request,
            )
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/admin"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(payload=payload, handler=handler)
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)
        assert error.value.code == "SOURCE_URL_SCHEME_UNSUPPORTED"
        assert [request.url.path for request in seen] == [
            "/robots.txt",
            "/investor/report",
        ]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_download_redirect_limit_is_three() -> None:
    payload = submissions(website="https://apple.example.com/investor/report")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                headers={"content-type": "text/plain"},
                request=request,
            )
        return httpx.Response(
            302,
            headers={"location": f"/redirect-{len(seen)}"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(payload=payload, handler=handler)
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)

        assert error.value.code == "SOURCE_REDIRECT_LIMIT"
        assert len(seen) == 5
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_redirect_bodies_share_the_run_byte_budget() -> None:
    payload = submissions(website="https://apple.example.com/investor/report")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                headers={"content-type": "text/plain"},
                request=request,
            )
        if request.url.path == "/investor/report":
            return httpx.Response(
                302,
                content=b"r" * 40,
                headers={"location": "/final"},
                request=request,
            )
        return httpx.Response(
            200,
            content=b"Official final source body text.",
            headers={"content-type": "text/plain"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=handler,
        total_source_bytes=80,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)

        assert error.value.code == "SOURCE_RUN_BYTE_BUDGET_EXCEEDED"
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_robots_redirect_target_is_revalidated_before_second_request() -> None:
    payload = submissions(website="https://apple.example.com/investor/overview")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/admin"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(payload=payload, handler=handler)
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)

        assert error.value.code == "SOURCE_URL_SCHEME_UNSUPPORTED"
        assert len(seen) == 1
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_issuer_redirect_target_rechecks_robots_before_request() -> None:
    payload = submissions(website="https://apple.example.com/public/report")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /public\nDisallow: /private",
                headers={"content-type": "text/plain"},
                request=request,
            )
        return httpx.Response(
            302,
            headers={"location": "/private/report"},
            request=request,
        )

    tools, client, _, _, _ = await prepared_tools(payload=payload, handler=handler)
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("ir_page",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)

        assert error.value.code == "SOURCE_ROBOTS_DISALLOWED"
        assert [request.url.path for request in seen] == [
            "/robots.txt",
            "/public/report",
        ]
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_artifact_failure_maps_to_retryable_safe_error() -> None:
    payload = submissions()
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/aapl-1.htm"
    secret = "artifact-provider-secret"

    class FailingArtifactStore:
        async def put(self, **kwargs: Any) -> str:
            raise GraphArtifactProviderError() from RuntimeError(secret)

        async def get(self, *, artifact_key: str) -> bytes:
            raise AssertionError("get should not be called")

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            response_handler(
                {url: (b"Official source body with enough text.", "text/plain")}
            )
        ),
        timeout=1,
    )
    provider = SubmissionsProvider(payload, client=client)
    collector = OfficialSourceCollectorImpl(
        sec_provider=provider,
        client=client,
        artifact_store=FailingArtifactStore(),
        resolver=PublicResolver(),
        user_agent="EquityLens test admin@example.com",
        source_limit=24,
        per_source_bytes=100_000,
        total_source_bytes=300_000,
    )
    try:
        tools = await collector.prepare_catalog(company=company("apple.example.com"))
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        with pytest.raises(SourceCollectionError) as error:
            await tools.fetch_official_source(source_id=listed[0].source_id)

        assert error.value.code == "SOURCE_ARTIFACT_UNAVAILABLE"
        assert error.value.retryable is True
        assert secret not in str(error.value)
        assert error.value.__cause__ is None
    finally:
        await client.aclose()


@pytest.mark.anyio
async def test_selected_documents_preserve_requested_order() -> None:
    payload = submissions(rows=2)
    urls = [
        "https://www.sec.gov/Archives/edgar/data/320193/"
        f"{accession.replace('-', '')}/{document}"
        for accession, document in zip(
            payload["filings"]["recent"]["accessionNumber"],
            payload["filings"]["recent"]["primaryDocument"],
            strict=True,
        )
    ]
    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=response_handler(
            {
                url: (b"Official source body with enough text.", "text/plain")
                for url in urls
            }
        ),
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        for source in listed:
            await tools.fetch_official_source(source_id=source.source_id)
        requested = [listed[1].source_id, listed[0].source_id]

        selected = tools.selected_documents(requested)

        assert [document.source_id for document in selected] == requested
    finally:
        await client.aclose()


def test_html_extraction_preserves_headings_and_table_rows() -> None:
    text = extract_official_text(
        b"<html><nav>Noise</nav><h1>Supply Chain</h1><table>"
        b"<tr><th>Supplier</th><th>Part</th></tr>"
        b"<tr><td>TSMC</td><td>Chips</td></tr></table></html>",
        content_type="text/html",
    )

    assert text.splitlines() == ["Supply Chain", "Supplier Part", "TSMC Chips"]
    assert "Noise" not in text


@pytest.mark.anyio
async def test_pdf_uses_injected_parser_and_model_text_is_capped() -> None:
    payload = submissions()
    url = "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/aapl-1.htm"
    tools, client, _, _, _ = await prepared_tools(
        payload=payload,
        handler=response_handler({url: (b"%PDF fixture", "application/pdf")}),
        pdf_text_extractor=lambda _: "Official PDF fixture text " * 10,
        max_model_chars=40,
    )
    try:
        listed = await tools.list_official_sources(
            company=company("apple.example.com"),
            query="",
            source_types=("sec_filing",),
        )
        document = await tools.fetch_official_source(source_id=listed[0].source_id)
        assert len(document.body_text) == 40
        assert document.body_text.startswith("Official PDF fixture")
    finally:
        await client.aclose()
