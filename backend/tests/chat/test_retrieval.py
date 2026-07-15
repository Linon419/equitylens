from dataclasses import dataclass, field
from uuid import UUID

import pytest

from app.chat.retrieval import (
    ChunkCandidate,
    HybridFilingRetriever,
    OpenAIQueryRewriter,
    QueryRewrite,
    RewriteRequest,
    reciprocal_rank_fusion,
    select_chunks,
    validate_query_rewrite,
)


def candidate(
    value: int,
    *,
    section: int,
    tokens: int = 100,
) -> ChunkCandidate:
    return ChunkCandidate(
        id=UUID(int=value),
        section_id=UUID(int=section),
        text=f"chunk-{value}",
        token_count=tokens,
        source_anchor=f"item-{section}",
        heading=f"Section {section}",
        source_url="https://www.sec.gov/example",
    )


def test_rewrite_request_keeps_latest_eight_messages() -> None:
    request = RewriteRequest(
        company_name="Apple Inc.",
        symbol="AAPL",
        locale="zh-CN",
        question="2025 财年服务收入增长了吗？",
        context_labels=["Services revenue", "FY2025"],
        history=[f"message-{index}" for index in range(12)],
        summary="Earlier discussion about business segments.",
    )

    assert request.history == [f"message-{index}" for index in range(4, 12)]
    assert request.required_terms == ["2025", "Services revenue", "FY2025"]


def test_rewrite_validation_preserves_ticker_period_metric_and_entity() -> None:
    request = RewriteRequest(
        company_name="Apple Inc.",
        symbol="AAPL",
        locale="zh-CN",
        question="FY2025 的毛利率和 TSMC 依赖是什么？",
        context_labels=["gross margin", "TSMC"],
        history=[],
    )
    rewrite = QueryRewrite(
        filing_query_en="AAPL FY2025 gross margin dependency on TSMC",
        display_query="AAPL FY2025 毛利率与 TSMC 依赖",
        current_intent=False,
    )

    validate_query_rewrite(request, rewrite)

    with pytest.raises(ValueError, match="required term"):
        validate_query_rewrite(
            request,
            QueryRewrite(
                filing_query_en="Apple profitability",
                display_query="苹果盈利能力",
                current_intent=False,
            ),
        )


def test_rewrite_current_intent_uses_word_boundaries() -> None:
    request = RewriteRequest(
        company_name="Apple Inc.",
        symbol="AAPL",
        locale="en-US",
        question="What is Apple known for?",
        context_labels=[],
        history=[],
    )

    validate_query_rewrite(
        request,
        QueryRewrite(
            filing_query_en="AAPL core business",
            display_query="AAPL core business",
            current_intent=False,
        ),
    )


class FakeStructuredRunnable:
    def __init__(self) -> None:
        self.messages = []

    async def ainvoke(self, messages):
        self.messages.append(messages)
        return {
            "filing_query_en": "AAPL FY2025 revenue",
            "display_query": "AAPL FY2025 revenue",
            "current_intent": False,
        }


class FakeStructuredModel:
    def __init__(self) -> None:
        self.calls = []
        self.runnable = FakeStructuredRunnable()

    def with_structured_output(self, schema, **kwargs):
        self.calls.append((schema, kwargs))
        return self.runnable


@pytest.mark.asyncio
async def test_openai_rewriter_uses_strict_schema_and_validates_output() -> None:
    model = FakeStructuredModel()
    rewriter = OpenAIQueryRewriter(model)
    request = RewriteRequest(
        company_name="Apple Inc.",
        symbol="AAPL",
        locale="en-US",
        question="How did FY2025 revenue change?",
        context_labels=[],
        history=[f"message-{index}" for index in range(10)],
        summary="Earlier discussion.",
    )

    result = await rewriter.rewrite(request)

    assert result.filing_query_en == "AAPL FY2025 revenue"
    assert model.calls == [
        (
            QueryRewrite,
            {"method": "json_schema", "strict": True},
        )
    ]
    payload = model.runnable.messages[0][1][1]
    assert "message-0" not in payload
    assert "message-2" in payload
    assert "Earlier discussion." in payload


def test_rrf_is_stable_for_ties_and_combines_both_channels() -> None:
    a = candidate(1, section=1)
    b = candidate(2, section=1)
    c = candidate(3, section=2)
    d = candidate(4, section=3)

    ranked = reciprocal_rank_fusion([a, b, c], [b, a, d], k=60)

    assert [item.chunk.id for item in ranked] == [a.id, b.id, c.id, d.id]
    assert ranked[0].score == ranked[1].score
    assert ranked[0].best_rank == 1
    assert ranked[-1].channels == frozenset({"vector"})


def test_selection_enforces_section_diversity_count_and_token_budget() -> None:
    fts = [
        candidate(index, section=1 if index <= 5 else index, tokens=900)
        for index in range(1, 11)
    ]
    ranked = reciprocal_rank_fusion(fts, [], k=60)

    selected = select_chunks(
        ranked,
        max_chunks=8,
        max_per_section=3,
        token_budget=6_000,
    )

    assert len(selected) == 6
    assert sum(item.chunk.token_count for item in selected) <= 6_000
    assert sum(item.chunk.section_id == UUID(int=1) for item in selected) == 3


@dataclass
class FakeEmbeddingProvider:
    model_id: str = "text-embedding-3-small"
    dimensions: int = 3
    queries: list[str] = field(default_factory=list)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("retrieval embeds only the query")

    async def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2, 0.3]


@dataclass
class FakeRewriter:
    requests: list[RewriteRequest] = field(default_factory=list)

    async def rewrite(self, request: RewriteRequest) -> QueryRewrite:
        self.requests.append(request)
        return QueryRewrite(
            filing_query_en="AAPL FY2025 revenue",
            display_query="AAPL FY2025 revenue",
            current_intent=False,
        )


class RecordingChunkRepository:
    def __init__(self) -> None:
        self.fts_calls = []
        self.vector_calls = []

    def full_text_candidates(
        self,
        *,
        company_id,
        filing_id,
        query,
        limit,
    ):
        self.fts_calls.append((company_id, filing_id, query, limit))
        return [candidate(1, section=1), candidate(2, section=2)]

    def vector_candidates(
        self,
        *,
        company_id,
        filing_id,
        embedding,
        limit,
    ):
        self.vector_calls.append((company_id, filing_id, embedding, limit))
        return [candidate(2, section=2), candidate(3, section=3)]


@pytest.mark.asyncio
async def test_retriever_filters_company_filing_and_uses_locked_limits() -> None:
    repository = RecordingChunkRepository()
    embeddings = FakeEmbeddingProvider()
    rewriter = FakeRewriter()
    retriever = HybridFilingRetriever(repository, embeddings, rewriter)
    filing_id = UUID(int=99)
    request = RewriteRequest(
        company_name="Apple Inc.",
        symbol="AAPL",
        locale="en-US",
        question="How did FY2025 revenue change?",
        context_labels=[],
        history=[],
    )

    result = await retriever.retrieve(
        request,
        company_id=1,
        filing_id=filing_id,
    )

    assert repository.fts_calls == [(1, filing_id, "AAPL FY2025 revenue", 20)]
    assert repository.vector_calls == [
        (1, filing_id, [0.1, 0.2, 0.3], 20)
    ]
    assert embeddings.queries == ["AAPL FY2025 revenue"]
    assert [item.id for item in result.chunks] == [
        UUID(int=2),
        UUID(int=1),
        UUID(int=3),
    ]
    assert result.rewrite.display_query == "AAPL FY2025 revenue"
