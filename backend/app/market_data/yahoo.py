import asyncio
from collections.abc import Iterable, Mapping
from typing import Any

import yfinance as yf

from app.providers.market import SymbolMatch


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
