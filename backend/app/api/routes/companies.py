from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import (
    AgentPrincipal,
    GraphSynchronizationServicesDep,
    JobBackendDep,
    MarketDataProviderDep,
    QuotaRepositoryDep,
    SecDataProviderDep,
    SessionDep,
    SupplyChainGraphServiceDep,
)
from app.companies.schemas import (
    CompanyPublic,
    CompanySearchResponse,
)
from app.companies.service import get_or_create_company, search_companies
from app.core.config import settings
from app.filings.mapper import latest_10k
from app.financials.schemas import FinancialsResponse
from app.financials.service import get_financials
from app.jobs.schemas import SyncResponse
from app.jobs.service import (
    SynchronizationServices,
    synchronize_company,
    synchronize_supply_chain_graph,
)
from app.market_data.schemas import MarketResponse
from app.market_data.service import get_market_snapshot, refresh_company_profile
from app.research.schemas import IntelligenceResponse
from app.research.service import get_public_intelligence
from app.supply_chain.schemas import (
    GraphRefreshRequest,
    GraphRefreshResponse,
    PublicSupplyChainGraph,
)

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


@router.get("/{symbol}/financials", response_model=FinancialsResponse)
async def get_company_financials(
    symbol: str,
    session: SessionDep,
    sec_provider: SecDataProviderDep,
) -> FinancialsResponse:
    company = await get_or_create_company(session, sec_provider, symbol)
    return await get_financials(session, company, sec_provider)


@router.get("/{symbol}/intelligence", response_model=IntelligenceResponse)
async def get_company_intelligence(
    symbol: str,
    session: SessionDep,
    sec_provider: SecDataProviderDep,
    locale: Literal["en", "zh"] = "en",
) -> IntelligenceResponse:
    company = await get_or_create_company(session, sec_provider, symbol)
    return get_public_intelligence(session, company, locale)


@router.get(
    "/{symbol}/supply-chain-graph",
    response_model=PublicSupplyChainGraph,
)
async def get_supply_chain_graph(
    symbol: str,
    session: SessionDep,
    principal: AgentPrincipal,
    service: SupplyChainGraphServiceDep,
    sec_provider: SecDataProviderDep,
    locale: Literal["en", "zh"] = "en",
    evidence: Annotated[
        str,
        Query(pattern=r"^(verified|verified,potential)$"),
    ] = "verified",
    limit: Annotated[int, Query(ge=10, le=40)] = 40,
) -> PublicSupplyChainGraph:
    company = await get_or_create_company(session, sec_provider, symbol)
    return service.get_current(
        company=company,
        principal=principal,
        locale=locale,
        evidence=set(evidence.split(",")),
        limit=limit,
    )


@router.post("/{symbol}/sync", response_model=SyncResponse)
async def synchronize_company_intelligence(
    symbol: str,
    response: Response,
    session: SessionDep,
    principal: AgentPrincipal,
    repository: QuotaRepositoryDep,
    backend: JobBackendDep,
    sec_provider: SecDataProviderDep,
) -> SyncResponse:
    company = await get_or_create_company(session, sec_provider, symbol)
    submissions = await sec_provider.get_submissions(company.cik)
    filing = latest_10k(company.cik, submissions)
    result = await synchronize_company(
        session,
        company,
        principal,
        filing.accession_number,
        SynchronizationServices(
            quota_repository=repository,
            job_backend=backend,
            schema_version=settings.RESEARCH_SCHEMA_VERSION,
            prompt_version=settings.RESEARCH_PROMPT_VERSION,
            model_id=settings.RESEARCH_MODEL,
            guest_limit=settings.GUEST_DAILY_ANALYSIS_LIMIT,
            user_limit=settings.USER_DAILY_ANALYSIS_LIMIT,
            ip_limit=settings.IP_DAILY_ANALYSIS_LIMIT,
        ),
    )
    if result.status == "accepted":
        response.status_code = status.HTTP_202_ACCEPTED
    return result


@router.post(
    "/{symbol}/supply-chain-graph/sync",
    response_model=GraphRefreshResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def synchronize_company_supply_chain_graph(
    symbol: str,
    command: GraphRefreshRequest,
    response: Response,
    session: SessionDep,
    principal: AgentPrincipal,
    services: GraphSynchronizationServicesDep,
    sec_provider: SecDataProviderDep,
) -> GraphRefreshResponse:
    company = await get_or_create_company(session, sec_provider, symbol)
    submissions = await sec_provider.get_submissions(company.cik)
    filing = latest_10k(company.cik, submissions)
    result = await synchronize_supply_chain_graph(
        session,
        company=company,
        principal=principal,
        latest_accession=filing.accession_number,
        force_refresh=command.force_refresh,
        services=services,
    )
    if result.status == "reused_snapshot":
        response.status_code = status.HTTP_200_OK
    return result
