from fastapi import APIRouter

from app.api.deps import CurrentUser, SecDataProviderDep, SessionDep
from app.core.errors import DomainError
from app.watchlist.schemas import WatchlistMutation, WatchlistResponse
from app.watchlist.service import (
    add_to_watchlist,
    list_watchlist,
    remove_from_watchlist,
)

router = APIRouter(prefix="/watchlist")


def _user_id(current_user: CurrentUser) -> int:
    if current_user.id is None:
        raise DomainError("AUTH_REQUIRED", 401)
    return current_user.id


@router.get("", response_model=WatchlistResponse)
def get_watchlist(
    session: SessionDep,
    current_user: CurrentUser,
) -> WatchlistResponse:
    items = list_watchlist(session, _user_id(current_user))
    return WatchlistResponse(items=items, count=len(items))


@router.post("/{symbol}", response_model=WatchlistMutation)
async def add_watchlist_company(
    symbol: str,
    session: SessionDep,
    current_user: CurrentUser,
    provider: SecDataProviderDep,
) -> WatchlistMutation:
    await add_to_watchlist(
        session,
        _user_id(current_user),
        symbol,
        provider,
    )
    return WatchlistMutation(symbol=symbol.strip().upper(), in_watchlist=True)


@router.delete("/{symbol}", response_model=WatchlistMutation)
def delete_watchlist_company(
    symbol: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> WatchlistMutation:
    remove_from_watchlist(session, _user_id(current_user), symbol)
    return WatchlistMutation(symbol=symbol.strip().upper(), in_watchlist=False)
