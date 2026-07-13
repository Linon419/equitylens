from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class WatchlistItem(BaseModel):
    symbol: str
    name: str
    exchange: str | None
    price: Decimal | None
    trailing_pe: Decimal | None
    added_at: datetime


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    count: int


class WatchlistMutation(BaseModel):
    symbol: str
    in_watchlist: bool
