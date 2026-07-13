from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlmodel import Session, select

from app.core.errors import DomainError
from app.financials.mapper import METRIC_ORDER, MappedPoint, map_company_facts
from app.financials.schemas import (
    FinancialPoint,
    FinancialSeries,
    FinancialsResponse,
)
from app.models.company_model import Company
from app.models.market_model import FinancialMetric
from app.providers.sec import SecDataProvider

DEFAULT_TTL_SECONDS = 24 * 60 * 60


async def get_financials(
    session: Session,
    company: Company,
    provider: SecDataProvider,
    *,
    now: datetime | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> FinancialsResponse:
    current_time = now or datetime.now(UTC)
    cached = _metric_rows(session, company)
    if cached and _is_fresh(cached[0].fetched_at, current_time, ttl_seconds):
        return _build_response(company.symbol, cached, "fresh")

    try:
        payload = await provider.get_company_facts(company.cik)
        mapped = map_company_facts(payload)
        if not any(series.annual for series in mapped.values()):
            raise DomainError("FINANCIAL_FACTS_EMPTY", 502)
        rows = _persist_metrics(
            session,
            company,
            mapped,
            fetched_at=current_time,
        )
    except Exception as error:
        if cached:
            return _build_response(company.symbol, cached, "stale")
        if (
            isinstance(error, DomainError)
            and error.code == "FINANCIAL_DATA_UNAVAILABLE"
        ):
            raise
        raise DomainError("FINANCIAL_DATA_UNAVAILABLE", 503) from error

    return _build_response(company.symbol, rows, "fresh")


def _metric_rows(
    session: Session,
    company: Company,
) -> list[FinancialMetric]:
    return list(
        session.exec(
            select(FinancialMetric)
            .where(FinancialMetric.company_id == company.id)
            .order_by(FinancialMetric.fetched_at.desc())
        ).all()
    )


def _persist_metrics(
    session: Session,
    company: Company,
    mapped: dict,
    *,
    fetched_at: datetime,
) -> list[FinancialMetric]:
    existing = _metric_rows(session, company)
    by_key = {
        (row.metric_key, row.period_key, row.accession_number): row
        for row in existing
    }
    desired: set[tuple[str, str, str]] = set()

    for series in mapped.values():
        for point in (*series.annual, *(() if series.ttm is None else (series.ttm,))):
            key = (point.metric_key, point.period_key, point.accession_number)
            desired.add(key)
            row = by_key.get(key)
            if row is None:
                row = FinancialMetric(company_id=company.id, **_point_values(point))
            else:
                for field, value in _point_values(point).items():
                    setattr(row, field, value)
            row.fetched_at = fetched_at
            session.add(row)

    for key, row in by_key.items():
        if key not in desired:
            session.delete(row)
    session.commit()
    return _metric_rows(session, company)


def _point_values(point: MappedPoint) -> dict:
    return {
        "metric_key": point.metric_key,
        "fiscal_year": point.fiscal_year,
        "fiscal_period": point.fiscal_period,
        "period_key": point.period_key,
        "start_date": point.start_date,
        "end_date": point.end_date,
        "value": point.value,
        "unit": point.unit,
        "taxonomy_tag": point.taxonomy_tag,
        "accession_number": point.accession_number,
        "filed_at": point.filed_at,
        "source_url": point.source_url,
    }


def _build_response(
    symbol: str,
    rows: list[FinancialMetric],
    freshness: Literal["fresh", "stale"],
) -> FinancialsResponse:
    fetched_at = max(_as_utc(row.fetched_at) for row in rows)
    current_rows = [
        row for row in rows if _as_utc(row.fetched_at) == fetched_at
    ]
    grouped = {
        metric: [row for row in current_rows if row.metric_key == metric]
        for metric in METRIC_ORDER
    }
    series = [_build_series(metric, grouped[metric]) for metric in METRIC_ORDER]
    return FinancialsResponse(
        symbol=symbol,
        series=series,
        fetched_at=fetched_at,
        freshness=freshness,
    )


def _build_series(
    metric_key: str,
    rows: list[FinancialMetric],
) -> FinancialSeries:
    annual_rows = sorted(
        (row for row in rows if row.fiscal_period != "TTM"),
        key=lambda row: (row.fiscal_year, row.end_date),
    )
    ttm_row = max(
        (row for row in rows if row.fiscal_period == "TTM"),
        key=lambda row: row.end_date,
        default=None,
    )
    missing_reason = None
    if not annual_rows:
        missing_reason = "ANNUAL_FACTS_UNAVAILABLE"
    elif ttm_row is None:
        missing_reason = "COMPARABLE_YTD_UNAVAILABLE"
    return FinancialSeries(
        metric_key=metric_key,
        annual=[_public_point(row) for row in annual_rows],
        ttm=_public_point(ttm_row) if ttm_row is not None else None,
        missing_reason=missing_reason,
    )


def _public_point(row: FinancialMetric) -> FinancialPoint:
    return FinancialPoint(
        period_key=row.period_key,
        value=row.value,
        unit=row.unit,
        end_date=row.end_date,
        accession_number=row.accession_number,
        source_url=row.source_url,
    )


def _is_fresh(value: datetime, now: datetime, ttl_seconds: int) -> bool:
    return now - _as_utc(value) <= timedelta(seconds=ttl_seconds)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
