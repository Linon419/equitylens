from datetime import UTC, datetime

from sqlmodel import Session

from app.chat.schemas import (
    BusinessClaimContext,
    ChatReadiness,
    ContextSelection,
    EvidenceCandidate,
    EvidenceGap,
    FinancialMetricContext,
    MarketMetricContext,
    ReadinessResource,
    StructuredContextItem,
    StructuredContextPack,
    SupplyChainEdgeContext,
    SupplyChainNodeContext,
)
from app.chat.structured_entities import EntityContextResolver
from app.chat.structured_metrics import LABELS, MetricContextResolver
from app.chat.structured_repository import SqlStructuredContextRepository
from app.core.errors import DomainError
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.models.market_model import FinancialMetric, MarketSnapshot
from app.models.research_model import CompanyIntelligenceSnapshot, Filing
from app.models.supply_chain_model import SupplyChainGraphSnapshot


class StructuredContextService:
    def __init__(
        self,
        session: Session,
        *,
        repository: SqlStructuredContextRepository | None = None,
        now: datetime | None = None,
    ) -> None:
        self._repository = repository or SqlStructuredContextRepository(session)
        self._now = _as_utc(now or datetime.now(UTC))
        self._metrics = MetricContextResolver(now=self._now)
        self._entities = EntityContextResolver(self._repository, now=self._now)

    async def resolve(
        self,
        *,
        company: Company,
        selections: list[ContextSelection],
        locale: str,
    ) -> StructuredContextPack:
        if company.id is None or locale not in LABELS:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        market = self._repository.latest_market(company.id)
        financials = self._repository.financial_window(company.id)
        intelligence = self._repository.latest_intelligence(company.id)
        filing = self._repository.latest_filing(company.id)
        graph = self._repository.latest_graph(company.id)
        evidence = [
            *self._metrics.market_evidence(company, market),
            *self._metrics.financial_evidence(company, financials),
        ]
        items = [
            self._selection(
                company,
                selection,
                locale=locale,
                market=market,
                financials=financials,
                intelligence=intelligence,
                graph=graph,
            )
            for selection in selections
        ]
        evidence.extend(item.citation for item in items)
        readiness = self._readiness(
            company.id,
            company.symbol,
            intelligence=intelligence,
            filing=filing,
            graph=graph,
        )
        return StructuredContextPack(
            items=items,
            evidence=_unique_evidence(evidence),
            readiness=readiness,
            gaps=self._gaps(market, financials, readiness),
        )

    def _selection(
        self,
        company: Company,
        selection: ContextSelection,
        *,
        locale: str,
        market: MarketSnapshot | None,
        financials: list[FinancialMetric],
        intelligence: CompanyIntelligenceSnapshot | None,
        graph: SupplyChainGraphSnapshot | None,
    ) -> StructuredContextItem:
        if isinstance(selection, MarketMetricContext):
            return self._metrics.market_item(company, selection, locale, market)
        if isinstance(selection, FinancialMetricContext):
            return self._metrics.financial_item(
                company,
                selection,
                locale,
                financials,
            )
        if isinstance(selection, BusinessClaimContext):
            return self._entities.business_item(
                company,
                selection,
                locale,
                intelligence,
            )
        if isinstance(selection, SupplyChainNodeContext):
            return self._entities.node_item(selection, locale, graph)
        if isinstance(selection, SupplyChainEdgeContext):
            return self._entities.edge_item(selection, locale, graph)
        raise DomainError("CHAT_CONTEXT_INVALID", 422)

    def _readiness(
        self,
        company_id: int,
        symbol: str,
        *,
        intelligence: CompanyIntelligenceSnapshot | None,
        filing: Filing | None,
        graph: SupplyChainGraphSnapshot | None,
    ) -> ChatReadiness:
        analysis_job = self._repository.latest_job(company_id, "company_intelligence")
        index_job = self._repository.latest_job(company_id, "filing_index")
        graph_job = self._repository.latest_job(company_id, "supply_chain_graph")
        filing_ready = filing is not None
        index_ready = filing_ready and self._repository.filing_is_indexed(filing.id)
        return ChatReadiness(
            company_symbol=symbol,
            intelligence=_resource(
                intelligence is not None,
                analysis_job,
                "company_analysis",
            ),
            filing_text=_resource(filing_ready, analysis_job, "company_analysis"),
            filing_index=_resource(
                index_ready,
                index_job,
                "filing_index" if filing_ready else "company_analysis",
            ),
            supply_chain_graph=_resource(
                graph is not None,
                graph_job,
                "supply_chain_graph",
            ),
            web_recency=ReadinessResource(state="missing", action=None),
        )

    def _gaps(
        self,
        market: MarketSnapshot | None,
        financials: list[FinancialMetric],
        readiness: ChatReadiness,
    ) -> list[EvidenceGap]:
        gaps: list[EvidenceGap] = []
        if market is None:
            gaps.append(EvidenceGap(resource="market", code="MARKET_MISSING"))
        if not financials:
            gaps.append(EvidenceGap(resource="financials", code="FINANCIALS_MISSING"))
        for name in (
            "intelligence",
            "filing_text",
            "filing_index",
            "supply_chain_graph",
            "web_recency",
        ):
            resource = getattr(readiness, name)
            if resource.state != "ready":
                gaps.append(
                    EvidenceGap(
                        resource=name,
                        code=f"{name.upper()}_{resource.state.upper()}",
                        action=resource.action,
                    )
                )
        return gaps


def _resource(
    ready: bool,
    job: IngestionJob | None,
    action,
) -> ReadinessResource:
    if ready:
        return ReadinessResource(state="ready", action=None)
    if job is not None and job.state == "failed":
        return ReadinessResource(state="failed", action=action)
    if job is not None and job.state != "completed":
        return ReadinessResource(state="running", action=None)
    return ReadinessResource(state="missing", action=action)


def _unique_evidence(
    evidence: list[EvidenceCandidate],
) -> list[EvidenceCandidate]:
    result: dict[str, EvidenceCandidate] = {}
    for item in evidence:
        result.setdefault(item.evidence_id, item)
    return list(result.values())


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
