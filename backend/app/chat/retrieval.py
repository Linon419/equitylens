from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, literal_column
from sqlmodel import Session, select

from app.chat.contracts import (
    EmbeddingProvider,
    FilingChunkRepository,
    QueryRewriter,
)
from app.chat.schemas import QueryRewrite
from app.models.chat_model import FilingChunk
from app.models.research_model import Filing, FilingSection

_MAX_HISTORY_MESSAGES = 8
_MAX_CANDIDATES_PER_CHANNEL = 20
_FISCAL_PERIOD = re.compile(
    r"\b(?:Q[1-4]\s*(?:FY\s*)?|FY\s*)(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_CALENDAR_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_UPPERCASE_ENTITY = re.compile(r"\b[A-Z][A-Z0-9&.-]{1,15}\b")
_ENGLISH_CURRENT_INTENT_TERMS = (
    "current",
    "currently",
    "latest",
    "recent",
    "today",
    "now",
)
_CHINESE_CURRENT_INTENT_TERMS = (
    "当前",
    "目前",
    "最新",
    "今天",
    "近期",
)
_METRIC_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("gross margin", "毛利率"), "gross margin"),
    (("operating margin", "营业利润率"), "operating margin"),
    (("free cash flow", "自由现金流"), "free cash flow"),
    (("net income", "净利润"), "net income"),
    (("earnings per share", "每股收益"), "earnings per share"),
    (("revenue", "营收", "收入"), "revenue"),
    (("p/e", "pe ratio", "市盈率"), "P/E"),
)

QUERY_REWRITE_SYSTEM_PROMPT = """You rewrite a company research question for
filing retrieval.
Return a standalone English filing query and a localized display query.
Both queries must preserve the ticker, explicit fiscal periods, dates, metrics,
and selected entities. Set current_intent when the user asks for current or
recent information. Use only the supplied conversation data."""


