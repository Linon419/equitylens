from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from app.chat.schemas import (
    EvidenceCandidate,
    FinancialMetricContext,
    MarketMetricContext,
    StructuredContextItem,
)
from app.core.errors import DomainError
from app.financials.mapper import METRIC_ORDER
from app.models.company_model import Company
from app.models.market_model import FinancialMetric, MarketSnapshot

MARKET_METRICS = (
    "price",
    "market_cap",
    "trailing_eps",
    "trailing_pe",
    "forward_pe",
)
LABELS = {
    "en-US": {
        "price": "Price",
        "market_cap": "Market cap",
        "trailing_eps": "Trailing EPS",
        "trailing_pe": "Trailing P/E",
        "forward_pe": "Forward P/E",
        "revenue": "Revenue",
        "net_income": "Net income",
        "operating_cash_flow": "Operating cash flow",
        "capital_expenditure": "Capital expenditure",
        "free_cash_flow": "Free cash flow",
    },
    "zh-CN": {
        "price": "股价",
        "market_cap": "市值",
        "trailing_eps": "滚动每股收益",
        "trailing_pe": "滚动市盈率",
        "forward_pe": "预期市盈率",
        "revenue": "营收",
        "net_income": "净利润",
        "operating_cash_flow": "经营现金流",
        "capital_expenditure": "资本支出",
        "free_cash_flow": "自由现金流",
    },
}


class MetricContextResolver:
    def __init__(self, *, now: datetime) -> None:
        self._now = now

    def market_evidence(
        self,
        company: Company,
        snapshot: MarketSnapshot | None,
    ) -> list[EvidenceCandidate]:
        if snapshot is None:
            return []
        return [
            self._market_candidate(company, snapshot, metric)
            for metric in MARKET_METRICS
            if getattr(snapshot, metric) is not None
        ]

    def financial_evidence(
        self,
        company: Company,
        rows: list[FinancialMetric],
    ) -> list[EvidenceCandidate]:
        return [self._financial_candidate(company, row) for row in rows]

    def market_item(
        self,
        company: Company,
        selection: MarketMetricContext,
        locale: str,
        snapshot: MarketSnapshot | None,
    ) -> StructuredContextItem:
        if snapshot is None or getattr(snapshot, selection.metric_key) is None:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        if selection.observed_at is not None and _as_utc(
            selection.observed_at
        ) != _as_utc(snapshot.observed_at):
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        citation = self._market_candidate(company, snapshot, selection.metric_key)
        return StructuredContextItem(
            kind=selection.kind,
            source_id=str(snapshot.id),
            label=LABELS[locale][selection.metric_key],
            description=citation.excerpt,
            citation=citation,
        )

    def financial_item(
        self,
        company: Company,
        selection: FinancialMetricContext,
        locale: str,
        rows: list[FinancialMetric],
    ) -> StructuredContextItem:
        if selection.metric_key not in METRIC_ORDER:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        row = next(
            (
                item
                for item in rows
                if item.metric_key == selection.metric_key
                and item.period_key == selection.period_key
            ),
            None,
        )
        if row is None:
            raise DomainError("CHAT_CONTEXT_INVALID", 422)
        citation = self._financial_candidate(company, row)
        label = LABELS[locale][selection.metric_key]
        return StructuredContextItem(
            kind=selection.kind,
            source_id=str(row.id),
            label=f"{label} · {row.period_key}",
            description=citation.excerpt,
            citation=citation,
        )

    def _market_candidate(
        self,
        company: Company,
        snapshot: MarketSnapshot,
        metric: str,
    ) -> EvidenceCandidate:
        value = cast(Decimal, getattr(snapshot, metric))
        label = LABELS["en-US"][metric]
        value_text = _market_value(metric, value)
        return EvidenceCandidate(
            evidence_id=f"market:{snapshot.id}:{metric}",
            source_kind="financial",
            source_id=str(snapshot.id),
            title=f"{company.symbol} {label}",
            source_url=f"https://finance.yahoo.com/quote/{company.symbol}",
            source_anchor=metric,
            excerpt=f"{company.symbol} {label} was {value_text} {snapshot.currency}.",
            published_at=_as_utc(snapshot.observed_at),
            retrieved_at=self._now,
            source_tier="trusted_secondary",
            verification="supporting",
            attributes={
                "metric_key": metric,
                "value": value_text,
                "unit": snapshot.currency,
                "provider": snapshot.provider,
            },
        )

    def _financial_candidate(
        self,
        company: Company,
        row: FinancialMetric,
    ) -> EvidenceCandidate:
        label = LABELS["en-US"][row.metric_key]
        value = format(row.value.normalize(), "f")
        return EvidenceCandidate(
            evidence_id=f"financial:{row.id}",
            source_kind="financial",
            source_id=str(row.id),
            title=f"{company.symbol} {label} · {row.period_key}",
            source_url=row.source_url,
            source_anchor=row.period_key,
            excerpt=(
                f"{company.symbol} {label} for {row.period_key} was "
                f"{value} {row.unit}."
            ),
            published_at=datetime.combine(
                row.filed_at,
                datetime.min.time(),
                tzinfo=UTC,
            ),
            retrieved_at=self._now,
            source_tier="primary",
            verification="verified",
            attributes={
                "metric_key": row.metric_key,
                "period_key": row.period_key,
                "value": value,
                "unit": row.unit,
                "accession_number": row.accession_number,
            },
        )


def _market_value(metric: str, value: Decimal) -> str:
    if metric == "market_cap":
        return f"{value:.0f}"
    return f"{value:.2f}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
