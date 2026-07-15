import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

SourceTier = Literal["primary", "trusted_secondary"]


@dataclass(frozen=True, slots=True)
class SearchCandidate:
    result_id: str
    url: str
    tool_ordinal: int
    title: str | None = None
    published_at: str | None = None


@dataclass(frozen=True, slots=True)
class SearchCall:
    ordinal: int
    queries: list[str]
    candidates: list[SearchCandidate]


@dataclass(frozen=True, slots=True)
class SearchDiscovery:
    provider_request_id: str | None
    calls: list[SearchCall]


class OpenAIWebSearchProvider:
    def __init__(self, client: Any, *, model_id: str, max_queries: int = 3) -> None:
        self._client = client
        self.model_id = model_id
        self._max_queries = max_queries

    async def search(
        self,
        *,
        question: str,
        company_name: str,
        symbol: str,
        internal_coverage: str,
        locale: str,
    ) -> SearchDiscovery:
        response = await self._client.responses.create(
            model=self.model_id,
            input=_provider_prompt(
                question=question,
                company_name=company_name,
                symbol=symbol,
                internal_coverage=internal_coverage,
                locale=locale,
                max_queries=self._max_queries,
            ),
            tools=[{"type": "web_search"}],
            tool_choice="auto",
            max_tool_calls=self._max_queries,
            include=["web_search_call.action.sources"],
            store=False,
        )
        return _parse_discovery(response, max_queries=self._max_queries)


class SourceClassifier:
    def __init__(self, *, trusted_secondary_hosts: tuple[str, ...] = ()) -> None:
        self._trusted_secondary_hosts = tuple(
            _normalize_host(host) for host in trusted_secondary_hosts
        )

    def classify(
        self,
        url: str,
        *,
        official_hosts: tuple[str, ...] = (),
    ) -> SourceTier | None:
        canonical = canonicalize_url(url)
        if canonical is None:
            return None
        host = urlsplit(canonical).hostname or ""
        primary_hosts = (
            "sec.gov",
            "nasdaq.com",
            "nyse.com",
            "cboe.com",
            *(_normalize_host(value) for value in official_hosts),
        )
        if host.endswith(".gov") or any(
            _host_matches(host, allowed) for allowed in primary_hosts
        ):
            return "primary"
        if any(
            _host_matches(host, allowed)
            for allowed in self._trusted_secondary_hosts
        ):
            return "trusted_secondary"
        return None


def canonicalize_url(url: str) -> str | None:
    if not isinstance(url, str) or len(url) > 2_000 or "\\" in url:
        return None
    try:
        parsed = urlsplit(url)
        host = _normalize_host(parsed.hostname or "")
        port = parsed.port
    except (UnicodeError, ValueError):
        return None
    if (
        parsed.scheme.casefold() != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
        or any(character.isspace() or ord(character) < 32 for character in url)
    ):
        return None
    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def normalize_queries(values: list[Any], *, limit: int | None = None) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values[:limit]:
        query = _normalize_query(value)
        key = query.casefold()
        if query and key not in seen:
            seen.add(key)
            unique.append(query)
    return unique


def _parse_discovery(response: Any, *, max_queries: int) -> SearchDiscovery:
    remaining = max_queries
    calls: list[SearchCall] = []
    for tool_ordinal, item in enumerate(_read(response, "output", [])):
        if _read(item, "type") != "web_search_call":
            continue
        action = _read(item, "action")
        raw_queries = list(_read(action, "queries", []) or [])
        if not raw_queries and _read(action, "query"):
            raw_queries = [_read(action, "query")]
        queries = normalize_queries(raw_queries, limit=remaining)
        remaining -= min(len(raw_queries), remaining)
        candidates = _provider_candidates(
            _read(action, "sources", []) or [],
            tool_ordinal=tool_ordinal,
        )
        calls.append(SearchCall(tool_ordinal, queries, candidates))
        if remaining <= 0:
            break
    return SearchDiscovery(_read(response, "id"), calls)


def _provider_prompt(**values: Any) -> str:
    return (
        "Decide whether current external evidence is needed for this company "
        "research question. Use web search only when current, missing, or broader "
        "evidence is material. Prefer regulators, company investor relations, "
        "exchanges, and trusted publications. "
        f"Use at most {values['max_queries']} concise queries.\n"
        f"Company: {values['company_name']} ({values['symbol']})\n"
        f"Locale: {values['locale']}\n"
        f"Internal evidence coverage: {values['internal_coverage']}\n"
        f"Question: {values['question']}"
    )


def _provider_candidates(
    values: list[Any],
    *,
    tool_ordinal: int,
) -> list[SearchCandidate]:
    candidates: list[SearchCandidate] = []
    seen: set[str] = set()
    for value in values:
        canonical = canonicalize_url(_read(value, "url", ""))
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        result_id = hashlib.sha256(canonical.encode()).hexdigest()[:24]
        candidates.append(
            SearchCandidate(
                result_id,
                canonical,
                tool_ordinal,
                title=_optional_text(_read(value, "title")),
                published_at=_optional_text(_read(value, "published_at")),
            )
        )
    return candidates


def _read(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _normalize_query(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()[:500]


def _optional_text(value: Any) -> str | None:
    normalized = _normalize_query(value)
    return normalized or None


def _normalize_host(value: str) -> str:
    return value.strip().rstrip(".").encode("idna").decode("ascii").casefold()


def _host_matches(host: str, allowed: str) -> bool:
    return host == allowed or host.endswith(f".{allowed}")
