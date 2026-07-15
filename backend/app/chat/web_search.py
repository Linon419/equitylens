import html
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.chat.artifacts import StoredWebArtifact, WebArtifactPage
from app.chat.contracts import WebArtifactWriter, WebPageFetcher, WebSearchProvider
from app.chat.web_discovery import (
    OpenAIWebSearchProvider,
    SearchCall,
    SearchCandidate,
    SearchDiscovery,
    SourceClassifier,
    SourceTier,
    canonicalize_url,
    normalize_queries,
)
from app.chat.web_fetcher import FetchedWebPage, PinnedWebPageFetcher
from app.chat.web_trace import WebSearchTraceRecord, build_web_traces
from app.core.errors import DomainError

__all__ = [
    "BoundedWebSearchService",
    "FetchedWebPage",
    "OpenAIWebSearchProvider",
    "PinnedWebPageFetcher",
    "SearchCall",
    "SearchCandidate",
    "SearchDiscovery",
    "SourceClassifier",
    "WebSearchRequest",
]

SearchDecision = Literal[
    "required_current",
    "required_low_evidence",
    "agent_requested",
    "not_needed",
    "optional_failed",
]


@dataclass(frozen=True, slots=True)
class WebSearchRequest:
    question: str
    company_name: str
    symbol: str
    locale: str
    internal_coverage: str
    official_hosts: tuple[str, ...]
    principal_scope: str
    conversation_id: UUID
    message_id: UUID


@dataclass(frozen=True, slots=True)
class SelectedWebPage:
    result_id: str
    url: str
    title: str
    body_text: str
    source_tier: SourceTier
    published_at: datetime | None
    retrieved_at: datetime
    artifact: StoredWebArtifact

    def prompt_block(self) -> str:
        safe_body = html.escape(self.body_text, quote=False)
        return (
            "<untrusted_web_evidence>\n"
            f"source_id: {html.escape(self.result_id)}\n{safe_body}\n"
            "</untrusted_web_evidence>"
        )


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    decision: SearchDecision
    queries: list[str] = field(default_factory=list)
    selected_pages: list[SelectedWebPage] = field(default_factory=list)
    traces: list[WebSearchTraceRecord] = field(default_factory=list)
    evidence_gap: str | None = None


