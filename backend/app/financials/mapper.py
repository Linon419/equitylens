from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

TAGS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
}
METRIC_ORDER = (*TAGS, "free_cash_flow")
ANNUAL_FORMS = {"10-K", "20-F"}


@dataclass(frozen=True)
class MappedPoint:
    metric_key: str
    period_key: str
    fiscal_year: int
    fiscal_period: str
    start_date: date | None
    end_date: date
    value: Decimal
    unit: str
    taxonomy_tag: str
    accession_number: str
    filed_at: date
    source_url: str


@dataclass(frozen=True)
class MappedSeries:
    metric_key: str
    annual: tuple[MappedPoint, ...]
    ttm: MappedPoint | None
    missing_reason: str | None = None


def map_company_facts(payload: dict[str, Any]) -> dict[str, MappedSeries]:
    cik = _normalize_cik(payload.get("cik"))
    source_url = (
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    )
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    if not isinstance(us_gaap, dict):
        us_gaap = {}

    result = {
        metric: _map_metric(metric, tags, us_gaap, source_url)
        for metric, tags in TAGS.items()
    }
    result["free_cash_flow"] = _derive_free_cash_flow(
        result["operating_cash_flow"],
        result["capital_expenditure"],
    )
    return result


def _map_metric(
    metric_key: str,
    tags: tuple[str, ...],
    facts: dict[str, Any],
    source_url: str,
) -> MappedSeries:
    for tag in tags:
        raw_facts = _usd_facts(facts.get(tag))
        annual = _select_annual(raw_facts, metric_key, tag, source_url)
        if not annual:
            continue
        ttm = _select_ttm(
            raw_facts,
            annual[-1],
            metric_key,
            tag,
            source_url,
        )
        return MappedSeries(
            metric_key=metric_key,
            annual=tuple(annual[-4:]),
            ttm=ttm,
            missing_reason=(
                None if ttm is not None else "COMPARABLE_YTD_UNAVAILABLE"
            ),
        )
    return MappedSeries(
        metric_key=metric_key,
        annual=(),
        ttm=None,
        missing_reason="ANNUAL_FACTS_UNAVAILABLE",
    )


def _usd_facts(concept: Any) -> list[dict[str, Any]]:
    if not isinstance(concept, dict):
        return []
    units = concept.get("units")
    if not isinstance(units, dict):
        return []
    values = units.get("USD", [])
    return [item for item in values if isinstance(item, dict)]


def _select_annual(
    facts: list[dict[str, Any]],
    metric_key: str,
    tag: str,
    source_url: str,
) -> list[MappedPoint]:
    candidates: dict[tuple[str, date], MappedPoint] = {}
    for fact in facts:
        point = _to_point(fact, metric_key, tag, source_url)
        if (
            point is None
            or fact.get("form") not in ANNUAL_FORMS
            or fact.get("fp") != "FY"
        ):
            continue
        if point.start_date is None:
            continue
        duration = (point.end_date - point.start_date).days
        if duration < 300 or duration > 430:
            continue
        key = (point.accession_number, point.end_date)
        previous = candidates.get(key)
        if previous is None or point.filed_at > previous.filed_at:
            candidates[key] = point

    by_year: dict[int, MappedPoint] = {}
    for point in candidates.values():
        previous = by_year.get(point.fiscal_year)
        if previous is None or (point.end_date, point.filed_at) > (
            previous.end_date,
            previous.filed_at,
        ):
            by_year[point.fiscal_year] = point
    return [by_year[year] for year in sorted(by_year)]


def _select_ttm(
    facts: list[dict[str, Any]],
    latest_fy: MappedPoint,
    metric_key: str,
    tag: str,
    source_url: str,
) -> MappedPoint | None:
    ytd_points: list[MappedPoint] = []
    for fact in facts:
        point = _to_point(fact, metric_key, tag, source_url)
        if point is None or fact.get("form") != "10-Q":
            continue
        if point.start_date is None or point.fiscal_period not in {"Q1", "Q2", "Q3"}:
            continue
        duration = (point.end_date - point.start_date).days
        if 45 <= duration < 300:
            ytd_points.append(point)
    if not ytd_points:
        return None

    current = max(ytd_points, key=lambda point: (point.end_date, point.filed_at))
    comparable = [
        point
        for point in ytd_points
        if point.fiscal_year == current.fiscal_year - 1
        and point.fiscal_period == current.fiscal_period
    ]
    if not comparable:
        return None
    prior = max(comparable, key=lambda point: (point.end_date, point.filed_at))
    return replace(
        current,
        period_key=f"TTM-{current.fiscal_year}{current.fiscal_period}",
        fiscal_period="TTM",
        start_date=None,
        value=latest_fy.value + current.value - prior.value,
    )


def _to_point(
    fact: dict[str, Any],
    metric_key: str,
    tag: str,
    source_url: str,
) -> MappedPoint | None:
    try:
        fiscal_year = int(fact["fy"])
        fiscal_period = str(fact["fp"])
        end_date = date.fromisoformat(str(fact["end"]))
        start = fact.get("start")
        start_date = date.fromisoformat(str(start)) if start else None
        filed_at = date.fromisoformat(str(fact["filed"]))
        value = Decimal(str(fact["val"]))
        accession = str(fact["accn"])
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
    return MappedPoint(
        metric_key=metric_key,
        period_key=(
            f"FY{fiscal_year}"
            if fiscal_period == "FY"
            else f"{fiscal_year}{fiscal_period}"
        ),
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        start_date=start_date,
        end_date=end_date,
        value=value,
        unit="USD",
        taxonomy_tag=tag,
        accession_number=accession,
        filed_at=filed_at,
        source_url=source_url,
    )


def _derive_free_cash_flow(
    operating: MappedSeries,
    capex: MappedSeries,
) -> MappedSeries:
    capex_by_period = {point.period_key: point for point in capex.annual}
    annual = tuple(
        _subtract_capex(point, capex_by_period[point.period_key])
        for point in operating.annual
        if point.period_key in capex_by_period
    )
    ttm = None
    if operating.ttm is not None and capex.ttm is not None:
        ttm = _subtract_capex(operating.ttm, capex.ttm)
    missing_reason = None
    if not annual:
        missing_reason = "FREE_CASH_FLOW_INPUTS_UNAVAILABLE"
    elif ttm is None:
        missing_reason = "COMPARABLE_YTD_UNAVAILABLE"
    return MappedSeries("free_cash_flow", annual, ttm, missing_reason)


def _subtract_capex(
    operating: MappedPoint,
    capex: MappedPoint,
) -> MappedPoint:
    return replace(
        operating,
        metric_key="free_cash_flow",
        value=operating.value - abs(capex.value),
        taxonomy_tag="derived:operating_cash_flow-capital_expenditure",
    )


def _normalize_cik(value: Any) -> str:
    try:
        return f"{int(value):010d}"
    except (TypeError, ValueError):
        return "0000000000"
