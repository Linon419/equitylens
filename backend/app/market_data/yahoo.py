import asyncio
from collections.abc import Iterable, Mapping
from typing import Any

import yfinance as yf

from app.market_data.mapper import map_company_profile, map_quote
from app.providers.market import CompanyProfile, QuoteSnapshot, SymbolMatch


def map_search_results(
    rows: Iterable[Mapping[str, Any]],
) -> list[SymbolMatch]:
    matches: list[SymbolMatch] = []
    seen: set[str] = set()
    for row in rows:
        if str(row.get("quoteType", "")).upper() != "EQUITY":
            continue
        symbol = str(row.get("symbol", "")).strip().upper()
        name = str(row.get("longname") or row.get("shortname") or "").strip()
        if not symbol or not name or symbol in seen:
            continue
        exchange = str(row.get("exchange") or "").strip() or None
        matches.append(SymbolMatch(symbol=symbol, name=name, exchange=exchange))
        seen.add(symbol)
        if len(matches) == 8:
            break
    return matches


class YahooMarketDataProvider:
    async def search_symbols(self, query: str) -> list[SymbolMatch]:
        rows = await asyncio.to_thread(
            lambda: yf.Search(query, max_results=8, news_count=0).quotes
        )
        return map_search_results(rows)

    async def get_quote(self, symbol: str) -> QuoteSnapshot:
        def load() -> tuple[dict[str, object], dict[str, object]]:
            ticker = yf.Ticker(symbol)
            return dict(ticker.fast_info), dict(ticker.info)

        fast_info, info = await asyncio.to_thread(load)
        return map_quote(symbol, fast_info=fast_info, info=info)

    async def get_company_profile(self, symbol: str) -> CompanyProfile:
        info = await asyncio.to_thread(lambda: dict(yf.Ticker(symbol).info))
        return map_company_profile(symbol, info)
