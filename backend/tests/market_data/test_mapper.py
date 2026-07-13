import json
from decimal import Decimal
from pathlib import Path

from app.market_data.mapper import map_company_profile, map_quote, to_decimal

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/yahoo/aapl_quote.json"


def test_profile_mapper_preserves_company_classification() -> None:
    result = map_company_profile(
        "AAPL",
        {
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "longBusinessSummary": "Apple designs and sells devices and services.",
        },
    )

    assert result.name == "Apple Inc."
    assert result.sector == "Technology"
    assert result.industry == "Consumer Electronics"


def test_mapper_uses_provider_values_and_calculates_missing_trailing_pe() -> None:
    payload = json.loads(FIXTURE.read_text())

    result = map_quote(
        "AAPL",
        fast_info=payload["fast_info"],
        info=payload["info"],
    )

    assert result.price == Decimal("212.48")
    assert result.previous_close == Decimal("209.88")
    assert result.price_change == Decimal("2.60")
    assert result.price_change_percent == Decimal("1.238803")
    assert result.trailing_pe == Decimal("33.096573")
    assert result.forward_pe == Decimal("29.4")
    assert result.missing_reasons == {}


def test_mapper_prefers_provider_trailing_pe() -> None:
    result = map_quote(
        "AAPL",
        fast_info={"last_price": 212.48, "currency": "USD"},
        info={"trailingEps": 6.42, "trailingPE": 32.5},
    )

    assert result.trailing_pe == Decimal("32.5")


def test_mapper_marks_non_positive_eps_as_not_meaningful() -> None:
    result = map_quote(
        "LOSS",
        fast_info={"last_price": 10, "currency": "USD"},
        info={"trailingEps": -2},
    )

    assert result.trailing_pe is None
    assert result.missing_reasons["trailing_pe"] == "NON_POSITIVE_EPS"
    assert result.missing_reasons["forward_pe"] == "PROVIDER_FIELD_MISSING"


def test_decimal_conversion_rejects_non_finite_and_boolean_values() -> None:
    assert to_decimal(True) is None
    assert to_decimal(float("nan")) is None
    assert to_decimal(float("inf")) is None
    assert to_decimal("not-a-number") is None
