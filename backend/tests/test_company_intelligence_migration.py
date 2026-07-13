from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "app/migrations/versions/20260713_0003_company_intelligence.py"


def test_company_intelligence_migration_declares_all_tables_and_constraints() -> None:
    migration = MIGRATION.read_text()

    for table in (
        "company",
        "watchlist",
        "market_snapshot",
        "financial_metric",
        "filing",
        "filing_artifact",
        "filing_section",
        "company_intelligence_snapshot",
        "evidence_citation",
        "ingestion_job",
        "agent_daily_usage",
    ):
        assert f'"{table}"' in migration

    for constraint in (
        "uq_watchlist_user_company",
        "uq_financial_metric_source_period",
        "uq_filing_company_accession",
        "uq_company_intelligence_snapshot_version",
        "uq_ingestion_job_deduplication",
        "uq_agent_daily_usage_principal_date",
        "ck_agent_usage_nonnegative",
        "ck_agent_usage_limit",
    ):
        assert constraint in migration

    assert 'down_revision: str | None = "20260713_0002"' in migration
    assert 'sa.Column("job_type"' in migration
    assert 'sa.Column("price_change"' in migration
    assert 'sa.Column("price_change_percent"' in migration


def test_company_intelligence_downgrade_drops_children_before_parents() -> None:
    downgrade = MIGRATION.read_text().split("def downgrade() -> None:", maxsplit=1)[1]
    tables = [
        "evidence_citation",
        "filing_section",
        "filing_artifact",
        "ingestion_job",
        "company_intelligence_snapshot",
        "financial_metric",
        "market_snapshot",
        "watchlist",
        "agent_daily_usage",
        "filing",
        "company",
    ]

    positions = [downgrade.index(f'op.drop_table("{table}")') for table in tables]
    assert positions == sorted(positions)
