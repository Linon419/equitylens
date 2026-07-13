from copy import deepcopy
from decimal import Decimal

from app.financials.mapper import map_company_facts


def test_mapper_returns_four_fiscal_years_and_ttm(company_facts: dict) -> None:
    result = map_company_facts(company_facts)

    revenue = result["revenue"]
    assert [point.period_key for point in revenue.annual] == [
        "FY2022",
        "FY2023",
        "FY2024",
        "FY2025",
    ]
    assert revenue.annual[-2].value == Decimal("390000000000")
    assert revenue.ttm is not None
    assert revenue.ttm.value == Decimal("401000000000")
    assert revenue.ttm.period_key == "TTM-2026Q1"
    assert revenue.ttm.taxonomy_tag == (
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    )


def test_free_cash_flow_subtracts_positive_capex(
    company_facts: dict,
) -> None:
    result = map_company_facts(company_facts)

    free_cash_flow = result["free_cash_flow"]
    assert free_cash_flow.annual[-1].value == Decimal("108000000000")
    assert free_cash_flow.ttm is not None
    assert free_cash_flow.ttm.value == Decimal("109000000000")


def test_mapper_uses_ordered_revenue_tag_fallbacks(
    company_facts: dict,
) -> None:
    fallback = deepcopy(company_facts)
    facts = fallback["facts"]["us-gaap"]
    facts["Revenues"] = facts.pop(
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    )

    result = map_company_facts(fallback)

    assert result["revenue"].annual[-1].taxonomy_tag == "Revenues"

    facts["SalesRevenueNet"] = facts.pop("Revenues")
    result = map_company_facts(fallback)
    assert result["revenue"].annual[-1].taxonomy_tag == "SalesRevenueNet"


def test_mapper_supports_non_calendar_fiscal_year() -> None:
    payload = {
        "cik": 1,
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "start": "2024-07-01",
                                "end": "2025-06-30",
                                "val": 42,
                                "accn": "0001-25-000001",
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2025-08-20",
                            }
                        ]
                    }
                }
            }
        },
    }

    revenue = map_company_facts(payload)["revenue"]

    assert revenue.annual[0].period_key == "FY2025"
    assert revenue.annual[0].end_date.isoformat() == "2025-06-30"


def test_mapper_marks_ttm_unavailable_when_comparable_ytd_is_missing(
    company_facts: dict,
) -> None:
    incomplete = deepcopy(company_facts)
    revenue = incomplete["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"]
    incomplete["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"] = [
        fact
        for fact in revenue
        if fact.get("fy") != 2025 or fact["fp"] == "FY"
    ]

    mapped = map_company_facts(incomplete)["revenue"]

    assert mapped.ttm is None
    assert mapped.missing_reason == "COMPARABLE_YTD_UNAVAILABLE"
