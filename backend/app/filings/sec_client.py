from typing import Any

import httpx

from app.companies.service import normalize_symbol
from app.core.errors import DomainError
from app.providers.sec import CompanyReference

COMPANY_DIRECTORY_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


class SecClient:
    def __init__(self, client: httpx.AsyncClient, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent

    async def resolve_company(self, symbol: str) -> CompanyReference:
        normalized = normalize_symbol(symbol)
        try:
            response = await self._client.get(
                COMPANY_DIRECTORY_URL,
                headers={"User-Agent": self._user_agent},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise DomainError("SEC_DIRECTORY_UNAVAILABLE", 503) from error

        company = _find_company(payload, normalized)
        if company is None:
            raise DomainError("COMPANY_NOT_FOUND", 404)
        return company


def _find_company(
    payload: dict[str, Any],
    symbol: str,
) -> CompanyReference | None:
    fields = payload.get("fields")
    rows = payload.get("data")
    if not isinstance(fields, list) or not isinstance(rows, list):
        raise DomainError("SEC_DIRECTORY_INVALID", 502)

    for row in rows:
        if not isinstance(row, list):
            continue
        values = dict(zip(fields, row, strict=False))
        ticker = str(values.get("ticker", "")).strip().upper()
        if ticker != symbol:
            continue
        try:
            cik = f"{int(values['cik']):010d}"
        except (KeyError, TypeError, ValueError) as error:
            raise DomainError("SEC_DIRECTORY_INVALID", 502) from error
        return CompanyReference(
            symbol=ticker,
            cik=cik,
            name=str(values.get("name", "")).strip(),
            exchange=str(values.get("exchange") or "").strip() or None,
        )
    return None
