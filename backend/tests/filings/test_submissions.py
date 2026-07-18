from copy import deepcopy

import pytest

from app.core.errors import DomainError
from app.filings.mapper import latest_10k, latest_annual_filing


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


def test_latest_annual_filing_accepts_a_newer_20_f(submissions: dict) -> None:
    foreign_issuer = deepcopy(submissions)
    recent = foreign_issuer["filings"]["recent"]
    latest_index = recent["accessionNumber"].index("0000320193-25-000079")
    recent["form"][latest_index] = "20-F"

    filing = latest_annual_filing("0001577552", foreign_issuer)

    assert filing.accession_number == "0000320193-25-000079"
    assert filing.form == "20-F"
