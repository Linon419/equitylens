from datetime import UTC, datetime

import pandas as pd
import pytest

from app.chat.yahoo_market_analysis import YahooMarketAnalysisProvider
from app.models.company_model import Company

NOW = datetime(2026, 7, 15, 12, tzinfo=UTC)


class FakeTicker:
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        self.info = {
            "currentPrice": 110.0 if symbol == "AAPL" else 55.0,
            "previousClose": 108.0,
            "marketCap": 1_000_000_000,
            "sharesOutstanding": 10_000_000,
            "floatShares": 8_000_000,
            "bid": 109.9,
            "ask": 110.1,
            "navPrice": 100.0,
            "averageVolume": 1_000_000,
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "totalCash": 100_000_000,
            "totalDebt": 50_000_000,
            "beta": 1.1,
            "freeCashflow": 80_000_000,
        }
        self.fast_info = {"lastPrice": self.info["currentPrice"]}
        self.income_stmt = pd.DataFrame(
            {
                pd.Timestamp("2025-09-30"): {
                    "Total Revenue": 500_000_000,
                    "Operating Income": 100_000_000,
                    "Net Income": 75_000_000,
                }
            }
        )
        self.cashflow = pd.DataFrame(
            {
                pd.Timestamp("2025-09-30"): {
                    "Free Cash Flow": 80_000_000,
                    "Operating Cash Flow": 95_000_000,
                    "Capital Expenditure": -15_000_000,
                }
            }
        )
        self.balance_sheet = pd.DataFrame()
        self.quarterly_income_stmt = pd.DataFrame()
        self.quarterly_cashflow = pd.DataFrame()
        self.calendar = {}
        self.earnings_estimate = pd.DataFrame()
        self.revenue_estimate = pd.DataFrame()
        self.earnings_history = pd.DataFrame()
        self.earnings_dates = pd.DataFrame()
        self.eps_trend = pd.DataFrame()
        self.eps_revisions = pd.DataFrame()
        self.growth_estimates = pd.DataFrame()
        self.recommendations_summary = pd.DataFrame()
        self.analyst_price_targets = {}
        self.options = ()

    def history(self, **kwargs):
        del kwargs
        index = pd.date_range("2026-01-01", periods=80, freq="B", tz="UTC")
        start = 100.0 if self.symbol == "AAPL" else 50.0
        step = 1.0 if self.symbol == "AAPL" else 0.5
        return pd.DataFrame(
            {
                "Close": [start + index * step for index in range(80)],
                "Volume": [900_000 + index * 1_000 for index in range(80)],
            },
            index=index,
        )


@pytest.mark.asyncio
async def test_yahoo_provider_returns_skill_scoped_citable_evidence() -> None:
    provider = YahooMarketAnalysisProvider(FakeTicker, now=lambda: NOW)
    company = Company(id=1, symbol="AAPL", cik="0000320193", name="Apple Inc.")

    records = await provider.collect(
        company=company,
        question="Is AAPL liquid and is its ETF price above NAV?",
        skills=["stock-liquidity", "etf-premium"],
    )

    assert [record.candidate.source_id for record in records] == [
        "stock-liquidity:AAPL",
        "etf-premium:AAPL",
    ]
    assert all(record.company_id == 1 for record in records)
    assert all(record.candidate.source_kind == "financial" for record in records)
    assert all(
        record.candidate.source_url == "https://finance.yahoo.com/quote/AAPL"
        for record in records
    )
    assert '"average_daily_dollar_volume_20d"' in records[0].source_text
    assert '"premium_discount_percent":10.0' in records[1].source_text
    assert '"spread_percent"' in records[1].source_text


@pytest.mark.asyncio
async def test_yahoo_provider_computes_pair_correlation_from_question_tickers() -> None:
    provider = YahooMarketAnalysisProvider(FakeTicker, now=lambda: NOW)
    company = Company(id=1, symbol="AAPL", cik="0000320193", name="Apple Inc.")

    records = await provider.collect(
        company=company,
        question="Compare the return correlation between AAPL and MSFT",
        skills=["stock-correlation"],
    )

    assert len(records) == 1
    assert '"comparison_symbol":"MSFT"' in records[0].source_text
    assert '"pearson_correlation":1.0' in records[0].source_text
    assert '"lookback":"1y daily adjusted closes"' in records[0].source_text
