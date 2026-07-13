from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.models.market_model import MarketSnapshot


class MarketMetric(BaseModel):
    value: Decimal | None
    missing_reason: str | None = None


class MarketResponse(BaseModel):
    symbol: str
    price: MarketMetric
    previous_close: MarketMetric
    price_change: MarketMetric
    price_change_percent: MarketMetric
    market_cap: MarketMetric
    trailing_eps: MarketMetric
    trailing_pe: MarketMetric
    forward_pe: MarketMetric
    currency: str
    provider: str
    observed_at: datetime
    fetched_at: datetime
    freshness: Literal["fresh", "stale"]

    @classmethod
    def from_snapshot(
        cls,
        symbol: str,
        snapshot: MarketSnapshot,
        freshness: Literal["fresh", "stale"],
    ) -> "MarketResponse":
        reasons = snapshot.missing_reasons

        def metric(field: str) -> MarketMetric:
            return MarketMetric(
                value=getattr(snapshot, field),
                missing_reason=reasons.get(field),
            )

        return cls(
            symbol=symbol,
            price=metric("price"),
            previous_close=metric("previous_close"),
            price_change=metric("price_change"),
            price_change_percent=metric("price_change_percent"),
            market_cap=metric("market_cap"),
            trailing_eps=metric("trailing_eps"),
            trailing_pe=metric("trailing_pe"),
            forward_pe=metric("forward_pe"),
            currency=snapshot.currency,
            provider=snapshot.provider,
            observed_at=snapshot.observed_at,
            fetched_at=snapshot.fetched_at,
            freshness=freshness,
        )
