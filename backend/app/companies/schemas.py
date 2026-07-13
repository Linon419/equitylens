from pydantic import BaseModel, ConfigDict


class CompanySearchItem(BaseModel):
    symbol: str
    name: str
    exchange: str | None


class CompanySearchResponse(BaseModel):
    items: list[CompanySearchItem]
    count: int


class CompanyPublic(CompanySearchItem):
    model_config = ConfigDict(from_attributes=True)

    cik: str
    sector: str | None
    industry: str | None
    description: str | None
