from sqlmodel import Session, select

from app.companies.service import get_or_create_company, normalize_symbol
from app.models.company_model import Company, Watchlist
from app.models.market_model import MarketSnapshot
from app.providers.sec import SecDataProvider
from app.watchlist.schemas import WatchlistItem


def list_watchlist(session: Session, user_id: int) -> list[WatchlistItem]:
    rows = session.exec(
        select(Watchlist, Company)
        .join(Company, Company.id == Watchlist.company_id)
        .where(Watchlist.user_id == user_id)
        .order_by(Watchlist.created_at.desc(), Company.symbol.asc())
    ).all()
    return [
        _to_item(session, watchlist, company)
        for watchlist, company in rows
    ]


async def add_to_watchlist(
    session: Session,
    user_id: int,
    raw_symbol: str,
    provider: SecDataProvider,
) -> Watchlist:
    company = await get_or_create_company(session, provider, raw_symbol)
    existing = session.exec(
        select(Watchlist).where(
            Watchlist.user_id == user_id,
            Watchlist.company_id == company.id,
        )
    ).first()
    if existing is not None:
        return existing

    watchlist = Watchlist(user_id=user_id, company_id=company.id)
    session.add(watchlist)
    session.commit()
    session.refresh(watchlist)
    return watchlist


def remove_from_watchlist(
    session: Session,
    user_id: int,
    raw_symbol: str,
) -> bool:
    symbol = normalize_symbol(raw_symbol)
    watchlist = session.exec(
        select(Watchlist)
        .join(Company, Company.id == Watchlist.company_id)
        .where(
            Watchlist.user_id == user_id,
            Company.symbol == symbol,
        )
    ).first()
    if watchlist is None:
        return False
    session.delete(watchlist)
    session.commit()
    return True


def _to_item(
    session: Session,
    watchlist: Watchlist,
    company: Company,
) -> WatchlistItem:
    market = session.exec(
        select(MarketSnapshot)
        .where(MarketSnapshot.company_id == company.id)
        .order_by(MarketSnapshot.fetched_at.desc())
    ).first()
    return WatchlistItem(
        symbol=company.symbol,
        name=company.name,
        exchange=company.exchange,
        price=market.price if market else None,
        trailing_pe=market.trailing_pe if market else None,
        added_at=watchlist.created_at,
    )
