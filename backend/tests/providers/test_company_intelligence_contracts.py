from datetime import UTC, datetime
from decimal import Decimal

from app.providers.contracts import JobState
from app.providers.market import QuoteSnapshot
from app.providers.sec import CompanyReference, FilingReference


def test_phase_2_job_states_are_stable() -> None:
    assert [state.value for state in JobState] == [
        "queued",
        "downloading",
        "parsing",
        "analyzing",
        "verifying",
        "localizing",
        "completed",
        "failed",
    ]


def test_market_and_sec_contract_values_are_typed() -> None:
    quote = QuoteSnapshot(
        symbol="AAPL",
        price=Decimal("212.48"),
        previous_close=Decimal("209.88"),
        market_cap=Decimal("3170000000000"),
        trailing_eps=Decimal("6.42"),
        trailing_pe=Decimal("33.096573"),
        forward_pe=Decimal("29.4"),
        currency="USD",
        observed_at=datetime(2026, 7, 13, tzinfo=UTC),
        provider="yahoo",
        missing_reasons={},
    )
    company = CompanyReference(
        symbol="AAPL",
        cik="0000320193",
        name="Apple Inc.",
        exchange="Nasdaq",
    )
    filing = FilingReference(
        accession_number="0000320193-25-000079",
        form="10-K",
        filed_at=datetime(2025, 10, 31, tzinfo=UTC),
        report_date="2025-09-27",
        primary_document="aapl-20250927.htm",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/320193/example/aapl.htm"
        ),
    )

    assert quote.trailing_pe == Decimal("33.096573")
    assert company.cik == "0000320193"
    assert filing.form == "10-K"
