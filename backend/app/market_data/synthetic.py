"""Deterministic market data for evaluation environments.

All prices, ratios, capitalization values, and descriptions produced here are
fabricated. The catalog contains public identifiers and names plus hand-authored
coarse category labels.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256

from app.providers.market import CompanyProfile, QuoteSnapshot, SymbolMatch

PROVIDER_NAME = "synthetic-evaluation-v1"
OBSERVED_AT = datetime(2026, 7, 15, 20, tzinfo=UTC)
MONEY = Decimal("0.01")
RATIO = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class EvaluationCompany:
    name: str
    exchange: str
    sector: str
    industry: str


EVALUATION_CATALOG = {
    "AAPL": EvaluationCompany(
        "Apple Inc.", "Nasdaq", "Technology", "Consumer electronics"
    ),
    "AMZN": EvaluationCompany(
        "Amazon.com, Inc.", "Nasdaq", "Consumer", "Internet retail"
    ),
    "COST": EvaluationCompany(
        "Costco Wholesale Corporation", "Nasdaq", "Consumer", "Retail"
    ),
    "GOOGL": EvaluationCompany(
        "Alphabet Inc.", "Nasdaq", "Communication services", "Internet services"
    ),
    "JPM": EvaluationCompany(
        "JPMorgan Chase & Co.", "NYSE", "Financials", "Banking"
    ),
    "META": EvaluationCompany(
        "Meta Platforms, Inc.", "Nasdaq", "Communication services", "Internet services"
    ),
    "MSFT": EvaluationCompany(
        "Microsoft Corporation", "Nasdaq", "Technology", "Software"
    ),
    "NFLX": EvaluationCompany(
        "Netflix, Inc.", "Nasdaq", "Communication services", "Entertainment"
    ),
    "NVDA": EvaluationCompany(
        "NVIDIA Corporation", "Nasdaq", "Technology", "Semiconductors"
    ),
    "TSLA": EvaluationCompany(
        "Tesla, Inc.", "Nasdaq", "Consumer", "Automotive"
    ),
    "XOM": EvaluationCompany(
        "Exxon Mobil Corporation", "NYSE", "Energy", "Integrated energy"
    ),
}


class SyntheticMarketDataProvider:
    """Serve reproducible fabricated values without external market-data calls."""

    provider_name = PROVIDER_NAME

    async def search_symbols(self, query: str) -> list[SymbolMatch]:
        normalized = query.strip().casefold()
        return [
            SymbolMatch(symbol, company.name, company.exchange)
            for symbol, company in EVALUATION_CATALOG.items()
            if normalized in symbol.casefold() or normalized in company.name.casefold()
        ][:8]

    async def get_quote(self, symbol: str) -> QuoteSnapshot:
        normalized = _normalize_symbol(symbol)
        seed = int.from_bytes(sha256(normalized.encode()).digest()[:8])
        price = (Decimal(5_000 + seed % 35_000) / 100).quantize(MONEY)
        change = (Decimal((seed >> 8) % 1_001) / 100 - Decimal("5")).quantize(
            MONEY
        )
        previous_close = max(price - change, MONEY)
        trailing_pe = (Decimal("12") + Decimal((seed >> 16) % 2_400) / 100).quantize(
            RATIO
        )
        trailing_eps = (price / trailing_pe).quantize(RATIO)
        forward_pe = (trailing_pe * Decimal("0.94")).quantize(RATIO)
        shares = Decimal(500_000_000 + (seed >> 24) % 15_000_000_000)
        price_change_percent = (change / previous_close * 100).quantize(RATIO)
        return QuoteSnapshot(
            symbol=normalized,
            price=price,
            previous_close=previous_close,
            market_cap=(price * shares).quantize(MONEY),
            trailing_eps=trailing_eps,
            trailing_pe=trailing_pe,
            forward_pe=forward_pe,
            currency="USD",
            observed_at=OBSERVED_AT,
            provider=PROVIDER_NAME,
            missing_reasons={},
            price_change=change,
            price_change_percent=price_change_percent,
        )

    async def get_company_profile(self, symbol: str) -> CompanyProfile:
        normalized = _normalize_symbol(symbol)
        company = EVALUATION_CATALOG[normalized]
        return CompanyProfile(
            symbol=normalized,
            name=company.name,
            sector=company.sector,
            industry=company.industry,
            description=(
                f"{company.name} synthetic evaluation profile. "
                "All market metrics and narrative fields are fabricated."
            ),
        )


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol is required")
    return normalized
