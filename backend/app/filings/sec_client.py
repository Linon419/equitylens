from typing import Any

import httpx

from app.companies.service import normalize_symbol
from app.core.errors import DomainError
from app.providers.sec import CompanyReference, FilingContent, FilingReference

COMPANY_DIRECTORY_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
DEFAULT_MAX_JSON_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_FILING_BYTES = 15 * 1024 * 1024


class SecClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        user_agent: str,
        max_json_bytes: int = DEFAULT_MAX_JSON_BYTES,
        max_filing_bytes: int = DEFAULT_MAX_FILING_BYTES,
    ) -> None:
        self._client = client
        self._user_agent = user_agent
        self._max_json_bytes = max_json_bytes
        self._max_filing_bytes = max_filing_bytes

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

    async def get_company_facts(self, cik: str) -> dict[str, Any]:
        normalized = _normalize_cik(cik)
        url = COMPANY_FACTS_URL.format(cik=normalized)
        return await self._get_json(url)

    async def get_submissions(self, cik: str) -> dict[str, Any]:
        normalized = _normalize_cik(cik)
        return await self._get_json(SUBMISSIONS_URL.format(cik=normalized))

    async def download_filing(self, filing: FilingReference) -> FilingContent:
        try:
            async with self._client.stream(
                "GET",
                filing.source_url,
                headers={"User-Agent": self._user_agent},
            ) as response:
                _raise_for_sec_status(response)
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > self._max_filing_bytes:
                        raise DomainError("FILING_TOO_LARGE", 413)
                    chunks.append(chunk)
                return FilingContent(
                    body=b"".join(chunks),
                    content_type=response.headers.get(
                        "content-type",
                        "application/octet-stream",
                    ),
                    source_url=str(response.url),
                )
        except httpx.HTTPError as error:
            raise DomainError(
                "SEC_DATA_UNAVAILABLE",
                503,
                {"retryable": True},
            ) from error

    async def _get_json(self, url: str) -> dict[str, Any]:
        try:
            response = await self._client.get(
                url,
                headers={"User-Agent": self._user_agent},
            )
        except httpx.HTTPError as error:
            raise DomainError(
                "SEC_DATA_UNAVAILABLE",
                503,
                {"retryable": True},
            ) from error
        _raise_for_sec_status(response)
        if len(response.content) > self._max_json_bytes:
            raise DomainError("SEC_RESPONSE_TOO_LARGE", 502)
        try:
            payload = response.json()
        except ValueError as error:
            raise DomainError("SEC_DATA_INVALID", 502) from error
        if not isinstance(payload, dict):
            raise DomainError("SEC_DATA_INVALID", 502)
        return payload


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


def _normalize_cik(value: str) -> str:
    try:
        return f"{int(value):010d}"
    except (TypeError, ValueError) as error:
        raise DomainError("SEC_CIK_INVALID", 400) from error


def _raise_for_sec_status(response: httpx.Response) -> None:
    if response.status_code == 429 or response.status_code >= 500:
        raise DomainError(
            "SEC_DATA_UNAVAILABLE",
            503,
            {"retryable": True},
        )
    if response.is_error:
        raise DomainError(
            "SEC_DATA_UNAVAILABLE",
            502,
            {"retryable": False},
        )
