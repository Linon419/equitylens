from pathlib import Path

from alembic import command, op
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.ext.compiler import compiles

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[1]
GRAPH_TABLES = {
    "supply_chain_graph_snapshot",
    "supply_chain_graph_node",
    "supply_chain_graph_edge",
    "graph_official_source",
    "graph_edge_citation",
    "agent_quota_reservation",
}


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(_type: JSONB, _compiler: object, **_kw: object) -> str:
    return "JSON"


@compiles(BYTEA, "sqlite")
def compile_bytea_for_sqlite(_type: BYTEA, _compiler: object, **_kw: object) -> str:
    return "BLOB"


def replace_postgres_extension_statement(
    _conn: object,
    _cursor: object,
    statement: str,
    parameters: object,
    _context: object,
    _executemany: bool,
) -> tuple[str, object]:
    sqlite_compatibility_noops = (
        "CREATE EXTENSION",
        "ALTER TABLE user ALTER COLUMN hashed_password DROP NOT NULL",
        "ALTER TABLE user ADD CONSTRAINT ck_user_preferred_locale",
    )
    if statement.strip().startswith(sqlite_compatibility_noops):
        return "SELECT 1", parameters
    return statement, parameters


def migration_config(monkeypatch, database: Path) -> Config:
    database_url = f"sqlite:///{database}"
    monkeypatch.setitem(settings.__dict__, "SYNC_DATABASE_URI", database_url)
    return Config(ROOT / "alembic.ini")


def named(items: list[dict[str, object]]) -> set[str]:
    return {str(item["name"]) for item in items}


def foreign_key_targets(inspector, table: str) -> dict[str, tuple[str, str]]:
    return {
        str(foreign_key["constrained_columns"][0]): (
            str(foreign_key["referred_table"]),
            str(foreign_key["referred_columns"][0]),
        )
        for foreign_key in inspector.get_foreign_keys(table)
    }


def test_supply_chain_migration_upgrade_downgrade_round_trip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "supply-chain-migration.db"
    config = migration_config(monkeypatch, database)
    monkeypatch.setattr(op, "create_check_constraint", lambda *args, **kwargs: None)
    event.listen(
        Engine,
        "before_cursor_execute",
        replace_postgres_extension_statement,
        retval=True,
    )
    try:
        command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{database}")
        inspector = inspect(engine)

        assert set(inspector.get_table_names()) >= GRAPH_TABLES
        assert {
            "graph_snapshot_id",
            "snapshot_id",
        } <= {column["name"] for column in inspector.get_columns("ingestion_job")}
        assert foreign_key_targets(inspector, "ingestion_job") == {
            "company_id": ("company", "id"),
            "snapshot_id": ("company_intelligence_snapshot", "id"),
            "graph_snapshot_id": ("supply_chain_graph_snapshot", "id"),
        }
        assert "ix_ingestion_job_graph_snapshot_id" in named(
            inspector.get_indexes("ingestion_job")
        )

        snapshot_columns = {
            column["name"]: column
            for column in inspector.get_columns("supply_chain_graph_snapshot")
        }
        assert snapshot_columns["content_en"]["nullable"] is False
        assert snapshot_columns["content_zh"]["nullable"] is False
        assert snapshot_columns["overall_confidence"]["nullable"] is True
        assert snapshot_columns["completed_at"]["nullable"] is True
        assert {
            "ix_supply_chain_graph_snapshot_company_id",
            "ix_supply_chain_graph_snapshot_status",
            "ix_supply_chain_graph_snapshot_source_fingerprint",
        } <= named(inspector.get_indexes("supply_chain_graph_snapshot"))
        assert "uq_supply_chain_graph_snapshot_version" in named(
            inspector.get_unique_constraints("supply_chain_graph_snapshot")
        )

        node_columns = {
            column["name"]: column
            for column in inspector.get_columns("supply_chain_graph_node")
        }
        assert node_columns["description_en"]["nullable"] is False
        assert node_columns["description_zh"]["nullable"] is False
        assert foreign_key_targets(inspector, "supply_chain_graph_node") == {
            "snapshot_id": ("supply_chain_graph_snapshot", "id"),
            "company_id": ("company", "id"),
        }

        assert foreign_key_targets(inspector, "supply_chain_graph_edge") == {
            "snapshot_id": ("supply_chain_graph_snapshot", "id"),
            "source_node_id": ("supply_chain_graph_node", "id"),
            "target_node_id": ("supply_chain_graph_node", "id"),
        }
        assert "uq_supply_chain_graph_edge_key" in named(
            inspector.get_unique_constraints("supply_chain_graph_edge")
        )
        assert {
            "ix_supply_chain_graph_edge_snapshot_id",
            "ix_supply_chain_graph_edge_source_node_id",
            "ix_supply_chain_graph_edge_target_node_id",
        } <= named(inspector.get_indexes("supply_chain_graph_edge"))

        assert foreign_key_targets(inspector, "graph_edge_citation") == {
            "edge_id": ("supply_chain_graph_edge", "id"),
            "source_id": ("graph_official_source", "id"),
        }
        assert "uq_agent_quota_reservation_job_id" in named(
            inspector.get_unique_constraints("agent_quota_reservation")
        )
        assert "ix_agent_quota_reservation_job_id" in named(
            inspector.get_indexes("agent_quota_reservation")
        )

        expected_checks = {
            "supply_chain_graph_snapshot": {
                "ck_supply_chain_graph_snapshot_status",
                "ck_supply_chain_graph_snapshot_evidence_coverage",
                "ck_supply_chain_graph_snapshot_confidence",
                "ck_supply_chain_graph_snapshot_node_count",
                "ck_supply_chain_graph_snapshot_edge_count",
            },
            "supply_chain_graph_node": {
                "ck_supply_chain_graph_node_kind",
                "ck_supply_chain_graph_node_layer",
                "ck_supply_chain_graph_node_importance",
                "ck_supply_chain_graph_node_confidence",
                "ck_supply_chain_graph_node_rank",
            },
            "supply_chain_graph_edge": {
                "ck_supply_chain_graph_edge_relationship_type",
                "ck_supply_chain_graph_edge_evidence_status",
                "ck_supply_chain_graph_edge_confidence",
                "ck_supply_chain_graph_edge_distinct_nodes",
            },
            "graph_official_source": {"ck_graph_official_source_type"},
            "graph_edge_citation": {"ck_graph_edge_citation_support_role"},
            "agent_quota_reservation": {
                "ck_agent_quota_reservation_principal_daily_limit",
                "ck_agent_quota_reservation_ip_daily_limit",
                "ck_agent_quota_reservation_state",
            },
        }
        for table, checks in expected_checks.items():
            assert checks <= named(inspector.get_check_constraints(table))

        engine.dispose()
        command.downgrade(config, "20260713_0003")
        engine = create_engine(f"sqlite:///{database}")
        inspector = inspect(engine)
        assert GRAPH_TABLES.isdisjoint(inspector.get_table_names())
        assert "graph_snapshot_id" not in {
            column["name"] for column in inspector.get_columns("ingestion_job")
        }

        engine.dispose()
        command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{database}")
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) >= GRAPH_TABLES
        assert "graph_snapshot_id" in {
            column["name"] for column in inspector.get_columns("ingestion_job")
        }
        engine.dispose()
    finally:
        event.remove(
            Engine,
            "before_cursor_execute",
            replace_postgres_extension_statement,
        )
