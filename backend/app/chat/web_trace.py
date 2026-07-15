from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.chat.web_discovery import (
    SearchDiscovery,
    SourceClassifier,
    canonicalize_url,
    normalize_queries,
)

if TYPE_CHECKING:
    from app.chat.web_search import SelectedWebPage


@dataclass(frozen=True, slots=True)
class WebSearchTraceRecord:
    normalized_query: str
    search_decision: str
    search_reason: str
    candidate_results: list[dict[str, Any]]
    selected_result_ids: list[str]
    artifact_key: str | None
    artifact_sha256: str | None
    provider_request_id: str | None
    duration_ms: int
    tool_ordinal: int


def build_web_traces(
    discovery: SearchDiscovery,
    *,
    decision: str,
    pages: list[SelectedWebPage],
    classifier: SourceClassifier,
    official_hosts: tuple[str, ...],
    duration_ms: int,
) -> list[WebSearchTraceRecord]:
    selected = {page.result_id: page for page in pages}
    traces: list[WebSearchTraceRecord] = []
    for call in discovery.calls:
        candidate_results = [
            _candidate_metadata(item, selected, classifier, official_hosts)
            for item in call.candidates
        ]
        selected_pages = [
            selected[item.result_id]
            for item in call.candidates
            if item.result_id in selected
        ]
        queries = normalize_queries(call.queries) or ["web search"]
        trace_count = max(len(queries), len(selected_pages))
        for index in range(trace_count):
            query = queries[index % len(queries)]
            page = selected_pages[index] if index < len(selected_pages) else None
            traces.append(
                WebSearchTraceRecord(
                    normalized_query=query,
                    search_decision=decision,
                    search_reason=decision,
                    candidate_results=candidate_results,
                    selected_result_ids=[page.result_id for page in selected_pages],
                    artifact_key=page.artifact.artifact_key if page else None,
                    artifact_sha256=(
                        page.artifact.artifact_sha256 if page else None
                    ),
                    provider_request_id=discovery.provider_request_id,
                    duration_ms=duration_ms,
                    tool_ordinal=call.ordinal,
                )
            )
    return traces


def _candidate_metadata(
    candidate: Any,
    selected: dict[str, SelectedWebPage],
    classifier: SourceClassifier,
    official_hosts: tuple[str, ...],
) -> dict[str, Any]:
    page = selected.get(candidate.result_id)
    published_at = page.published_at.isoformat() if page and page.published_at else None
    return {
        "result_id": candidate.result_id,
        "url": canonicalize_url(candidate.url),
        "title": page.title if page else candidate.title,
        "published_at": published_at or candidate.published_at,
        "source_tier": classifier.classify(
            candidate.url,
            official_hosts=official_hosts,
        )
        or "rejected",
    }
