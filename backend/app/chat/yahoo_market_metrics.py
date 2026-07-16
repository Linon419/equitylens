import re
from collections.abc import Callable, Mapping
from typing import Any

from app.chat.yahoo_market_data import (
    close_returns,
    column,
    history,
    last_float,
    number,
    period_return,
    ratio,
    rounded,
    slice_mean,
    table,
    tail_mean,
    tail_std,
)

_TICKER_STOP_WORDS = {
    "ADV",
    "ARR",
    "DCF",
    "DTE",
    "EPS",
    "ETF",
    "FCF",
    "NAV",
    "PE",
    "SEPA",
    "SOTP",
    "TTM",
    "USD",
    "VCP",
}


def etf_payload(quote: dict[str, Any]) -> dict[str, Any]:
    price = number(quote.get("currentPrice"))
    nav = number(quote.get("navPrice"))
    bid = number(quote.get("bid"))
    ask = number(quote.get("ask"))
    premium = (price - nav) / nav * 100 if price is not None and nav else None
    spread = None
    if bid is not None and ask is not None and bid + ask > 0:
        spread = (ask - bid) / ((ask + bid) / 2) * 100
    return {
        "quote": quote,
        "premium_discount_percent": rounded(premium),
        "spread_percent": rounded(spread),
        "formula": "(market_price - nav) / nav * 100",
    }


def options_payload(ticker: Any, quote: dict[str, Any]) -> dict[str, Any]:
    try:
        expirations = list(ticker.options or ())[:6]
    except Exception:
        expirations = []
    chain_payload: dict[str, Any] | None = None
    if expirations:
        chain = ticker.option_chain(expirations[0])
        chain_payload = {
            "expiration": expirations[0],
            "calls_by_open_interest": table(
                getattr(chain, "calls", None), limit=12, sort_by="openInterest"
            ),
            "puts_by_open_interest": table(
                getattr(chain, "puts", None), limit=12, sort_by="openInterest"
            ),
        }
    return {
        "quote": quote,
        "available_expirations": expirations,
        "nearest_chain": chain_payload,
        "required_user_inputs": [
            "option type and long/short direction",
            "strike, premium, quantity and expiration for each leg",
        ],
    }


def sepa_payload(
    ticker: Any,
    *,
    benchmark: Any,
    quote: dict[str, Any],
) -> dict[str, Any]:
    market_history = history(ticker, period="2y")
    close = column(market_history, "Close")
    volume = column(market_history, "Volume")
    benchmark_close = column(history(benchmark, period="1y"), "Close")
    if close is None or close.empty:
        return {"quote": quote, "technical_data": None}
    price = last_float(close)
    ma50 = tail_mean(close, 50)
    ma150 = tail_mean(close, 150)
    ma200 = tail_mean(close, 200)
    previous_ma200 = slice_mean(close, -220, -20)
    window = close.tail(252)
    high_52 = number(window.max())
    low_52 = number(window.min())
    stock_return = period_return(close, 252)
    benchmark_return = period_return(benchmark_close, 252)
    recent_returns = close.pct_change(fill_method=None).dropna()
    return {
        "quote": quote,
        "moving_averages": {"sma_50": ma50, "sma_150": ma150, "sma_200": ma200},
        "52_week": {"high": high_52, "low": low_52},
        "trend_template": _trend_template(
            price=price,
            ma50=ma50,
            ma150=ma150,
            ma200=ma200,
            previous_ma200=previous_ma200,
            low_52=low_52,
            high_52=high_52,
            stock_return=stock_return,
            benchmark_return=benchmark_return,
        ),
        "volatility_contraction": {
            "return_volatility_60d": tail_std(recent_returns, 60),
            "return_volatility_30d": tail_std(recent_returns, 30),
            "return_volatility_15d": tail_std(recent_returns, 15),
            "latest_volume_to_50d_average": ratio(
                last_float(volume), tail_mean(volume, 50)
            ),
        },
        "returns": {"stock_12m": stock_return, "spy_12m": benchmark_return},
    }


def correlation_payload(
    *,
    ticker_factory: Callable[[str], Any],
    primary_ticker: Any,
    primary_symbol: str,
    question: str,
    info: Mapping[str, Any],
) -> dict[str, Any]:
    symbols = _question_tickers(question, primary_symbol)
    comparisons = [symbol for symbol in symbols if symbol != primary_symbol]
    if not comparisons:
        comparisons = _default_peers(info, primary_symbol)
    base = close_returns(history(primary_ticker, period="1y"))
    pairs = [
        pair
        for symbol in comparisons[:5]
        if (
            pair := _correlation_pair(
                base,
                close_returns(history(ticker_factory(symbol), period="1y")),
                symbol,
            )
        )
        is not None
    ]
    return {
        "primary_symbol": primary_symbol,
        "lookback": "1y daily adjusted closes",
        "pairs": pairs,
        "limitations": [
            "correlation is historical and regime-dependent",
            "pair relationships do not establish causation",
        ],
    }


