from fastapi import APIRouter, Query

from app.api.deps import MarketDataProviderDep, SecDataProviderDep, SessionDep
from app.companies.schemas import (
    CompanyPublic,
    CompanySearchResponse,
)
from app.companies.service import get_or_create_company, search_companies
from app.market_data.schemas import MarketResponse
from app.market_data.service import get_market_snapshot, refresh_company_profile

router = APIRouter(prefix="/companies")


@router.get("/search", response_model=CompanySearchResponse)
async def search(
    provider: MarketDataProviderDep,
    q: str = Query(max_length=64),
) -> CompanySearchResponse:
    items = await search_companies(provider, q)
    return CompanySearchResponse(items=items, count=len(items))


@router.get("/{symbol}", response_model=CompanyPublic)
async def get_company(
    symbol: str,
    session: SessionDep,
    sec_provider: SecDataProviderDep,
    market_provider: MarketDataProviderDep,
) -> CompanyPublic:
    company = await get_or_create_company(session, sec_provider, symbol)
    company = await refresh_company_profile(session, company, market_provider)
    return CompanyPublic.model_validate(company)


@router.get("/{symbol}/market", response_model=MarketResponse)
async def get_company_market(
    symbol: str,
    session: SessionDep,
    sec_provider: SecDataProviderDep,
    market_provider: MarketDataProviderDep,
) -> MarketResponse:
    company = await get_or_create_company(session, sec_provider, symbol)
    result = await get_market_snapshot(session, company, market_provider)
    return MarketResponse.from_snapshot(
        company.symbol,
        result.snapshot,
        result.freshness,
    )
