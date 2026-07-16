from collections.abc import Callable, Mapping
from typing import Any

from app.chat.market_analysis_skills import MarketAnalysisSkill
from app.chat.yahoo_market_data import (
    BALANCE_ROWS,
    CASH_FLOW_ROWS,
    INCOME_ROWS,
    history,
    history_rows,
    json_safe,
    quote_payload,
    read,
    statement,
    table,
)
from app.chat.yahoo_market_metrics import (
    correlation_payload,
    etf_payload,
    liquidity_payload,
    options_payload,
    sepa_payload,
)


def build_skill_payload(
    skill: MarketAnalysisSkill,
    *,
    ticker: Any,
    ticker_factory: Callable[[str], Any],
    info: Mapping[str, Any],
    fast_info: Mapping[str, Any],
    question: str,
    symbol: str,
) -> dict[str, Any]:
    quote = quote_payload(info, fast_info)
    if skill == "company-valuation":
        return _valuation_payload(ticker, quote)
    if skill == "earnings-preview":
        return _earnings_preview_payload(ticker, quote)
    if skill == "earnings-recap":
        return _earnings_recap_payload(ticker, quote)
    if skill == "estimate-analysis":
        return _estimate_payload(ticker, quote)
    if skill == "etf-premium":
        return etf_payload(quote)
    if skill == "options-payoff":
        return options_payload(ticker, quote)
    if skill == "saas-valuation-compression":
        return _saas_payload(quote)
    if skill == "sepa-strategy":
        return sepa_payload(
            ticker,
            benchmark=ticker_factory("SPY"),
            quote=quote,
        )
    if skill == "stock-correlation":
        return correlation_payload(
            ticker_factory=ticker_factory,
            primary_ticker=ticker,
            primary_symbol=symbol,
            question=question,
            info=info,
        )
    if skill == "stock-liquidity":
        return liquidity_payload(ticker, quote)
    return _general_yahoo_payload(ticker, quote)


def _valuation_payload(ticker: Any, quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "quote": quote,
        "annual_income": statement(read(ticker, "income_stmt"), INCOME_ROWS),
        "annual_cash_flow": statement(read(ticker, "cashflow"), CASH_FLOW_ROWS),
        "annual_balance_sheet": statement(read(ticker, "balance_sheet"), BALANCE_ROWS),
        "earnings_estimates": table(read(ticker, "earnings_estimate")),
        "revenue_estimates": table(read(ticker, "revenue_estimate")),
        "growth_estimates": table(read(ticker, "growth_estimates")),
        "default_assumptions": {
            "projection_years": 5,
            "terminal_growth": 0.025,
            "equity_risk_premium": 0.055,
            "scenario_growth_shift": 0.03,
            "scenario_margin_shift": 0.02,
            "wacc_sensitivity_shift": 0.01,
        },
    }


def _earnings_preview_payload(ticker: Any, quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "quote": quote,
        "calendar": json_safe(read(ticker, "calendar", {})),
        "earnings_estimates": table(read(ticker, "earnings_estimate")),
        "revenue_estimates": table(read(ticker, "revenue_estimate")),
        "earnings_history": table(read(ticker, "earnings_history")),
        "eps_trend": table(read(ticker, "eps_trend")),
        "recommendations": table(read(ticker, "recommendations_summary")),
        "analyst_price_targets": json_safe(read(ticker, "analyst_price_targets", {})),
    }


def _earnings_recap_payload(ticker: Any, quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "quote": quote,
        "earnings_dates": table(read(ticker, "earnings_dates")),
        "quarterly_income": statement(
            read(ticker, "quarterly_income_stmt"), INCOME_ROWS
        ),
        "quarterly_cash_flow": statement(
            read(ticker, "quarterly_cashflow"), CASH_FLOW_ROWS
        ),
        "recent_price_history": history_rows(history(ticker, period="3mo"), limit=70),
    }


def _estimate_payload(ticker: Any, quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "quote": quote,
        "earnings_estimates": table(read(ticker, "earnings_estimate")),
        "revenue_estimates": table(read(ticker, "revenue_estimate")),
        "eps_trend": table(read(ticker, "eps_trend")),
        "eps_revisions": table(read(ticker, "eps_revisions")),
        "growth_estimates": table(read(ticker, "growth_estimates")),
        "earnings_history": table(read(ticker, "earnings_history")),
    }


def _saas_payload(quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "quote": quote,
        "web_evidence_required": [
            "dated funding-round valuations",
            "ARR at each comparable date",
            "lead investors and primary announcements",
            "public SaaS peer multiples",
        ],
    }


def _general_yahoo_payload(ticker: Any, quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "quote": quote,
        "annual_income": statement(read(ticker, "income_stmt"), INCOME_ROWS),
        "annual_cash_flow": statement(read(ticker, "cashflow"), CASH_FLOW_ROWS),
        "annual_balance_sheet": statement(read(ticker, "balance_sheet"), BALANCE_ROWS),
        "actions": table(read(ticker, "actions"), limit=12),
    }
