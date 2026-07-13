from datetime import date

from sqlmodel import Session, select

from app.models.company_model import Company
from app.models.research_model import (
    CompanyIntelligenceSnapshot,
    Filing,
    FilingSection,
)


def test_company_search_and_identity_are_public(phase_2_api) -> None:
    search = phase_2_api.client.get("/api/v1/companies/search?q=apple")
    assert search.status_code == 200
    assert search.json() == {
        "items": [{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NMS"}],
        "count": 1,
    }

    company = phase_2_api.client.get("/api/v1/companies/aapl")
    assert company.status_code == 200
    assert company.json()["cik"] == "0000320193"
    assert company.json()["symbol"] == "AAPL"
    assert company.json()["sector"] == "Technology"
    assert company.json()["industry"] == "Consumer Electronics"


def test_company_market_returns_compact_valuation_context(phase_2_api) -> None:
    response = phase_2_api.client.get("/api/v1/companies/AAPL/market")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "AAPL"
    assert payload["price"] == {"value": "212.48000000", "missing_reason": None}
    assert payload["trailing_eps"]["value"] == "6.42000000"
    assert payload["trailing_pe"]["value"] == "33.09657300"
    assert payload["forward_pe"]["value"] == "29.40000000"
    assert payload["provider"] == "yahoo"
    assert payload["freshness"] == "fresh"


def test_company_financials_return_four_years_and_ttm(phase_2_api) -> None:
    response = phase_2_api.client.get("/api/v1/companies/AAPL/financials")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "AAPL"
    assert payload["source"] == "SEC XBRL Company Facts"
    revenue = next(
        item for item in payload["series"] if item["metric_key"] == "revenue"
    )
    assert [point["period_key"] for point in revenue["annual"]] == [
        "FY2022",
        "FY2023",
        "FY2024",
        "FY2025",
    ]
    assert revenue["ttm"]["value"] == "401000000000.0000"


def test_company_intelligence_returns_localized_verified_citations(
    phase_2_api,
) -> None:
    phase_2_api.client.get("/api/v1/companies/AAPL")
    with Session(phase_2_api.engine) as session:
        company = session.exec(
            select(Company).where(Company.symbol == "AAPL")
        ).one()
        filing = Filing(
            company_id=company.id,
            accession_number="0000320193-25-000079",
            form="10-K",
            fiscal_period="FY2025",
            filed_at=date(2025, 10, 31),
            report_date=date(2025, 9, 27),
            primary_document="aapl-20250927.htm",
            source_url="https://www.sec.gov/example/aapl-20250927.htm",
        )
        session.add(filing)
        session.commit()
        session.refresh(filing)
        section = FilingSection(
            filing_id=filing.id,
            heading="Item 1. Business",
            source_anchor="item-1-business",
            ordinal=0,
            text="The Company designs and sells products and services.",
        )
        session.add(section)
        session.commit()
        session.refresh(section)
        base = {
            "core_businesses": [
                {
                    "claim_id": "business-1",
                    "title": "Devices and services",
                    "explanation": "Products anchor a services ecosystem.",
                    "confidence": "High",
                    "citation_ids": ["citation-1"],
                }
            ],
            "revenue_engines": [],
            "upstream": [],
            "company_layer": [],
            "downstream": [],
            "competitors": [],
            "material_dependencies": [],
            "citations": [
                {
                    "citation_id": "citation-1",
                    "section_id": str(section.id),
                    "excerpt": "The Company designs and sells products and services.",
                }
            ],
            "evidence_coverage": "complete",
            "overall_confidence": "High",
        }
        snapshot = CompanyIntelligenceSnapshot(
            company_id=company.id,
            filing_id=filing.id,
            status="completed",
            evidence_coverage="complete",
            schema_version="v1",
            prompt_version="p1",
            model_id="model-1",
            content_en={**base, "locale": "en"},
            content_zh={**base, "locale": "zh"},
            overall_confidence="High",
        )
        session.add(snapshot)
        session.commit()

    response = phase_2_api.client.get(
        "/api/v1/companies/AAPL/intelligence?locale=en"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"]["core_businesses"][0]["claim_id"] == "business-1"
    assert payload["citations"][0]["filing_type"] == "10-K"
    assert payload["citations"][0]["source_url"].endswith("#item-1-business")


def test_company_search_rejects_short_queries_with_request_id(phase_2_api) -> None:
    response = phase_2_api.client.get(
        "/api/v1/companies/search?q=a",
        headers={"x-request-id": "company-test-request"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "COMPANY_SEARCH_QUERY_INVALID",
        "request_id": "company-test-request",
    }


def test_company_identity_returns_stable_not_found(phase_2_api) -> None:
    response = phase_2_api.client.get("/api/v1/companies/NVDA")

    assert response.status_code == 404
    assert response.json()["code"] == "COMPANY_NOT_FOUND"