class BoundedWebSearchService:
    def __init__(
        self,
        provider: WebSearchProvider,
        fetcher: WebPageFetcher,
        archive: WebArtifactWriter,
        *,
        classifier: SourceClassifier | None = None,
        max_queries: int = 3,
        max_pages: int = 8,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider = provider
        self._fetcher = fetcher
        self._archive = archive
        self._classifier = classifier or SourceClassifier()
        self._max_queries = max_queries
        self._max_pages = max_pages
        self._monotonic = monotonic

    async def search(self, request: WebSearchRequest) -> WebSearchResult:
        initial_decision = _search_decision(request)
        started = self._monotonic()
        try:
            discovery = await self._provider.search(
                question=request.question,
                company_name=request.company_name,
                symbol=request.symbol,
                internal_coverage=request.internal_coverage,
                locale=request.locale,
            )
        except Exception:
            return _handle_search_failure(initial_decision)
        queries = _discovery_queries(discovery, self._max_queries)
        candidates = _classified_candidates(
            discovery,
            classifier=self._classifier,
            official_hosts=request.official_hosts,
        )
        selected = sorted(candidates, key=_candidate_priority)[: self._max_pages]
        pages = await self._fetch_and_archive(selected, request)
        if not pages:
            return _handle_empty_result(initial_decision, discovery, queries)
        duration_ms = max(0, round((self._monotonic() - started) * 1000))
        decision = (
            initial_decision
            if initial_decision.startswith("required_")
            else "agent_requested"
        )
        traces = build_web_traces(
            discovery,
            decision=decision,
            pages=pages,
            classifier=self._classifier,
            official_hosts=request.official_hosts,
            duration_ms=duration_ms,
        )
        return WebSearchResult(decision, queries, pages, traces)

    async def _fetch_and_archive(
        self,
        candidates: list[tuple[SearchCandidate, SourceTier, str]],
        request: WebSearchRequest,
    ) -> list[SelectedWebPage]:
        pages: list[SelectedWebPage] = []
        for candidate, _tier, canonical_url in candidates:
            try:
                fetched = await self._fetcher.fetch(canonical_url)
                final_tier = self._classifier.classify(
                    fetched.url,
                    official_hosts=request.official_hosts,
                )
                if final_tier is None:
                    continue
                artifact_page = WebArtifactPage(
                    url=fetched.url,
                    title=fetched.title,
                    body_text=fetched.body_text,
                    source_tier=final_tier,
                    published_at=fetched.published_at,
                    retrieved_at=fetched.retrieved_at,
                )
                artifact = await self._archive.store(
                    principal_scope=request.principal_scope,
                    conversation_id=request.conversation_id,
                    message_id=request.message_id,
                    ordinal=len(pages),
                    page=artifact_page,
                )
            except Exception:
                continue
            pages.append(
                SelectedWebPage(
                    candidate.result_id,
                    fetched.url,
                    fetched.title,
                    fetched.body_text,
                    final_tier,
                    fetched.published_at,
                    fetched.retrieved_at,
                    artifact,
                )
            )
        return pages


def _search_decision(request: WebSearchRequest) -> SearchDecision:
    current_terms = re.compile(
        r"\b(today|latest|current|recent|now|breaking|update|newest)\b",
        re.IGNORECASE,
    )
    if current_terms.search(request.question) or any(
        term in request.question for term in ("今天", "最新", "当前", "近期", "刚刚")
    ):
        return "required_current"
    if request.internal_coverage in {"partial", "insufficient"}:
        return "required_low_evidence"
    return "agent_requested"


def _handle_search_failure(decision: SearchDecision) -> WebSearchResult:
    if decision.startswith("required_"):
        raise DomainError("CHAT_WEB_SEARCH_FAILED", 503, {"retryable": True})
    return WebSearchResult(
        decision="optional_failed",
        evidence_gap="CHAT_WEB_SEARCH_UNAVAILABLE",
    )


def _handle_empty_result(
    decision: SearchDecision,
    discovery: SearchDiscovery,
    queries: list[str],
) -> WebSearchResult:
    if decision.startswith("required_"):
        raise DomainError("CHAT_WEB_SEARCH_FAILED", 503, {"retryable": True})
    result_decision: SearchDecision = (
        "not_needed" if not discovery.calls else "optional_failed"
    )
    return WebSearchResult(
        decision=result_decision,
        queries=queries,
        evidence_gap=(
            None
            if result_decision == "not_needed"
            else "CHAT_WEB_SEARCH_UNAVAILABLE"
        ),
    )


def _discovery_queries(discovery: SearchDiscovery, limit: int) -> list[str]:
    flattened = [query for call in discovery.calls for query in call.queries]
    return normalize_queries(flattened, limit=limit)


def _classified_candidates(
    discovery: SearchDiscovery,
    *,
    classifier: SourceClassifier,
    official_hosts: tuple[str, ...],
) -> list[tuple[SearchCandidate, SourceTier, str]]:
    selected: list[tuple[SearchCandidate, SourceTier, str]] = []
    seen: set[str] = set()
    for call in discovery.calls:
        for candidate in call.candidates:
            canonical = canonicalize_url(candidate.url)
            tier = classifier.classify(
                candidate.url,
                official_hosts=official_hosts,
            )
            if canonical is None or tier is None or canonical in seen:
                continue
            seen.add(canonical)
            selected.append((candidate, tier, canonical))
    return selected


def _candidate_priority(
    value: tuple[SearchCandidate, SourceTier, str],
) -> tuple[int, int, str]:
    candidate, tier, canonical = value
    return (0 if tier == "primary" else 1, candidate.tool_ordinal, canonical)

