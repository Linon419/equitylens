from unittest.mock import MagicMock

from app.api import deps
from app.core.config import MarketDataProviderName
from app.market_data.synthetic import SyntheticMarketDataProvider


def test_synthetic_profile_selects_local_market_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        deps.settings,
        "MARKET_DATA_PROVIDER",
        MarketDataProviderName.SYNTHETIC,
    )

    provider = deps.get_market_data_provider()

    assert isinstance(provider, SyntheticMarketDataProvider)


def test_synthetic_profile_disables_direct_yahoo_chat_collection(monkeypatch) -> None:
    monkeypatch.setattr(
        deps.settings,
        "MARKET_DATA_PROVIDER",
        MarketDataProviderName.SYNTHETIC,
    )

    pipeline = deps.get_chat_evidence_pipeline(
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )

    assert pipeline._market_analysis is None
