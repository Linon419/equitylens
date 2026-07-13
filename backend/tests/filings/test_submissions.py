import pytest

from app.core.errors import DomainError
from app.filings.mapper import latest_10k


def test_latest_10k_ignores_amendments_and_other_forms(
    submissions: dict,
) -> None:
    filing = latest_10k("0000320193", submissions)

    assert filing.accession_number == "0000320193-25-000079"
    assert filing.form == "10-K"
    assert filing.source_url == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019325000079/aapl-20250927.htm"
    )


def test_latest_10k_raises_stable_error_for_empty_submissions() -> None:
    with pytest.raises(DomainError) as error:
        latest_10k("0000320193", {"filings": {"recent": {}}})

    assert error.value.code == "TEN_K_NOT_FOUND"
    assert error.value.status_code == 404