@dataclass
class RewriteRequest:
    company_name: str
    symbol: str
    locale: Literal["en-US", "zh-CN"]
    question: str
    context_labels: list[str]
    history: list[str]
    summary: str | None = None

    def __post_init__(self) -> None:
        self.company_name = self.company_name.strip()
        self.symbol = self.symbol.strip().upper()
        self.question = self.question.strip()
        self.context_labels = _clean_values(self.context_labels)
        self.history = _clean_values(self.history)[-_MAX_HISTORY_MESSAGES:]
        if self.summary is not None:
            self.summary = self.summary.strip() or None
        if not self.company_name or not self.symbol or not self.question:
            raise ValueError("rewrite request identity and question are required")

    @property
    def required_terms(self) -> list[str]:
        return _required_terms(self)

    def as_prompt_payload(self) -> str:
        return json.dumps(
            {
                "company_name": self.company_name,
                "symbol": self.symbol,
                "locale": self.locale,
                "question": self.question,
                "context_labels": self.context_labels,
                "history": self.history,
                "summary": self.summary,
                "required_terms": self.required_terms,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


class OpenAIQueryRewriter:
    def __init__(
        self,
        model: Any,
        *,
        structured_output_method: str = "json_schema",
    ) -> None:
        self._model = model
        self._structured_output_method = structured_output_method

    async def rewrite(self, request: RewriteRequest) -> QueryRewrite:
        options: dict[str, Any] = {"method": self._structured_output_method}
        if self._structured_output_method != "json_mode":
            options["strict"] = True
        runnable = self._model.with_structured_output(
            QueryRewrite,
            **options,
        )
        messages = [
            ("system", QUERY_REWRITE_SYSTEM_PROMPT),
            ("human", request.as_prompt_payload()),
        ]
        if self._structured_output_method == "json_mode":
            messages.insert(
                1,
                (
                    "system",
                    "Return only valid JSON matching this JSON Schema. "
                    "Include every required property and no additional "
                    "properties.\nJSON Schema: "
                    + json.dumps(
                        QueryRewrite.model_json_schema(),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                ),
            )
        result = await runnable.ainvoke(messages)
        rewrite = QueryRewrite.model_validate(result)
        validate_query_rewrite(request, rewrite)
        return rewrite


def validate_query_rewrite(
    request: RewriteRequest,
    rewrite: QueryRewrite,
) -> None:
    filing_query = _searchable(rewrite.filing_query_en)
    display_query = _searchable(rewrite.display_query)
    required_filing_terms = [request.symbol, *request.required_terms]
    for term in required_filing_terms:
        if _searchable(term) not in filing_query:
            raise ValueError(f"query rewrite missing required term: {term}")
    if _searchable(request.symbol) not in display_query:
        raise ValueError(
            f"query rewrite missing required term: {request.symbol}"
        )
    for period in _extract_periods(request.question):
        if _searchable(period) not in display_query:
            raise ValueError(f"query rewrite missing required term: {period}")
    if _has_current_intent(request.question) and not rewrite.current_intent:
        raise ValueError("query rewrite must preserve current intent")


@dataclass(frozen=True)
class ChunkCandidate:
    id: UUID
    section_id: UUID
    text: str
    token_count: int
    source_anchor: str
    heading: str
    source_url: str
    filing_id: UUID | None = None
    channel_score: float | None = None


@dataclass(frozen=True)
class FusedChunk:
    chunk: ChunkCandidate
    score: float
    best_rank: int
    channels: frozenset[Literal["fts", "vector"]]


@dataclass(frozen=True)
class FilingRetrievalResult:
    rewrite: QueryRewrite
    chunks: list[ChunkCandidate]
    ranked_chunks: list[FusedChunk]


def reciprocal_rank_fusion(
    full_text: list[ChunkCandidate],
    vector: list[ChunkCandidate],
    *,
    k: int = 60,
) -> list[FusedChunk]:
    if k <= 0:
        raise ValueError("RRF k must be positive")
    candidates: dict[UUID, ChunkCandidate] = {}
    scores: defaultdict[UUID, float] = defaultdict(float)
    best_ranks: dict[UUID, int] = {}
    channels: defaultdict[
        UUID,
        set[Literal["fts", "vector"]],
    ] = defaultdict(set)
    for channel, ranked in (("fts", full_text), ("vector", vector)):
        seen: set[UUID] = set()
        for rank, chunk in enumerate(ranked, start=1):
            if chunk.id in seen:
                continue
            seen.add(chunk.id)
            candidates.setdefault(chunk.id, chunk)
            scores[chunk.id] += 1 / (k + rank)
            best_ranks[chunk.id] = min(best_ranks.get(chunk.id, rank), rank)
            channels[chunk.id].add(channel)
    fused = [
        FusedChunk(
            chunk=candidates[chunk_id],
            score=score,
            best_rank=best_ranks[chunk_id],
            channels=frozenset(channels[chunk_id]),
        )
        for chunk_id, score in scores.items()
    ]
    return sorted(
        fused,
        key=lambda item: (
            -item.score,
            item.best_rank,
            item.chunk.id.int,
        ),
    )


def select_chunks(
    ranked: list[FusedChunk],
    *,
    max_chunks: int,
    max_per_section: int,
    token_budget: int,
) -> list[FusedChunk]:
    if min(max_chunks, max_per_section, token_budget) <= 0:
        raise ValueError("retrieval selection limits must be positive")
    selected: list[FusedChunk] = []
    section_counts: defaultdict[UUID, int] = defaultdict(int)
    tokens = 0
    for item in ranked:
        if len(selected) >= max_chunks:
            break
        chunk = item.chunk
        if chunk.token_count <= 0:
            raise ValueError("filing chunk token count must be positive")
        if section_counts[chunk.section_id] >= max_per_section:
            continue
        if tokens + chunk.token_count > token_budget:
            continue
        selected.append(item)
        section_counts[chunk.section_id] += 1
        tokens += chunk.token_count
    return selected


class SqlFilingChunkRepository:
    def __init__(
        self,
        session: Session,
        *,
        embedding_dimensions: int = 1_536,
    ) -> None:
        self._session = session
        self._embedding_dimensions = embedding_dimensions

    def full_text_candidates(
        self,
        *,
        company_id: int,
        filing_id: UUID,
        query: str,
        limit: int,
    ) -> list[ChunkCandidate]:
        normalized_query = query.strip()
        _validate_candidate_request(company_id, normalized_query, limit)
        language = literal_column("'english'")
        document = func.to_tsvector(language, FilingChunk.text)
        search_query = func.plainto_tsquery(language, normalized_query)
        rank = func.ts_rank_cd(document, search_query)
        statement = (
            select(
                FilingChunk,
                FilingSection.heading,
                FilingSection.source_anchor,
                Filing.source_url,
                rank.label("channel_score"),
            )
            .join(FilingSection, FilingSection.id == FilingChunk.section_id)
            .join(Filing, Filing.id == FilingChunk.filing_id)
            .where(
                FilingChunk.company_id == company_id,
                FilingChunk.filing_id == filing_id,
                document.op("@@")(search_query),
            )
            .order_by(rank.desc(), FilingChunk.id)
            .limit(limit)
        )
        return [
            _candidate_from_row(row)
            for row in self._session.exec(statement).all()
        ]

    def vector_candidates(
        self,
        *,
        company_id: int,
        filing_id: UUID,
        embedding: list[float],
        limit: int,
    ) -> list[ChunkCandidate]:
        _validate_candidate_request(company_id, "vector", limit)
        _validate_embedding(embedding, self._embedding_dimensions)
        distance = FilingChunk.embedding.cosine_distance(embedding)
        similarity = (1 - distance).label("channel_score")
        statement = (
            select(
                FilingChunk,
                FilingSection.heading,
                FilingSection.source_anchor,
                Filing.source_url,
                similarity,
            )
            .join(FilingSection, FilingSection.id == FilingChunk.section_id)
            .join(Filing, Filing.id == FilingChunk.filing_id)
            .where(
                FilingChunk.company_id == company_id,
                FilingChunk.filing_id == filing_id,
            )
            .order_by(distance, FilingChunk.id)
            .limit(limit)
        )
        return [
            _candidate_from_row(row)
            for row in self._session.exec(statement).all()
        ]


class HybridFilingRetriever:
    def __init__(
        self,
        repository: FilingChunkRepository,
        embeddings: EmbeddingProvider,
        rewriter: QueryRewriter,
        *,
        candidate_limit: int = 20,
        max_chunks: int = 8,
        max_per_section: int = 3,
        token_budget: int = 6_000,
        rrf_k: int = 60,
    ) -> None:
        if candidate_limit > _MAX_CANDIDATES_PER_CHANNEL:
            raise ValueError("retrieval candidate limit cannot exceed 20")
        self._repository = repository
        self._embeddings = embeddings
        self._rewriter = rewriter
        self._candidate_limit = candidate_limit
        self._max_chunks = max_chunks
        self._max_per_section = max_per_section
        self._token_budget = token_budget
        self._rrf_k = rrf_k

    async def retrieve(
        self,
        request: RewriteRequest,
        *,
        company_id: int,
        filing_id: UUID,
    ) -> FilingRetrievalResult:
        rewrite = await self._rewriter.rewrite(request)
        validate_query_rewrite(request, rewrite)
        embedding = await self._embeddings.embed_query(
            rewrite.filing_query_en
        )
        _validate_embedding(embedding, self._embeddings.dimensions)
        full_text = self._repository.full_text_candidates(
            company_id=company_id,
            filing_id=filing_id,
            query=rewrite.filing_query_en,
            limit=self._candidate_limit,
        )
        vector = self._repository.vector_candidates(
            company_id=company_id,
            filing_id=filing_id,
            embedding=embedding,
            limit=self._candidate_limit,
        )
        fused = reciprocal_rank_fusion(full_text, vector, k=self._rrf_k)
        selected = select_chunks(
            fused,
            max_chunks=self._max_chunks,
            max_per_section=self._max_per_section,
            token_budget=self._token_budget,
        )
        return FilingRetrievalResult(
            rewrite=rewrite,
            chunks=[item.chunk for item in selected],
            ranked_chunks=selected,
        )


def _candidate_from_row(row: Any) -> ChunkCandidate:
    chunk, heading, source_anchor, source_url, score = row
    return ChunkCandidate(
        id=chunk.id,
        filing_id=chunk.filing_id,
        section_id=chunk.section_id,
        text=chunk.text,
        token_count=chunk.token_count,
        source_anchor=source_anchor,
        heading=heading,
        source_url=source_url,
        channel_score=float(score),
    )


def _validate_candidate_request(
    company_id: int,
    query: str,
    limit: int,
) -> None:
    if company_id <= 0 or not query:
        raise ValueError("company and retrieval query are required")
    if not 1 <= limit <= _MAX_CANDIDATES_PER_CHANNEL:
        raise ValueError("candidate limit must be between 1 and 20")


def _validate_embedding(embedding: list[float], dimensions: int) -> None:
    if len(embedding) != dimensions:
        raise ValueError("query embedding dimensions do not match provider")
    if any(not math.isfinite(value) for value in embedding):
        raise ValueError("query embedding values must be finite")


def _required_terms(request: RewriteRequest) -> list[str]:
    periods = _extract_periods(request.question)
    metrics = _extract_metrics(request.question, request.context_labels)
    entities = _extract_entities(request.question, request.symbol)
    return _deduplicate(
        [*periods, *metrics, *entities, *request.context_labels]
    )


def _extract_periods(question: str) -> list[str]:
    fiscal_matches = list(_FISCAL_PERIOD.finditer(question))
    terms = [re.sub(r"\s+", "", match.group()) for match in fiscal_matches]
    for match in _CALENDAR_YEAR.finditer(question):
        if any(
            fiscal.start() <= match.start() < fiscal.end()
            for fiscal in fiscal_matches
        ):
            continue
        terms.append(match.group())
    return _deduplicate(terms)


def _extract_metrics(question: str, context_labels: list[str]) -> list[str]:
    normalized_question = question.casefold()
    normalized_context = " ".join(context_labels).casefold()
    metrics: list[str] = []
    for aliases, canonical in _METRIC_ALIASES:
        if not any(alias.casefold() in normalized_question for alias in aliases):
            continue
        if any(alias.casefold() in normalized_context for alias in aliases):
            continue
        metrics.append(canonical)
    return metrics


def _extract_entities(question: str, symbol: str) -> list[str]:
    excluded = {symbol.casefold(), "eps", "pe"}
    return [
        match.group()
        for match in _UPPERCASE_ENTITY.finditer(question)
        if match.group().casefold() not in excluded
        and not _FISCAL_PERIOD.fullmatch(match.group())
    ]


def _has_current_intent(question: str) -> bool:
    normalized = question.casefold()
    return any(
        re.search(rf"\b{re.escape(term)}\b", normalized)
        for term in _ENGLISH_CURRENT_INTENT_TERMS
    ) or any(term in question for term in _CHINESE_CURRENT_INTENT_TERMS)


def _clean_values(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


def _deduplicate(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = _searchable(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _searchable(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()
