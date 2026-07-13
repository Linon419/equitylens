import json
from pathlib import Path

from app.market_data.yahoo import map_search_results

FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures/yahoo/search_aapl.json"
)


def test_yahoo_search_mapper_keeps_us_equities() -> None:
    payload = json.loads(FIXTURE.read_text())

    result = map_search_results(payload["quotes"])

    assert [match.symbol for match in result] == ["AAPL"]
    assert result[0].name == "Apple Inc."
    assert result[0].exchange == "NMS"


def test_yahoo_search_mapper_deduplicates_and_caps_results() -> None:
    rows = [
        {
            "symbol": f"TEST{index}",
            "shortname": f"Test {index}",
            "exchange": "NMS",
            "quoteType": "EQUITY",
        }
        for index in range(10)
    ]
    rows.insert(1, rows[0])

    result = map_search_results(rows)

    assert len(result) == 8
    assert len({match.symbol for match in result}) == 8
