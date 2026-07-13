import re

from sqlmodel import Session, select

from app.companies.schemas import CompanySearchItem
from app.core.errors import DomainError
from app.models.company_model import Company
from app.providers.market import MarketDataProvider
from app.providers.sec import SecDataProvider

SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,15}$")


def normalize_symbol(raw_symbol: str) -> str:
    symbol = raw_symbol.strip().upper()
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise DomainError("COMPANY_SYMBOL_INVALID", 422)
    return symbol


def normalize_search_query(raw_query: str) -> str:
    query = " ".join(raw_query.split())
    if len(query) < 2 or len(query) > 64:
        raise DomainError("COMPANY_SEARCH_QUERY_INVALID", 422)
    return query


async def search_companies(
    provider: MarketDataProvider,
    raw_query: str,
) -> list[CompanySearchItem]:
    query = normalize_search_query(raw_query)
    matches = await provider.search_symbols(query)
    items: list[CompanySearchItem] = []
    for match in matches[:8]:
        try:
            symbol = normalize_symbol(match.symbol)
        except DomainError:
            continue
        items.append(
            CompanySearchItem(
                symbol=symbol,
                name=match.name.strip(),
                exchange=match.exchange,
            )
        )
    return items


async def get_or_create_company(
    session: Session,
    provider: SecDataProvider,
    raw_symbol: str,
) -> Company:
    symbol = normalize_symbol(raw_symbol)
    existing = session.exec(
        select(Company).where(Company.symbol == symbol)
    ).first()
    if existing is not None:
        return existing

    reference = await provider.resolve_company(symbol)
    company = Company(
        symbol=reference.symbol,
        cik=reference.cik,
        name=reference.name,
        exchange=reference.exchange,
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    return company
