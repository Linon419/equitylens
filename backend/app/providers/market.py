from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class SymbolMatch:
    symbol: str
    name: str
    exchange: str | None


@dataclass(frozen=True)
class CompanyProfile:
    symbol: str
    name: str
    sector: str | None
    industry: str | None
    description: str | None


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    price: Decimal | None
    previous_close: Decimal | None
    market_cap: Decimal | None
    trailing_eps: Decimal | None
    trailing_pe: Decimal | None
    forward_pe: Decimal | None
    currency: str
    observed_at: datetime
    provider: str
    missing_reasons: dict[str, str]
    price_change: Decimal | None = None
    price_change_percent: Decimal | None = None


class MarketDataProvider(Protocol):
    provider_name: str

    async def search_symbols(self, query: str) -> list[SymbolMatch]: ...

    async def get_quote(self, symbol: str) -> QuoteSnapshot: ...

    async def get_company_profile(self, symbol: str) -> CompanyProfile: ...
