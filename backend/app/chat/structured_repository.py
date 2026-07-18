from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import case, or_
from sqlmodel import Session, select

from app.filings.mapper import ANNUAL_FILING_FORMS
from app.financials.mapper import METRIC_ORDER
from app.models.chat_model import FilingChunk
from app.models.job_model import IngestionJob
from app.models.market_model import FinancialMetric, MarketSnapshot
from app.models.research_model import (
    CompanyIntelligenceSnapshot,
    EvidenceCitation,
    Filing,
)
from app.models.supply_chain_model import (
    GraphEdgeCitation,
    GraphOfficialSource,
    SupplyChainGraphEdge,
    SupplyChainGraphNode,
    SupplyChainGraphSnapshot,
)

_PUBLIC_GRAPH_STATUSES = ("completed", "insufficient_evidence")


@dataclass(frozen=True)
class GraphCitationRecord:
    citation: GraphEdgeCitation
    source: GraphOfficialSource
    edge: SupplyChainGraphEdge


class SqlStructuredContextRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest_market(self, company_id: int) -> MarketSnapshot | None:
        return self._session.exec(
            select(MarketSnapshot)
            .where(MarketSnapshot.company_id == company_id)
            .order_by(MarketSnapshot.fetched_at.desc(), MarketSnapshot.id.desc())
        ).first()

    def financial_window(self, company_id: int) -> list[FinancialMetric]:
        rows = list(
            self._session.exec(
                select(FinancialMetric)
                .where(FinancialMetric.company_id == company_id)
                .order_by(FinancialMetric.fetched_at.desc())
            ).all()
        )
        if not rows:
            return []
        latest_fetch = rows[0].fetched_at
        current = [row for row in rows if row.fetched_at == latest_fetch]
        result: list[FinancialMetric] = []
        for metric_key in METRIC_ORDER:
            metric_rows = [row for row in current if row.metric_key == metric_key]
            annual_by_period: dict[str, FinancialMetric] = {}
            for row in metric_rows:
                if row.fiscal_period == "TTM":
                    continue
                previous = annual_by_period.get(row.period_key)
                if previous is None or (row.filed_at, row.accession_number) > (
                    previous.filed_at,
                    previous.accession_number,
                ):
                    annual_by_period[row.period_key] = row
            annual = sorted(
                annual_by_period.values(),
                key=lambda row: (row.fiscal_year, row.end_date, row.filed_at),
            )[-4:]
            ttm = max(
                (row for row in metric_rows if row.fiscal_period == "TTM"),
                key=lambda row: (row.end_date, row.filed_at),
                default=None,
            )
            result.extend(annual)
            if ttm is not None:
                result.append(ttm)
        return result

    def latest_intelligence(
        self,
        company_id: int,
    ) -> CompanyIntelligenceSnapshot | None:
        return self._session.exec(
            select(CompanyIntelligenceSnapshot)
            .where(
                CompanyIntelligenceSnapshot.company_id == company_id,
                CompanyIntelligenceSnapshot.status == "completed",
            )
            .order_by(
                CompanyIntelligenceSnapshot.generated_at.desc(),
                CompanyIntelligenceSnapshot.id.desc(),
            )
        ).first()

    def intelligence_citations(
        self,
        snapshot_id: UUID,
    ) -> list[EvidenceCitation]:
        return list(
            self._session.exec(
                select(EvidenceCitation)
                .where(EvidenceCitation.snapshot_id == snapshot_id)
                .order_by(EvidenceCitation.id)
            ).all()
        )

    def filing(self, filing_id: UUID) -> Filing | None:
        return self._session.get(Filing, filing_id)

    def latest_filing(self, company_id: int) -> Filing | None:
        return self._session.exec(
            select(Filing)
            .where(
                Filing.company_id == company_id,
                Filing.form.in_(ANNUAL_FILING_FORMS),
            )
            .order_by(
                Filing.filed_at.desc(),
                case((Filing.form == "10-K", 1), else_=0).desc(),
                Filing.id.desc(),
            )
        ).first()

    def filing_is_indexed(self, filing_id: UUID) -> bool:
        return (
            self._session.exec(
                select(FilingChunk.id).where(FilingChunk.filing_id == filing_id)
            ).first()
            is not None
        )

    def latest_graph(self, company_id: int) -> SupplyChainGraphSnapshot | None:
        return self._session.exec(
            select(SupplyChainGraphSnapshot)
            .where(
                SupplyChainGraphSnapshot.company_id == company_id,
                SupplyChainGraphSnapshot.status.in_(_PUBLIC_GRAPH_STATUSES),
            )
            .order_by(
                SupplyChainGraphSnapshot.completed_at.desc(),
                SupplyChainGraphSnapshot.generated_at.desc(),
                SupplyChainGraphSnapshot.id.desc(),
            )
        ).first()

    def graph_node(
        self,
        snapshot_id: UUID,
        node_id: UUID,
    ) -> SupplyChainGraphNode | None:
        return self._session.exec(
            select(SupplyChainGraphNode).where(
                SupplyChainGraphNode.snapshot_id == snapshot_id,
                SupplyChainGraphNode.id == node_id,
            )
        ).first()

    def graph_edge(
        self,
        snapshot_id: UUID,
        edge_id: UUID,
    ) -> SupplyChainGraphEdge | None:
        return self._session.exec(
            select(SupplyChainGraphEdge).where(
                SupplyChainGraphEdge.snapshot_id == snapshot_id,
                SupplyChainGraphEdge.id == edge_id,
                SupplyChainGraphEdge.evidence_status.in_(("verified", "potential")),
            )
        ).first()

    def graph_citation_for_edge(
        self,
        snapshot_id: UUID,
        edge_id: UUID,
    ) -> GraphCitationRecord | None:
        return self._graph_citation(snapshot_id, edge_id=edge_id)

    def graph_citation_for_node(
        self,
        snapshot_id: UUID,
        node_id: UUID,
    ) -> GraphCitationRecord | None:
        return self._graph_citation(snapshot_id, node_id=node_id)

    def latest_job(self, company_id: int, job_type: str) -> IngestionJob | None:
        return self._session.exec(
            select(IngestionJob)
            .where(
                IngestionJob.company_id == company_id,
                IngestionJob.job_type == job_type,
            )
            .order_by(IngestionJob.created_at.desc(), IngestionJob.id.desc())
        ).first()

    def _graph_citation(
        self,
        snapshot_id: UUID,
        *,
        edge_id: UUID | None = None,
        node_id: UUID | None = None,
    ) -> GraphCitationRecord | None:
        statement = (
            select(GraphEdgeCitation, GraphOfficialSource, SupplyChainGraphEdge)
            .join(
                GraphOfficialSource,
                GraphOfficialSource.id == GraphEdgeCitation.source_id,
            )
            .join(
                SupplyChainGraphEdge,
                SupplyChainGraphEdge.id == GraphEdgeCitation.edge_id,
            )
            .where(
                GraphEdgeCitation.snapshot_id == snapshot_id,
                GraphOfficialSource.snapshot_id == snapshot_id,
                SupplyChainGraphEdge.snapshot_id == snapshot_id,
                SupplyChainGraphEdge.evidence_status.in_(("verified", "potential")),
            )
        )
        if edge_id is not None:
            statement = statement.where(SupplyChainGraphEdge.id == edge_id)
        if node_id is not None:
            statement = statement.where(
                or_(
                    SupplyChainGraphEdge.source_node_id == node_id,
                    SupplyChainGraphEdge.target_node_id == node_id,
                )
            )
        row = self._session.exec(
            statement.order_by(
                case((SupplyChainGraphEdge.evidence_status == "verified", 0), else_=1),
                case((GraphEdgeCitation.support_role == "primary", 0), else_=1),
                GraphEdgeCitation.id,
            )
        ).first()
        if row is None:
            return None
        citation, source, edge = row
        return GraphCitationRecord(citation, source, edge)
