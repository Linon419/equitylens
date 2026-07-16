import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from urllib.parse import urlsplit
from uuid import UUID

from loguru import logger

from app.chat.contracts import MarketAnalysisProvider
from app.chat.market_analysis_skills import MarketAnalysisSkill
from app.chat.retrieval import HybridFilingRetriever, RewriteRequest
from app.chat.schemas import (
    AnswerEvidencePack,
    ApprovedEvidenceRecord,
    EvidenceCandidate,
    StructuredContextPack,
)
from app.chat.service import PreparedAnswerEvidence
from app.chat.structured_repository import SqlStructuredContextRepository
from app.chat.web_search import (
    BoundedWebSearchService,
    SelectedWebPage,
    WebSearchRequest,
)
from app.models.company_model import Company
from app.models.research_model import Filing
from app.quota.identity import RequestPrincipal


@dataclass(frozen=True, slots=True)
class InternalEvidence:
    company: Company
    records: list[ApprovedEvidenceRecord]
    evidence_gaps: list[str]
    coverage: str


class CompanyResearchEvidencePipeline:
    def __init__(
        self,
        repository: SqlStructuredContextRepository,
        retriever: HybridFilingRetriever,
        web_search: BoundedWebSearchService,
        market_analysis: MarketAnalysisProvider | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._retriever = retriever
        self._web_search = web_search
        self._market_analysis = market_analysis
        self._now = now or (lambda: datetime.now(UTC))

    async def prepare_internal(
        self,
        *,
        company: Company,
        structured_context: StructuredContextPack,
        question: str,
        context_labels: list[str],
        history: list[str],
        summary: str | None,
        locale: str,
        analysis_skills: list[MarketAnalysisSkill] | None = None,
    ) -> InternalEvidence:
        if company.id is None:
            raise ValueError("persisted company required")
        records = [
            ApprovedEvidenceRecord(
                company_id=company.id,
                candidate=candidate,
                source_text=candidate.excerpt,
            )
            for candidate in structured_context.evidence
        ]
        market_gaps: list[str] = []
        selected_skills = analysis_skills or []
        if selected_skills and self._market_analysis is not None:
            try:
                async with asyncio.timeout(20):
                    market_records = await self._market_analysis.collect(
                        company=company,
                        question=question,
                        skills=selected_skills,
                    )
                records.extend(market_records)
                if len(market_records) < len(selected_skills):
                    market_gaps.append("MARKET_ANALYSIS_DATA_PARTIAL")
            except Exception:
                logger.warning(
                    "Market-analysis evidence unavailable for {}",
                    company.symbol,
                )
                market_gaps.append("MARKET_ANALYSIS_DATA_UNAVAILABLE")
        elif selected_skills:
            market_gaps.append("MARKET_ANALYSIS_DATA_UNAVAILABLE")
        filing = self._repository.latest_filing(company.id)
        if filing is not None and self._repository.filing_is_indexed(filing.id):
            retrieval = await self._retriever.retrieve(
                RewriteRequest(
                    company_name=company.name,
                    symbol=company.symbol,
                    locale=locale,
                    question=question,
                    context_labels=context_labels,
                    history=history,
                    summary=summary,
                ),
                company_id=company.id,
                filing_id=filing.id,
            )
            records.extend(
                _filing_record(company, filing, chunk, self._now())
                for chunk in retrieval.chunks
            )
        gaps = [
            gap.code
            for gap in structured_context.gaps
            if _gap_is_relevant(gap.resource, question)
        ]
        gaps.extend(market_gaps)
        if _filing_question(question) and filing is None:
            gaps.append("FILING_TEXT_MISSING")
        elif (
            _filing_question(question)
            and filing is not None
            and not self._repository.filing_is_indexed(filing.id)
        ):
            gaps.append("FILING_INDEX_MISSING")
        gaps = list(dict.fromkeys(gaps))
        coverage = "complete" if records and not gaps else "partial"
        if not records:
            coverage = "insufficient"
        return InternalEvidence(company, records, gaps, coverage)

    async def add_web(
        self,
        *,
        internal: InternalEvidence,
        company: Company,
        question: str,
        locale: str,
        principal: RequestPrincipal,
        conversation_id: UUID,
        assistant_message_id: UUID,
    ) -> PreparedAnswerEvidence:
        if internal.company.id != company.id or company.id is None:
            raise ValueError("internal evidence company mismatch")
        result = await self._web_search.search(
            WebSearchRequest(
                question=question,
                company_name=company.name,
                symbol=company.symbol,
                locale=locale,
                internal_coverage=internal.coverage,
                official_hosts=_official_hosts(internal.records),
                principal_scope=_principal_scope(principal),
                conversation_id=conversation_id,
                message_id=assistant_message_id,
            )
        )
        records = list(internal.records)
        records.extend(_web_record(page, question) for page in result.selected_pages)
        gaps = list(internal.evidence_gaps)
        if result.evidence_gap is not None:
            gaps.append(result.evidence_gap)
        pack = AnswerEvidencePack(
            company_id=company.id,
            company_name=company.name,
            symbol=company.symbol,
            records=records,
            evidence_gaps=list(dict.fromkeys(gaps)),
            web_search_used=bool(result.selected_pages),
        )
        return PreparedAnswerEvidence(pack, result.traces)


class DeterministicConversationSummarizer:
    def __init__(self, *, max_chars: int = 4_000) -> None:
        self._max_chars = max_chars

    async def summarize(
        self,
        *,
        previous_summary: str | None,
        messages: list[str],
        locale: str,
    ) -> str:
        del locale
        values = [value.strip() for value in [previous_summary, *messages] if value]
        summary = "\n".join(values)
        if len(summary) <= self._max_chars:
            return summary
        return summary[-self._max_chars :].lstrip()


def _filing_record(company, filing: Filing, chunk, retrieved_at: datetime):
    excerpt = chunk.text.strip()[:1_000]
    candidate = EvidenceCandidate(
        evidence_id=f"filing:{chunk.id}",
        source_kind="filing",
        source_id=str(chunk.id),
        title=f"{company.symbol} 10-K · {chunk.heading}",
        source_url=chunk.source_url,
        source_anchor=chunk.source_anchor,
        excerpt=excerpt,
        published_at=datetime.combine(filing.filed_at, time.min, tzinfo=UTC),
        retrieved_at=retrieved_at,
        source_tier="primary",
        verification="verified",
        attributes={
            "filing_id": str(filing.id),
            "fiscal_period": filing.fiscal_period,
        },
    )
    return ApprovedEvidenceRecord(
        company_id=company.id,
        candidate=candidate,
        source_text=chunk.text,
    )


def _web_record(page: SelectedWebPage, question: str) -> ApprovedEvidenceRecord:
    excerpt = _relevant_excerpt(page.body_text, question, limit=600)
    candidate = EvidenceCandidate(
        evidence_id=f"web:{page.result_id}",
        source_kind="web",
        source_id=page.result_id,
        title=page.title,
        source_url=page.url,
        source_anchor=None,
        excerpt=excerpt,
        published_at=page.published_at,
        retrieved_at=page.retrieved_at,
        source_tier=page.source_tier,
        verification="verified",
        attributes={"artifact_sha256": page.artifact.artifact_sha256},
    )
    return ApprovedEvidenceRecord(
        company_id=None,
        candidate=candidate,
        source_text=page.body_text,
    )


def _relevant_excerpt(body: str, question: str, *, limit: int) -> str:
    normalized = " ".join(body.split())
    terms = [
        term.casefold() for term in re.findall(r"[A-Za-z][A-Za-z0-9.-]{3,}", question)
    ]
    lower = normalized.casefold()
    starts = [lower.find(term) for term in terms if lower.find(term) >= 0]
    start = max(0, min(starts, default=0) - 120)
    return normalized[start : start + limit]


def _official_hosts(records: list[ApprovedEvidenceRecord]) -> tuple[str, ...]:
    hosts: list[str] = []
    for record in records:
        if record.candidate.source_tier != "primary":
            continue
        host = urlsplit(record.candidate.source_url).hostname
        if host and not host.endswith("sec.gov"):
            hosts.append(host.casefold())
    return tuple(dict.fromkeys(hosts))


def _principal_scope(principal: RequestPrincipal) -> str:
    if principal.principal_type == "user" and principal.user_id is not None:
        return f"user-{principal.user_id}"
    return f"guest-{principal.principal_hash[:32]}"


def _filing_question(question: str) -> bool:
    return (
        re.search(
            r"\b(10-k|filing|revenue|margin|cash flow|income|balance sheet)\b|"
            r"财报|营收|利润|毛利率|现金流|资产负债",
            question,
            re.IGNORECASE,
        )
        is not None
    )


def _gap_is_relevant(resource: str, question: str) -> bool:
    patterns = {
        "market": r"\b(price|valuation|p/e|pe ratio|market cap)\b|股价|估值|市盈率",
        "financials": (
            r"\b(revenue|margin|profit|cash flow|eps)\b|营收|利润|现金流|毛利率"
        ),
        "intelligence": r"\b(business|segment|product|strategy)\b|业务|产品|战略",
        "filing_text": r"\b(10-k|filing|annual report)\b|财报|年报",
        "filing_index": r"\b(10-k|filing|annual report)\b|财报|年报",
        "supply_chain_graph": (
            r"\b(supply chain|supplier|customer|upstream|downstream)\b|"
            r"产业链|供应商|客户|上游|下游"
        ),
    }
    pattern = patterns.get(resource)
    return (
        pattern is not None and re.search(pattern, question, re.IGNORECASE) is not None
    )
