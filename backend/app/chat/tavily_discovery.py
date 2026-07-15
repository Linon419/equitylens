import hashlib
import json
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.chat.web_discovery import (
    SearchCall,
    SearchCandidate,
    SearchDiscovery,
    canonicalize_url,
    normalize_queries,
)

_DEFAULT_TAVILY_BASE_URL = "https://api.tavily.com"
_APPROVED_SEARCH_DOMAINS = (
    "sec.gov",
    "nasdaq.com",
    "nyse.com",
    "cboe.com",
    "reuters.com",
    "ft.com",
    "wsj.com",
    "bloomberg.com",
    "finance.yahoo.com",
)


class WebSearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_search: bool
    reason: str = Field(min_length=1, max_length=500)
    queries: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_queries(self) -> "WebSearchPlan":
        normalized = normalize_queries(self.queries, limit=3)
        if self.should_search and not normalized:
            raise ValueError("a search plan requires at least one query")
        if not self.should_search and normalized:
            raise ValueError("a skipped search plan must have no queries")
        self.queries = normalized
        return self


class TavilyWebSearchProvider:
    def __init__(
        self,
        planner: Any,
        client: httpx.AsyncClient,
        *,
        api_key: str | None,
        model_id: str,
        max_queries: int = 3,
        max_results: int = 5,
        search_depth: str = "basic",
        structured_output_method: str = "json_schema",
        base_url: str = _DEFAULT_TAVILY_BASE_URL,
    ) -> None:
        if max_queries < 1 or max_results < 1:
            raise ValueError("Tavily search limits must be positive")
        if search_depth not in {"basic", "advanced", "fast", "ultra-fast"}:
            raise ValueError("unsupported Tavily search depth")
        self._planner = planner
        self._client = client
        self._api_key = api_key.strip() if api_key else None
        self.model_id = model_id
        self._max_queries = min(max_queries, 3)
        self._max_results = min(max_results, 20)
        self._search_depth = search_depth
        self._structured_output_method = structured_output_method
        self._endpoint = f"{base_url.rstrip('/')}/search"

    async def search(
        self,
        *,
        question: str,
        company_name: str,
        symbol: str,
        internal_coverage: str,
        locale: str,
        official_hosts: tuple[str, ...] = (),
    ) -> SearchDiscovery:
        plan = await self._plan(
            question=question,
            company_name=company_name,
            symbol=symbol,
            internal_coverage=internal_coverage,
            locale=locale,
        )
        if not plan.should_search:
            return SearchDiscovery(None, [])

        calls: list[SearchCall] = []
        request_ids: list[str] = []
        for ordinal, query in enumerate(plan.queries[: self._max_queries]):
            payload = await self._search_tavily(
                query,
                official_hosts=official_hosts,
            )
            request_id = _optional_text(payload.get("request_id"))
            if request_id is not None:
                request_ids.append(request_id)
            calls.append(
                SearchCall(
                    ordinal=ordinal,
                    queries=[query],
                    candidates=_tavily_candidates(
                        payload.get("results"),
                        tool_ordinal=ordinal,
                    ),
                )
            )
        provider_request_id = ",".join(request_ids)[:255] or None
        return SearchDiscovery(provider_request_id, calls)

    async def _plan(self, **payload: str) -> WebSearchPlan:
        options: dict[str, Any] = {"method": self._structured_output_method}
        if self._structured_output_method != "json_mode":
            options["strict"] = True
        runnable = self._planner.with_structured_output(WebSearchPlan, **options)
        messages: list[tuple[str, str]] = [
            ("system", _planning_prompt(self._max_queries)),
            ("human", json.dumps(payload, ensure_ascii=False, separators=(",", ":"))),
        ]
        if self._structured_output_method == "json_mode":
            messages.insert(
                1,
                (
                    "system",
                    "Return only valid JSON matching this JSON Schema. Include every "
                    "required property and no additional properties.\nJSON Schema: "
                    + json.dumps(
                        WebSearchPlan.model_json_schema(),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                ),
            )
        result = await runnable.ainvoke(messages)
        return WebSearchPlan.model_validate(result)

    async def _search_tavily(
        self,
        query: str,
        *,
        official_hosts: tuple[str, ...],
    ) -> dict[str, Any]:
        headers = (
            {"Authorization": f"Bearer {self._api_key}"}
            if self._api_key
            else {"X-Tavily-Access-Mode": "keyless"}
        )
        response = await self._client.post(
            self._endpoint,
            headers=headers,
            json={
                "query": query,
                "search_depth": self._search_depth,
                "max_results": self._max_results,
                "topic": "finance",
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "include_domains": _search_domains(official_hosts),
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Tavily returned an invalid response")
        return payload


def _planning_prompt(max_queries: int) -> str:
    return (
        "You are the web-search router for a US-equity research Agent. Decide "
        "whether external web evidence materially improves the answer. Search "
        "for current facts, partial or insufficient internal coverage, industry "
        "context, competitors, customers, suppliers, and material developments. "
        "Skip search when complete internal evidence directly answers the question. "
        "When searching, produce concise English queries that include the company "
        "name or ticker and prefer regulators, investor relations, exchanges, and "
        f"trusted financial publications. Return at most {max_queries} queries."
    )


def _tavily_candidates(
    values: Any,
    *,
    tool_ordinal: int,
) -> list[SearchCandidate]:
    if not isinstance(values, list):
        return []
    candidates: list[SearchCandidate] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        canonical = canonicalize_url(value.get("url", ""))
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        candidates.append(
            SearchCandidate(
                result_id=hashlib.sha256(canonical.encode()).hexdigest()[:24],
                url=canonical,
                tool_ordinal=tool_ordinal,
                title=_optional_text(value.get("title")),
                published_at=_optional_text(value.get("published_date")),
            )
        )
    return candidates


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()[:500]
    return normalized or None


def _search_domains(official_hosts: tuple[str, ...]) -> list[str]:
    domains = [*_APPROVED_SEARCH_DOMAINS, *official_hosts]
    return list(dict.fromkeys(domain.casefold().strip(".") for domain in domains))
