from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

import pytest

from app.chat.artifacts import StoredWebArtifact
from app.chat.evidence_pipeline import (
    CompanyResearchEvidencePipeline,
    DeterministicConversationSummarizer,
)
from app.chat.retrieval import ChunkCandidate, FilingRetrievalResult
from app.chat.schemas import (
    ApprovedEvidenceRecord,
    ChatReadiness,
    EvidenceCandidate,
    EvidenceGap,
    QueryRewrite,
    ReadinessResource,
    StructuredContextPack,
)
from app.chat.web_search import SelectedWebPage, WebSearchResult
from app.models.company_model import Company
from app.models.research_model import Filing
from app.quota.identity import RequestPrincipal

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)


@dataclass
class FakeStructuredRepository:
    filing: Filing

    def latest_filing(self, company_id: int) -> Filing:
        assert company_id == self.filing.company_id
        return self.filing

    def filing_is_indexed(self, filing_id) -> bool:
        return filing_id == self.filing.id


@dataclass
class FakeRetriever:
    chunk: ChunkCandidate
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def retrieve(self, request, **kwargs) -> FilingRetrievalResult:
        self.calls.append({"request": request, **kwargs})
        return FilingRetrievalResult(
            rewrite=QueryRewrite(
                filing_query_en="AAPL supply chain",
                display_query="AAPL supply chain",
                current_intent=False,
            ),
            chunks=[self.chunk],
            ranked_chunks=[],
        )


@dataclass
class FakeWebSearch:
    result: WebSearchResult
    calls: list[Any] = field(default_factory=list)

    async def search(self, request) -> WebSearchResult:
        self.calls.append(request)
        return self.result


@dataclass
class FakeMarketAnalysis:
    record: ApprovedEvidenceRecord
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def collect(self, **kwargs) -> list[ApprovedEvidenceRecord]:
        self.calls.append(kwargs)
        return [self.record]


def structured_pack() -> StructuredContextPack:
    ready = ReadinessResource(state="ready", action=None)
    candidate = EvidenceCandidate(
        evidence_id="graph:apple-tsmc",
        source_kind="graph",
        source_id="apple-tsmc",
        title="Apple supplier responsibility",
        source_url="https://www.apple.com/supplier-responsibility/",
        source_anchor="tsmc",
        excerpt="TSMC supplies advanced silicon manufacturing capacity used by Apple.",
        published_at=NOW,
        retrieved_at=NOW,
        source_tier="primary",
        verification="verified",
        attributes={},
    )
    return StructuredContextPack(
        items=[],
        evidence=[candidate],
        readiness=ChatReadiness(
            company_symbol="AAPL",
            intelligence=ready,
            filing_text=ready,
            filing_index=ready,
            supply_chain_graph=ready,
            web_recency=ReadinessResource(state="missing", action=None),
        ),
        gaps=[
            EvidenceGap(resource="market", code="MARKET_MISSING"),
            EvidenceGap(
                resource="supply_chain_graph",
                code="SUPPLY_CHAIN_GRAPH_MISSING",
                action="supply_chain_graph",
            ),
            EvidenceGap(resource="web_recency", code="WEB_RECENCY_MISSING"),
        ],
    )


@pytest.mark.asyncio
async def test_pipeline_combines_relevant_structured_filing_and_web_evidence() -> None:
    company = Company(
        id=1,
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
    )
    filing = Filing(
        company_id=1,
        accession_number="0000320193-25-000079",
        form="10-K",
        fiscal_period="FY2025",
        filed_at=date(2025, 10, 31),
        report_date=date(2025, 9, 27),
        primary_document="aapl-20250927.htm",
        source_url="https://www.sec.gov/aapl-20250927.htm",
        retrieved_at=NOW,
    )
    chunk = ChunkCandidate(
        id=uuid4(),
        filing_id=filing.id,
        section_id=uuid4(),
        text="Apple depends on manufacturing partners for key components.",
        token_count=10,
        source_anchor="item-1",
        heading="Item 1",
        source_url=filing.source_url,
    )
    page = SelectedWebPage(
        result_id="result-1",
        url="https://www.ftc.gov/news/example",
        title="FTC update",
        body_text="The FTC published a current technology competition update.",
        source_tier="primary",
        published_at=NOW,
        retrieved_at=NOW,
        artifact=StoredWebArtifact("chat-web/page.gz", "a" * 64, "b" * 64),
    )
    retriever = FakeRetriever(chunk)
    market_candidate = EvidenceCandidate(
        evidence_id="financial:yahoo:stock-liquidity:AAPL",
        source_kind="financial",
        source_id="stock-liquidity:AAPL",
        title="AAPL Yahoo market analysis · stock-liquidity",
        source_url="https://finance.yahoo.com/quote/AAPL",
        source_anchor="stock-liquidity",
        excerpt="AAPL average daily dollar volume was calculated from Yahoo data.",
        published_at=None,
        retrieved_at=NOW,
        source_tier="trusted_secondary",
        verification="supporting",
        attributes={},
    )
    market = FakeMarketAnalysis(
        ApprovedEvidenceRecord(
            company_id=1,
            candidate=market_candidate,
            source_text=market_candidate.excerpt,
        )
    )
    web = FakeWebSearch(
        WebSearchResult(
            decision="agent_requested",
            selected_pages=[page],
            traces=[],
        )
    )
    pipeline = CompanyResearchEvidencePipeline(
        FakeStructuredRepository(filing),
        retriever,
        web,
        market,
        now=lambda: NOW,
    )
    question = "How does Apple's supply chain affect its business?"

    internal = await pipeline.prepare_internal(
        company=company,
        structured_context=structured_pack(),
        question=question,
        context_labels=["TSMC"],
        history=["user: Earlier question"],
        summary="Earlier summary",
        locale="en-US",
        analysis_skills=["stock-liquidity"],
    )
    prepared = await pipeline.add_web(
        internal=internal,
        company=company,
        question=question,
        locale="en-US",
        principal=RequestPrincipal.guest("g" * 64, "i" * 64),
        conversation_id=uuid4(),
        assistant_message_id=uuid4(),
    )

    assert [record.candidate.source_kind for record in internal.records] == [
        "graph",
        "financial",
        "filing",
    ]
    assert internal.evidence_gaps == ["SUPPLY_CHAIN_GRAPH_MISSING"]
    assert retriever.calls[0]["request"].summary == "Earlier summary"
    assert market.calls[0]["skills"] == ["stock-liquidity"]
    assert web.calls[0].official_hosts == ("www.apple.com",)
    assert [record.candidate.source_kind for record in prepared.evidence.records] == [
        "graph",
        "financial",
        "filing",
        "web",
    ]
    assert (
        prepared.evidence.records[-1].candidate.attributes["artifact_sha256"]
        == "a" * 64
    )
    assert page.body_text.startswith(prepared.evidence.records[-1].candidate.excerpt)


@pytest.mark.asyncio
async def test_deterministic_summary_has_hard_character_bound() -> None:
    summarizer = DeterministicConversationSummarizer(max_chars=20)

    result = await summarizer.summarize(
        previous_summary="older summary",
        messages=["user: newest message"],
        locale="en-US",
    )

    assert len(result) <= 20
    assert result.endswith("newest message")
