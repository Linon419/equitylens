"""Deterministic, fabricated company-intelligence fixtures for tests only."""

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.core.errors import DomainError
from app.jobs.schemas import JobSubmission
from app.providers.market import CompanyProfile, QuoteSnapshot, SymbolMatch
from app.providers.sec import CompanyReference, FilingContent
from app.research.schemas import (
    IntelligenceClaim,
    IntelligenceDraft,
    LocalizedIntelligence,
    VerificationResult,
    VerificationVerdict,
)

FIXTURE_ROOT = Path(__file__).parent
SEC_FIXTURES = FIXTURE_ROOT / "sec"
TEST_DATA_NOTICE = "All values and conclusions in this module are test data."
COMPANY_SYMBOLS = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "JPM",
    "XOM",
    "COST",
    "NFLX",
)
COMPANY_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms, Inc.",
    "TSLA": "Tesla, Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "XOM": "Exxon Mobil Corporation",
    "COST": "Costco Wholesale Corporation",
    "NFLX": "Netflix, Inc.",
}


@dataclass
class DeterministicMarketProvider:
    provider_name = "yahoo"

    searches: list[str] = field(default_factory=list)

    async def search_symbols(self, query: str) -> list[SymbolMatch]:
        self.searches.append(query)
        normalized = query.casefold()
        return [
            SymbolMatch(symbol, name, "NMS")
            for symbol, name in COMPANY_NAMES.items()
            if normalized in symbol.casefold() or normalized in name.casefold()
        ][:8]

    async def get_quote(self, symbol: str) -> QuoteSnapshot:
        return QuoteSnapshot(
            symbol=symbol,
            price=Decimal("212.48"),
            previous_close=Decimal("209.88"),
            market_cap=Decimal("3170000000000"),
            trailing_eps=Decimal("6.42"),
            trailing_pe=Decimal("33.096573"),
            forward_pe=Decimal("29.4"),
            currency="USD",
            observed_at=datetime(2026, 7, 13, 12, tzinfo=UTC),
            provider="yahoo",
            missing_reasons={},
            price_change=Decimal("2.60"),
            price_change_percent=Decimal("1.238803"),
        )

    async def get_company_profile(self, symbol: str) -> CompanyProfile:
        return CompanyProfile(
            symbol=symbol,
            name=COMPANY_NAMES[symbol],
            sector="Technology",
            industry="Consumer Electronics",
            description=(
                f"{COMPANY_NAMES[symbol]} is represented by fabricated "
                "company data in this deterministic test environment."
            ),
        )


@dataclass
class DeterministicSecProvider:
    downloads: int = 0

    async def resolve_company(self, symbol: str) -> CompanyReference:
        normalized = symbol.upper()
        if normalized not in COMPANY_NAMES:
            raise DomainError("COMPANY_NOT_FOUND", 404)
        cik = f"{COMPANY_SYMBOLS.index(normalized) + 320193:010d}"
        return CompanyReference(
            symbol=normalized,
            cik=cik,
            name=COMPANY_NAMES[normalized],
            exchange="Nasdaq",
        )

    async def get_submissions(self, cik: str) -> dict:
        payload = _load_json(SEC_FIXTURES / "aapl_submissions.json")
        payload["cik"] = cik
        return payload

    async def get_company_facts(self, cik: str) -> dict:
        payload = _load_json(SEC_FIXTURES / "aapl_companyfacts.json")
        payload["cik"] = cik
        return payload

    async def download_filing(self, filing) -> FilingContent:
        self.downloads += 1
        return FilingContent(
            body=(SEC_FIXTURES / "aapl_10k_excerpt.html").read_bytes(),
            content_type="text/html",
            source_url=filing.source_url,
        )


class DeterministicIntelligenceGenerator:
    model_id = "deterministic-test-model"

    async def generate(self, bundle) -> IntelligenceDraft:
        business, risk, sales = bundle.sections[:3]
        citations = [
            {
                "citation_id": "citation-1",
                "section_id": business.section_id,
                "excerpt": business.text,
            },
            {
                "citation_id": "citation-2",
                "section_id": risk.section_id,
                "excerpt": risk.text,
            },
            {
                "citation_id": "citation-3",
                "section_id": sales.section_id,
                "excerpt": sales.text,
            },
        ]
        return IntelligenceDraft(
            core_businesses=[
                _claim(
                    "business-1",
                    "Devices and services",
                    "Hardware and services form the fabricated test business.",
                    "citation-1",
                    "High",
                )
            ],
            revenue_engines=[
                _claim(
                    "revenue-1",
                    "Product and service sales FY2025",
                    (
                        "Products and services are the fabricated revenue "
                        "engines for FY2025."
                    ),
                    "citation-3",
                    "High",
                    revenue_period="FY2025",
                )
            ],
            upstream=[
                _claim(
                    "upstream-1",
                    "Manufacturing supply",
                    "Manufacturing capacity is a fabricated upstream dependency.",
                    "citation-2",
                    "Medium",
                )
            ],
            company_layer=[
                _claim(
                    "company-1",
                    "Integrated product layer",
                    "Devices and services form the fabricated company layer.",
                    "citation-1",
                    "High",
                )
            ],
            downstream=[
                _claim(
                    "downstream-1",
                    "Product and service customers",
                    "Fabricated customer demand sits downstream of product sales.",
                    "citation-3",
                    "Medium",
                )
            ],
            competitors=[
                _claim(
                    "competitor-1",
                    "Platform alternatives",
                    "Platform alternatives are a fabricated research question.",
                    "citation-1",
                    "Low",
                )
            ],
            material_dependencies=[
                _claim(
                    "dependency-1",
                    "Supply concentration",
                    "Supply concentration is a fabricated material dependency.",
                    "citation-2",
                    "High",
                )
            ],
            citations=citations,
        )

    async def verify(self, draft: IntelligenceDraft) -> VerificationResult:
        return VerificationResult(
            verdicts=[
                VerificationVerdict(
                    claim_id=claim.claim_id,
                    supported=True,
                    reason="Supported by deterministic test evidence.",
                )
                for claim in draft.all_claims()
            ]
        )

    async def localize(self, verified, locale) -> LocalizedIntelligence:
        payload = deepcopy(verified.model_dump())
        if locale == "zh":
            for claim in _payload_claims(payload):
                claim["title"] = f"测试：{claim['title']}"
                claim["explanation"] = f"测试数据：{claim['explanation']}"
        return LocalizedIntelligence(locale=locale, **payload)


@dataclass
class RecordingJobBackend:
    job_ids: list[str] = field(default_factory=list)

    async def enqueue(self, *, job_type: str, payload: dict) -> JobSubmission:
        job_id = str(payload["job_id"])
        self.job_ids.append(job_id)
        return JobSubmission(job_id=f"deterministic:{job_id}")


def _claim(
    claim_id: str,
    title: str,
    explanation: str,
    citation_id: str,
    confidence: str,
    *,
    revenue_period: str | None = None,
) -> IntelligenceClaim:
    return IntelligenceClaim(
        claim_id=claim_id,
        title=title,
        explanation=explanation,
        confidence=confidence,
        citation_ids=[citation_id],
        revenue_period=revenue_period,
    )


def _payload_claims(payload: dict) -> list[dict]:
    fields = (
        "core_businesses",
        "revenue_engines",
        "upstream",
        "company_layer",
        "downstream",
        "competitors",
        "material_dependencies",
    )
    return [claim for field in fields for claim in payload[field]]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())
