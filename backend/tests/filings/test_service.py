from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest
from sqlmodel import Session, select

from app.core.errors import DomainError
from app.filings.mapper import latest_10k
from app.filings.sec_client import SecClient
from app.filings.service import download_latest_10k, download_latest_annual_filing
from app.models.company_model import Company
from app.models.research_model import FilingArtifact, FilingSection
from app.providers.sec import FilingContent


class FilingProvider:
    def __init__(
        self,
        submissions: dict,
        body: bytes,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.submissions = submissions
        self.body = body
        self.content_type = content_type
        self.download_calls = 0

    async def get_submissions(self, cik: str) -> dict:
        return self.submissions

    async def download_filing(self, filing) -> FilingContent:
        self.download_calls += 1
        return FilingContent(
            body=self.body,
            content_type=self.content_type,
            source_url=filing.source_url,
        )


@pytest.mark.asyncio
async def test_download_latest_10k_persists_and_reuses_artifact(
    filing_session: Session,
    filing_company: Company,
    submissions: dict,
    filing_html: bytes,
) -> None:
    provider = FilingProvider(submissions, filing_html)
    now = datetime(2026, 7, 13, 12, tzinfo=UTC)

    first = await download_latest_10k(
        filing_session,
        filing_company,
        provider,
        now=now,
    )
    second = await download_latest_10k(
        filing_session,
        filing_company,
        provider,
        now=now,
    )

    assert first.filing.id == second.filing.id
    assert first.artifact.sha256 == first.filing.content_hash
    assert provider.download_calls == 1
    assert len(filing_session.exec(select(FilingArtifact)).all()) == 1
    assert len(filing_session.exec(select(FilingSection)).all()) == 3


@pytest.mark.asyncio
async def test_download_latest_10k_rejects_non_html_content(
    filing_session: Session,
    filing_company: Company,
    submissions: dict,
) -> None:
    provider = FilingProvider(
        submissions,
        b"%PDF-1.7",
        content_type="application/pdf",
    )

    with pytest.raises(DomainError) as error:
        await download_latest_10k(
            filing_session,
            filing_company,
            provider,
        )

    assert error.value.code == "FILING_CONTENT_INVALID"


@pytest.mark.asyncio
async def test_download_latest_annual_filing_persists_20_f(
    filing_session: Session,
    filing_company: Company,
    submissions: dict,
    filing_html: bytes,
) -> None:
    foreign_issuer = deepcopy(submissions)
    recent = foreign_issuer["filings"]["recent"]
    latest_index = recent["accessionNumber"].index("0000320193-25-000079")
    recent["form"][latest_index] = "20-F"
    provider = FilingProvider(foreign_issuer, filing_html)

    stored = await download_latest_annual_filing(
        filing_session,
        filing_company,
        provider,
    )

    assert stored.filing.form == "20-F"
    assert stored.sections


def test_fixture_reference_is_current(submissions: dict) -> None:
    assert latest_10k("0000320193", submissions).report_date == "2025-09-27"


@pytest.mark.asyncio
async def test_sec_client_streams_with_size_limit(submissions: dict) -> None:
    filing = latest_10k("0000320193", submissions)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "EquityLens test admin@example.com"
        return httpx.Response(
            200,
            content=b"x" * 101,
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sec = SecClient(
            client,
            "EquityLens test admin@example.com",
            max_filing_bytes=100,
        )
        with pytest.raises(DomainError) as error:
            await sec.download_filing(filing)

    assert error.value.code == "FILING_TOO_LARGE"


@pytest.mark.asyncio
async def test_sec_client_official_download_uses_run_specific_limit(
    submissions: dict,
) -> None:
    filing = latest_10k("0000320193", submissions)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * 51,
            headers={"content-type": "text/html"},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        sec = SecClient(
            client,
            "EquityLens test admin@example.com",
            max_filing_bytes=100,
        )
        with pytest.raises(DomainError) as error:
            await sec.download_official_filing(filing, max_bytes=50)

    assert error.value.code == "FILING_TOO_LARGE"
