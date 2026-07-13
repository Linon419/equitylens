def test_watchlist_requires_authentication(phase_2_api) -> None:
    assert phase_2_api.client.get("/api/v1/watchlist").status_code == 401
    assert phase_2_api.client.post("/api/v1/watchlist/AAPL").status_code == 401
    assert phase_2_api.client.delete("/api/v1/watchlist/AAPL").status_code == 401


def test_watchlist_is_idempotent_and_user_scoped(phase_2_api) -> None:
    user_headers = {"x-test-user-id": "1"}
    other_headers = {"x-test-user-id": "2"}

    first = phase_2_api.client.post("/api/v1/watchlist/AAPL", headers=user_headers)
    second = phase_2_api.client.post("/api/v1/watchlist/AAPL", headers=user_headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == {"symbol": "AAPL", "in_watchlist": True}

    mine = phase_2_api.client.get("/api/v1/watchlist", headers=user_headers)
    other = phase_2_api.client.get("/api/v1/watchlist", headers=other_headers)
    assert [item["symbol"] for item in mine.json()["items"]] == ["AAPL"]
    assert other.json()["items"] == []

    other_delete = phase_2_api.client.delete(
        "/api/v1/watchlist/AAPL",
        headers=other_headers,
    )
    assert other_delete.json() == {"symbol": "AAPL", "in_watchlist": False}
    assert phase_2_api.client.get(
        "/api/v1/watchlist",
        headers=user_headers,
    ).json()["count"] == 1

    removed = phase_2_api.client.delete(
        "/api/v1/watchlist/AAPL",
        headers=user_headers,
    )
    repeated = phase_2_api.client.delete(
        "/api/v1/watchlist/AAPL",
        headers=user_headers,
    )
    assert removed.json() == repeated.json() == {
        "symbol": "AAPL",
        "in_watchlist": False,
    }
