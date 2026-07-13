from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlmodel import Session, select

from app.core.errors import DomainError
from app.filings.sec_client import SecClient
from app.financials.service import get_financials
from app.models.company_model import Company
from app.models.market_model import FinancialMetric


class FactsProvider:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0
        self.error: Exception | None = None

    async def get_company_facts(self, cik: str) -> dict:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.payload


@pytest.mark.asyncio
async def test_service_persists_and_reuses_fresh_financials(
    financial_session: Session,
    apple: Company,
    company_facts: dict,
) -> None:
    provider = FactsProvider(company_facts)
    now = datetime(2026, 7, 13, 12, tzinfo=UTC)

    first = await get_financials(
        financial_session,
        apple,
        provider,
        now=now,
    )
    second = await get_financials(
        financial_session,
        apple,
        provider,
        now=now + timedelta(hours=23),
    )

    assert provider.calls == 1
    assert first.freshness == "fresh"
    assert second.freshness == "fresh"
    assert second.series[0].annual[-1].period_key == "FY2025"
    assert financial_session.exec(select(FinancialMetric)).all()


@pytest.mark.asyncio
async def test_service_returns_stale_rows_after_refresh_failure(
    financial_session: Session,
    apple: Company,
    company_facts: dict,
) -> None:
    provider = FactsProvider(company_facts)
    now = datetime(2026, 7, 13, 12, tzinfo=UTC)
    await get_financials(financial_session, apple, provider, now=now)
    provider.error = RuntimeError("SEC unavailable")

    result = await get_financials(
        financial_session,
        apple,
        provider,
        now=now + timedelta(hours=25),
    )

    assert result.freshness == "stale"
    assert result.fetched_at == now
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_service_raises_stable_error_without_cached_rows(
    financial_session: Session,
    apple: Company,
) -> None:
    provider = FactsProvider({})
    provider.error = RuntimeError("SEC unavailable")

    with pytest.raises(DomainError) as error:
        await get_financials(financial_session, apple, provider)

    assert error.value.code == "FINANCIAL_DATA_UNAVAILABLE"
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_sec_client_sends_user_agent() -> None:
    request_headers: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_headers.append(request.headers)
        return httpx.Response(200, json={"cik": 320193})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        sec = SecClient(client, "EquityLens test admin@example.com")
        payload = await sec.get_company_facts("0000320193")

    assert payload == {"cik": 320193}
    assert request_headers[0]["user-agent"] == "EquityLens test admin@example.com"


@pytest.mark.asyncio
async def test_sec_client_rejects_oversized_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"cik": 320193}', request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        sec = SecClient(
            client,
            "EquityLens test admin@example.com",
            max_json_bytes=4,
        )
        with pytest.raises(DomainError) as error:
            await sec.get_company_facts("0000320193")

    assert error.value.code == "SEC_RESPONSE_TOO_LARGE"


@pytest.mark.asyncio
async def test_sec_client_marks_rate_limits_as_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        sec = SecClient(client, "EquityLens test admin@example.com")
        with pytest.raises(DomainError) as error:
            await sec.get_company_facts("0000320193")

    assert error.value.code == "SEC_DATA_UNAVAILABLE"
    assert error.value.details == {"retryable": True}
