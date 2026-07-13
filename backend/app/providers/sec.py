from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class CompanyReference:
    symbol: str
    cik: str
    name: str
    exchange: str | None


@dataclass(frozen=True)
class FilingReference:
    accession_number: str
    form: str
    filed_at: datetime
    report_date: str
    primary_document: str
    source_url: str


@dataclass(frozen=True)
class FilingContent:
    body: bytes
    content_type: str
    source_url: str


class SecDataProvider(Protocol):
    async def resolve_company(self, symbol: str) -> CompanyReference: ...

    async def get_submissions(self, cik: str) -> dict[str, Any]: ...

    async def get_company_facts(self, cik: str) -> dict[str, Any]: ...

    async def download_filing(self, filing: FilingReference) -> FilingContent: ...
