from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.company_model import Company, Watchlist
from app.models.job_model import AgentDailyUsage, IngestionJob
from app.models.market_model import FinancialMetric, MarketSnapshot
from app.models.research_model import (
    CompanyIntelligenceSnapshot,
    EvidenceCitation,
    Filing,
    FilingArtifact,
    FilingSection,
)

NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)


def build_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_phase_2_models_round_trip() -> None:
    with build_session() as session:
        company = Company(symbol="AAPL", cik="0000320193", name="Apple Inc.")
        session.add(company)
        session.commit()
        session.refresh(company)
        assert company.id is not None

        market = MarketSnapshot(
            company_id=company.id,
            price=Decimal("212.48"),
            previous_close=Decimal("209.88"),
            price_change=Decimal("2.60"),
            price_change_percent=Decimal("1.238803"),
            currency="USD",
            provider="yahoo",
            observed_at=NOW,
            fetched_at=NOW,
            missing_reasons={},
        )
        metric = FinancialMetric(
            company_id=company.id,
            metric_key="revenue",
            fiscal_year=2025,
            fiscal_period="FY",
            period_key="FY2025",
            start_date=date(2024, 9, 29),
            end_date=date(2025, 9, 27),
            value=Decimal("416161000000"),
            unit="USD",
            taxonomy_tag="RevenueFromContractWithCustomerExcludingAssessedTax",
            accession_number="0000320193-25-000079",
            filed_at=date(2025, 10, 31),
            source_url="https://www.sec.gov/example",
            fetched_at=NOW,
        )
        session.add_all([market, metric])
        session.commit()

        assert session.exec(select(Company)).one().symbol == "AAPL"
        stored_market = session.exec(select(MarketSnapshot)).one()
        assert stored_market.price == Decimal("212.48")
        assert stored_market.price_change == Decimal("2.60")
        assert session.exec(select(FinancialMetric)).one().period_key == "FY2025"


def test_research_artifacts_and_citations_round_trip() -> None:
    with build_session() as session:
        company = Company(symbol="AAPL", cik="0000320193", name="Apple Inc.")
        session.add(company)
        session.commit()
        session.refresh(company)
        assert company.id is not None

        filing = Filing(
            company_id=company.id,
            accession_number="0000320193-25-000079",
            form="10-K",
            fiscal_period="FY2025",
            filed_at=date(2025, 10, 31),
            report_date=date(2025, 9, 27),
            primary_document="aapl-20250927.htm",
            source_url="https://www.sec.gov/example",
            content_hash="hash",
            retrieved_at=NOW,
        )
        session.add(filing)
        session.commit()
        session.refresh(filing)

        artifact = FilingArtifact(
            filing_id=filing.id,
            content_type="text/html",
            compressed_body=b"gzip",
            compressed_size=4,
            uncompressed_size=12,
            sha256="hash",
        )
        section = FilingSection(
            filing_id=filing.id,
            heading="Item 1. Business",
            source_anchor="item-1",
            ordinal=1,
            text="The company designs and sells products.",
        )
        snapshot = CompanyIntelligenceSnapshot(
            company_id=company.id,
            filing_id=filing.id,
            status="completed",
            evidence_coverage="complete",
            schema_version="company-intelligence-v1",
            prompt_version="company-intelligence-2026-07-13",
            model_id="gpt-5-mini",
            content_en={"core_businesses": []},
            content_zh={"core_businesses": []},
            overall_confidence="High",
            generated_at=NOW,
            verified_at=NOW,
        )
        session.add_all([artifact, section, snapshot])
        session.commit()
        session.refresh(snapshot)

        citation = EvidenceCitation(
            snapshot_id=snapshot.id,
            filing_id=filing.id,
            section_label="Item 1. Business",
            source_anchor="item-1",
            excerpt="The company designs and sells products.",
            source_url="https://www.sec.gov/example#item-1",
            verification_verdict="supported",
        )
        session.add(citation)
        session.commit()

        assert session.exec(select(FilingArtifact)).one().compressed_body == b"gzip"
        assert session.exec(select(FilingSection)).one().ordinal == 1
        assert session.exec(select(EvidenceCitation)).one().verification_verdict == (
            "supported"
        )


def test_job_and_usage_keys_are_explicit() -> None:
    job = IngestionJob(
        job_type="company_intelligence",
        company_id=1,
        requested_by_type="guest",
        requested_by_hash="guest-hash",
        deduplication_key="company:filing:schema:prompt:model",
        state="queued",
        current_step="queued",
    )
    usage = AgentDailyUsage(
        principal_type="guest",
        principal_hash="guest-hash",
        usage_date=date(2026, 7, 13),
        accepted_count=1,
        daily_limit=2,
    )

    assert job.retry_eligible is True
    assert job.job_type == "company_intelligence"
    assert usage.accepted_count < usage.daily_limit


def test_phase_2_constraints_are_named() -> None:
    watchlist_constraints = {
        constraint.name for constraint in Watchlist.__table__.constraints
    }
    job_constraints = {
        constraint.name for constraint in IngestionJob.__table__.constraints
    }
    usage_constraints = {
        constraint.name for constraint in AgentDailyUsage.__table__.constraints
    }

    assert "uq_watchlist_user_company" in watchlist_constraints
    assert "uq_ingestion_job_deduplication" in job_constraints
    assert "uq_agent_daily_usage_principal_date" in usage_constraints
    assert "ck_agent_usage_nonnegative" in usage_constraints
    assert "ck_agent_usage_limit" in usage_constraints


def test_market_cache_lookup_index_is_in_metadata() -> None:
    indexes = {index.name for index in MarketSnapshot.__table__.indexes}

    assert "ix_market_snapshot_fetched_at" in indexes
