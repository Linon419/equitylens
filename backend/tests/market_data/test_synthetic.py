from decimal import Decimal

import pytest

from app.market_data.synthetic import SyntheticMarketDataProvider


@pytest.mark.asyncio
async def test_synthetic_provider_returns_labeled_deterministic_quotes() -> None:
    provider = SyntheticMarketDataProvider()

    first = await provider.get_quote("aapl")
    second = await provider.get_quote("AAPL")

    assert first == second
    assert first.symbol == "AAPL"
    assert first.provider == "synthetic-evaluation-v1"
    assert first.price is not None and first.price > Decimal("0")
    assert first.price_change == first.price - first.previous_close


@pytest.mark.asyncio
async def test_synthetic_provider_searches_its_evaluation_catalog() -> None:
    provider = SyntheticMarketDataProvider()

    matches = await provider.search_symbols("apple")
    profile = await provider.get_company_profile("aapl")

    assert [match.symbol for match in matches] == ["AAPL"]
    assert profile.name == "Apple Inc."
    assert "synthetic evaluation" in (profile.description or "").lower()
