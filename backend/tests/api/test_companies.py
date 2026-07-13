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
