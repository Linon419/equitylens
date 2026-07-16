import math
from collections.abc import Mapping
from typing import Any

QUOTE_FIELDS = (
    "currentPrice",
    "regularMarketPrice",
    "previousClose",
    "currency",
    "marketCap",
    "enterpriseValue",
    "sharesOutstanding",
    "floatShares",
    "trailingEps",
    "forwardEps",
    "trailingPE",
    "forwardPE",
    "priceToBook",
    "enterpriseToRevenue",
    "enterpriseToEbitda",
    "beta",
    "totalRevenue",
    "ebitda",
    "freeCashflow",
    "operatingCashflow",
    "totalCash",
    "totalDebt",
    "revenueGrowth",
    "earningsGrowth",
    "grossMargins",
    "operatingMargins",
    "profitMargins",
    "fiftyTwoWeekHigh",
    "fiftyTwoWeekLow",
    "fiftyDayAverage",
    "twoHundredDayAverage",
    "averageVolume",
    "averageDailyVolume10Day",
    "bid",
    "ask",
    "bidSize",
    "askSize",
    "navPrice",
    "sector",
    "industry",
)
INCOME_ROWS = (
    "Total Revenue",
    "Gross Profit",
    "Operating Income",
    "EBIT",
    "EBITDA",
    "Net Income",
    "Diluted EPS",
)
CASH_FLOW_ROWS = (
    "Operating Cash Flow",
    "Capital Expenditure",
    "Free Cash Flow",
    "Depreciation And Amortization",
    "Change In Working Capital",
    "Stock Based Compensation",
)
BALANCE_ROWS = (
    "Cash Cash Equivalents And Short Term Investments",
    "Total Debt",
    "Stockholders Equity",
)


def read(value: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(value, name)
    except Exception:
        return default


def mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def quote_payload(
    info: Mapping[str, Any],
    fast_info: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {key: json_safe(info[key]) for key in QUOTE_FIELDS if key in info}
    if "currentPrice" not in payload:
        for key in ("lastPrice", "last_price"):
            if key in fast_info:
                payload["currentPrice"] = json_safe(fast_info[key])
                break
    return payload


def history(ticker: Any, *, period: str) -> Any:
    return ticker.history(period=period, interval="1d", auto_adjust=True)


def history_rows(frame: Any, *, limit: int) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    columns = [
        name for name in ("Open", "High", "Low", "Close", "Volume") if name in frame
    ]
    return table(frame[columns].tail(limit), limit=limit)


def statement(frame: Any, rows: tuple[str, ...]) -> dict[str, list[dict[str, Any]]]:
    if frame is None or getattr(frame, "empty", True):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for row_name in rows:
        if row_name not in frame.index:
            continue
        series = frame.loc[row_name]
        result[row_name] = [
            {"period": index_label(period), "value": json_safe(value)}
            for period, value in list(series.items())[:4]
        ]
    return result


def table(
    frame: Any,
    *,
    limit: int = 8,
    sort_by: str | None = None,
) -> list[dict[str, Any]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    view = frame
    if sort_by and sort_by in view.columns:
        view = view.sort_values(sort_by, ascending=False)
    result = []
    for index, row in view.head(limit).iterrows():
        item = {"period": index_label(index)}
        item.update({str(key): json_safe(value) for key, value in row.items()})
        result.append(item)
    return result


def column(frame: Any, name: str) -> Any | None:
    if frame is None or getattr(frame, "empty", True) or name not in frame:
        return None
    return frame[name].dropna()


def close_returns(frame: Any) -> Any | None:
    close = column(frame, "Close")
    if close is None or close.empty:
        return None
    return close.pct_change(fill_method=None).dropna()


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except (TypeError, ValueError):
            pass
    return str(value)


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rounded(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def last_float(series: Any | None) -> float | None:
    if series is None or getattr(series, "empty", True):
        return None
    return number(series.iloc[-1])


def tail_mean(series: Any | None, periods: int) -> float | None:
    if series is None or getattr(series, "empty", True):
        return None
    return rounded(number(series.tail(periods).mean()), 4)


def slice_mean(series: Any | None, start: int, end: int) -> float | None:
    if series is None or len(series) < abs(start):
        return None
    return rounded(number(series.iloc[start:end].mean()), 4)


def tail_std(series: Any | None, periods: int) -> float | None:
    if series is None or getattr(series, "empty", True):
        return None
    return rounded(number(series.tail(periods).std()), 6)


def period_return(series: Any | None, periods: int) -> float | None:
    if series is None or len(series) < 2:
        return None
    window = series.tail(periods)
    start = number(window.iloc[0])
    end = number(window.iloc[-1])
    if start in {None, 0.0} or end is None:
        return None
    return rounded(end / start - 1, 6)


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0.0}:
        return None
    return numerator / denominator


def index_label(value: Any) -> str:
    return str(json_safe(value))
