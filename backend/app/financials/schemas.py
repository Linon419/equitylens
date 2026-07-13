from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class FinancialPoint(BaseModel):
    period_key: str
    value: Decimal
    unit: str
    end_date: date
    accession_number: str
    source_url: str


class FinancialSeries(BaseModel):
    metric_key: str
    annual: list[FinancialPoint]
    ttm: FinancialPoint | None
    missing_reason: str | None = None


class FinancialsResponse(BaseModel):
    symbol: str
    series: list[FinancialSeries]
    source: Literal["SEC XBRL Company Facts"] = "SEC XBRL Company Facts"
    fetched_at: datetime
    freshness: Literal["fresh", "stale"]
