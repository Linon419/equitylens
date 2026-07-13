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
