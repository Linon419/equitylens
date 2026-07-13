from fastapi import APIRouter, Query

from app.api.deps import MarketDataProviderDep, SecDataProviderDep, SessionDep
from app.companies.schemas import (
    CompanyPublic,
    CompanySearchResponse,
)
from app.companies.service import get_or_create_company, search_companies

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
    provider: SecDataProviderDep,
) -> CompanyPublic:
    company = await get_or_create_company(session, provider, symbol)
    return CompanyPublic.model_validate(company)