def liquidity_payload(ticker: Any, quote: dict[str, Any]) -> dict[str, Any]:
    market_history = history(ticker, period="6mo")
    close = column(market_history, "Close")
    volume = column(market_history, "Volume")
    bid = number(quote.get("bid"))
    ask = number(quote.get("ask"))
    spread = None
    if bid is not None and ask is not None and bid + ask > 0:
        spread = (ask - bid) / ((ask + bid) / 2) * 100
    adv20 = tail_mean(volume, 20)
    adv60 = tail_mean(volume, 60)
    dollar_volume = close * volume if close is not None and volume is not None else None
    addv20 = tail_mean(dollar_volume, 20)
    float_shares = number(quote.get("floatShares"))
    return {
        "quote": quote,
        "spread_percent": rounded(spread),
        "average_daily_volume_20d": rounded(adv20, 2),
        "average_daily_volume_60d": rounded(adv60, 2),
        "average_daily_dollar_volume_20d": rounded(addv20, 2),
        "latest_relative_volume_to_20d": rounded(ratio(last_float(volume), adv20)),
        "daily_turnover_percent": rounded(
            adv20 / float_shares * 100
            if adv20 is not None and float_shares not in {None, 0.0}
            else None
        ),
        "amihud_illiquidity_scaled_1m": rounded(_amihud(close, dollar_volume), 8),
        "limitations": [
            "top-of-book and daily-volume proxies only",
            "market impact requires an order size and remains model-based",
        ],
    }


def _correlation_pair(base: Any, compared: Any, symbol: str) -> dict | None:
    if base is None or compared is None:
        return None
    correlation = number(base.corr(compared))
    variance = number(compared.var())
    covariance = number(base.cov(compared))
    beta = covariance / variance if covariance is not None and variance else None
    rolling = base.rolling(60).corr(compared).dropna()
    return {
        "comparison_symbol": symbol,
        "pearson_correlation": rounded(correlation),
        "r_squared": rounded(
            correlation * correlation if correlation is not None else None
        ),
        "beta_to_comparison": rounded(beta),
        "latest_60d_correlation": rounded(last_float(rolling)),
        "observations": int(base.align(compared, join="inner")[0].count()),
    }


def _amihud(close: Any, dollar_volume: Any) -> float | None:
    if close is None or dollar_volume is None:
        return None
    returns = close.pct_change(fill_method=None).abs()
    aligned_returns, aligned_volume = returns.align(dollar_volume, join="inner")
    valid = aligned_volume > 0
    values = (aligned_returns[valid] / aligned_volume[valid]).dropna()
    return number(values.mean() * 1_000_000) if not values.empty else None


def _trend_template(**values: float | None) -> dict[str, bool | None]:
    return {
        "price_above_150_and_200": _all_greater(
            values["price"], values["ma150"], values["ma200"]
        ),
        "sma_150_above_200": _greater(values["ma150"], values["ma200"]),
        "sma_200_rising": _greater(values["ma200"], values["previous_ma200"]),
        "sma_50_above_150_and_200": _all_greater(
            values["ma50"], values["ma150"], values["ma200"]
        ),
        "price_above_50": _greater(values["price"], values["ma50"]),
        "price_30_percent_above_52w_low": _ratio_at_least(
            values["price"], values["low_52"], 1.30
        ),
        "price_within_25_percent_of_52w_high": _ratio_at_least(
            values["price"], values["high_52"], 0.75
        ),
        "outperformed_spy_12m": _greater(
            values["stock_return"], values["benchmark_return"]
        ),
    }


def _question_tickers(question: str, primary_symbol: str) -> list[str]:
    symbols = [primary_symbol]
    for match in re.findall(
        r"(?<![A-Za-z0-9.])[A-Z][A-Z0-9.-]{0,5}(?![A-Za-z0-9.])", question
    ):
        if match not in _TICKER_STOP_WORDS and match not in symbols:
            symbols.append(match)
    return symbols[:6]


def _default_peers(info: Mapping[str, Any], primary_symbol: str) -> list[str]:
    text = f"{info.get('industry', '')} {info.get('sector', '')}".casefold()
    peer_sets = (
        (("semiconductor",), ("NVDA", "AMD", "AVGO", "MU", "INTC")),
        (("software",), ("MSFT", "ORCL", "CRM", "NOW", "ADBE")),
        (("bank", "financial"), ("JPM", "BAC", "WFC", "C", "GS")),
        (("oil", "energy"), ("XOM", "CVX", "COP", "EOG", "SLB")),
        (
            ("computer hardware", "consumer electronics"),
            ("AAPL", "DELL", "HPQ", "WDC", "STX"),
        ),
    )
    for markers, peers in peer_sets:
        if any(marker in text for marker in markers):
            return [peer for peer in peers if peer != primary_symbol]
    return [peer for peer in ("SPY", "QQQ") if peer != primary_symbol]


def _greater(left: float | None, right: float | None) -> bool | None:
    return left > right if left is not None and right is not None else None


def _all_greater(left: float | None, *rights: float | None) -> bool | None:
    if left is None or any(right is None for right in rights):
        return None
    return all(left > right for right in rights if right is not None)


def _ratio_at_least(
    numerator: float | None,
    denominator: float | None,
    threshold: float,
) -> bool | None:
    value = ratio(numerator, denominator)
    return value >= threshold if value is not None else None
