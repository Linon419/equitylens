from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.providers.market import CompanyProfile, QuoteSnapshot

RATIO_QUANTUM = Decimal("0.000001")


def to_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def map_company_profile(
    symbol: str,
    info: Mapping[str, Any],
) -> CompanyProfile:
    return CompanyProfile(
        symbol=symbol.strip().upper(),
        name=_text(info.get("longName") or info.get("shortName")) or symbol,
        sector=_text(info.get("sector")),
        industry=_text(info.get("industry")),
        description=_text(info.get("longBusinessSummary")),
    )


def map_quote(
    symbol: str,
    *,
    fast_info: Mapping[str, Any],
    info: Mapping[str, Any],
    observed_at: datetime | None = None,
) -> QuoteSnapshot:
    price = to_decimal(_get(fast_info, "last_price", "lastPrice"))
    previous_close = to_decimal(
        _get(fast_info, "previous_close", "previousClose")
    )
    market_cap = to_decimal(_get(fast_info, "market_cap", "marketCap"))
    trailing_eps = to_decimal(info.get("trailingEps"))
    forward_pe = to_decimal(info.get("forwardPE"))
    trailing_pe = _trailing_pe(info, price, trailing_eps)
    price_change, price_change_percent = _price_change(price, previous_close)
    values = {
        "price": price,
        "previous_close": previous_close,
        "price_change": price_change,
        "price_change_percent": price_change_percent,
        "market_cap": market_cap,
        "trailing_eps": trailing_eps,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
    }
    missing_reasons = {
        field: _missing_reason(field, trailing_eps)
        for field, value in values.items()
        if value is None
    }
    return QuoteSnapshot(
        symbol=symbol.strip().upper(),
        price=price,
        previous_close=previous_close,
        price_change=price_change,
        price_change_percent=price_change_percent,
        market_cap=market_cap,
        trailing_eps=trailing_eps,
        trailing_pe=trailing_pe,
        forward_pe=forward_pe,
        currency=_text(fast_info.get("currency")) or "USD",
        observed_at=observed_at or datetime.now(UTC),
        provider="yahoo",
        missing_reasons=missing_reasons,
    )


def _get(values: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key in values:
            return values[key]
    return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _trailing_pe(
    info: Mapping[str, Any],
    price: Decimal | None,
    trailing_eps: Decimal | None,
) -> Decimal | None:
    provider_value = to_decimal(info.get("trailingPE"))
    if provider_value is not None and provider_value > 0:
        return provider_value
    if price is None or trailing_eps is None or trailing_eps <= 0:
        return None
    return (price / trailing_eps).quantize(RATIO_QUANTUM)


def _price_change(
    price: Decimal | None,
    previous_close: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    if price is None or previous_close is None:
        return None, None
    change = price - previous_close
    if previous_close == 0:
        return change, None
    percent = (change / previous_close * 100).quantize(RATIO_QUANTUM)
    return change, percent


def _missing_reason(field: str, trailing_eps: Decimal | None) -> str:
    if field == "trailing_pe" and trailing_eps is not None and trailing_eps <= 0:
        return "NON_POSITIVE_EPS"
    if field in {"price_change", "price_change_percent"}:
        return "REQUIRED_INPUT_MISSING"
    return "PROVIDER_FIELD_MISSING"
