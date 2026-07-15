from pathlib import Path

from alembic import command, op
from alembic.config import Config
from pgvector.sqlalchemy import Vector
from sqlalchemy import Engine, event, inspect
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlmodel import create_engine

from app.core.config import settings

ROOT = Path(__file__).resolve().parents[1]
CHAT_TABLES = {
    "company_conversation",
    "conversation_message",
    "message_citation",
    "filing_chunk",
    "web_search_trace",
    "chat_quota_ledger",
}


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(
    _type: JSONB,
    _compiler: object,
    **_kw: object,
) -> str:
    return "JSON"


@compiles(BYTEA, "sqlite")
def compile_bytea_for_sqlite(
    _type: BYTEA,
    _compiler: object,
    **_kw: object,
) -> str:
    return "BLOB"


@compiles(Vector, "sqlite")
def compile_vector_for_sqlite(
    vector: Vector,
    _compiler: object,
    **_kw: object,
) -> str:
    return f"VECTOR({vector.dim})"


def replace_postgres_statements(
    _conn: object,
    _cursor: object,
    statement: str,
    parameters: object,
    _context: object,
    _executemany: bool,
) -> tuple[str, object]:
    normalized = " ".join(statement.split()).upper()
    if normalized.startswith("CREATE EXTENSION"):
        return "SELECT 1", parameters
    if " USING HNSW " in normalized or " USING GIN " in normalized:
        return "SELECT 1", parameters
    if normalized.startswith(
        "ALTER TABLE USER ALTER COLUMN HASHED_PASSWORD DROP NOT NULL"
    ):
        return "SELECT 1", parameters
    if normalized.startswith(
        "ALTER TABLE USER ADD CONSTRAINT CK_USER_PREFERRED_LOCALE"
    ):
        return "SELECT 1", parameters
    return statement, parameters


def migration_config(monkeypatch, database: Path) -> Config:
    database_url = f"sqlite:///{database}"
    monkeypatch.setitem(settings.__dict__, "SYNC_DATABASE_URI", database_url)
    return Config(ROOT / "alembic.ini")


def named(items: list[dict[str, object]]) -> set[str]:
    return {str(item["name"]) for item in items}


def foreign_key_relationships(
    inspector,
    table: str,
) -> set[tuple[tuple[str, ...], str, tuple[str, ...], str | None]]:
    return {
        (
            tuple(str(column) for column in foreign_key["constrained_columns"]),
            str(foreign_key["referred_table"]),
            tuple(str(column) for column in foreign_key["referred_columns"]),
            foreign_key.get("options", {}).get("ondelete"),
        )
        for foreign_key in inspector.get_foreign_keys(table)
    }


def test_chat_migration_upgrade_downgrade_round_trip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "chat-migration.db"
    config = migration_config(monkeypatch, database)
    monkeypatch.setattr(op, "create_check_constraint", lambda *args, **kwargs: None)
    event.listen(
        Engine,
        "before_cursor_execute",
        replace_postgres_statements,
        retval=True,
    )
    try:
        command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{database}")
        inspector = inspect(engine)

        assert set(inspector.get_table_names()) >= CHAT_TABLES
        assert {
            "uq_company_conversation_active_guest",
            "ix_company_conversation_company_id",
            "ix_company_conversation_user_id",
            "ix_company_conversation_guest_principal_hash",
        } <= named(inspector.get_indexes("company_conversation"))
        assert "uq_conversation_message_request" in named(
            inspector.get_unique_constraints("conversation_message")
        )
        assert "uq_message_citation_ordinal" in named(
            inspector.get_unique_constraints("message_citation")
        )
        assert "uq_filing_chunk_version" in named(
            inspector.get_unique_constraints("filing_chunk")
        )
        assert "uq_chat_quota_ledger_request_id" in named(
            inspector.get_unique_constraints("chat_quota_ledger")
        )

        assert foreign_key_relationships(inspector, "company_conversation") == {
            (("company_id",), "company", ("id",), "CASCADE"),
            (("user_id",), "user", ("id",), "CASCADE"),
            (
                ("summary_through_message_id",),
                "conversation_message",
                ("id",),
                "SET NULL",
            ),
        }
        assert foreign_key_relationships(inspector, "conversation_message") == {
            (
                ("conversation_id",),
                "company_conversation",
                ("id",),
                "CASCADE",
            ),
            (
                ("reply_to_message_id",),
                "conversation_message",
                ("id",),
                "SET NULL",
            ),
        }
        assert foreign_key_relationships(inspector, "chat_quota_ledger") == {
            (
                ("conversation_id",),
                "company_conversation",
                ("id",),
                "SET NULL",
            ),
            (
                ("user_message_id",),
                "conversation_message",
                ("id",),
                "SET NULL",
            ),
            (
                ("assistant_message_id",),
                "conversation_message",
                ("id",),
                "SET NULL",
            ),
        }

        expected_checks = {
            "company_conversation": {
                "ck_company_conversation_exactly_one_owner",
                "ck_company_conversation_locale",
                "ck_company_conversation_owner_expiration",
                "ck_company_conversation_title_length",
            },
            "conversation_message": {
                "ck_conversation_message_role",
                "ck_conversation_message_state",
                "ck_conversation_message_locale",
                "ck_conversation_message_request_owner",
                "ck_conversation_message_content_length",
                "ck_conversation_message_evidence_coverage",
                "ck_conversation_message_attempt_count",
            },
            "message_citation": {
                "ck_message_citation_ordinal",
                "ck_message_citation_source_kind",
                "ck_message_citation_source_tier",
                "ck_message_citation_verification",
                "ck_message_citation_excerpt_length",
                "ck_message_citation_https_url",
            },
            "filing_chunk": {
                "ck_filing_chunk_ordinal",
                "ck_filing_chunk_token_count",
                "ck_filing_chunk_content_hash",
            },
            "web_search_trace": {
                "ck_web_search_trace_decision",
                "ck_web_search_trace_duration",
                "ck_web_search_trace_tool_ordinal",
                "ck_web_search_trace_artifact_pair",
            },
            "chat_quota_ledger": {
                "ck_chat_quota_ledger_principal_type",
                "ck_chat_quota_ledger_attempt_number",
                "ck_chat_quota_ledger_state",
            },
        }
        for table, checks in expected_checks.items():
            assert checks <= named(inspector.get_check_constraints(table))

        engine.dispose()
        command.downgrade(config, "20260714_0004")
        engine = create_engine(f"sqlite:///{database}")
        inspector = inspect(engine)
        assert CHAT_TABLES.isdisjoint(inspector.get_table_names())
        engine.dispose()

        command.upgrade(config, "head")
        engine = create_engine(f"sqlite:///{database}")
        assert set(inspect(engine).get_table_names()) >= CHAT_TABLES
        engine.dispose()
    finally:
        event.remove(
            Engine,
            "before_cursor_execute",
            replace_postgres_statements,
        )


def test_chat_migration_declares_postgres_retrieval_indexes() -> None:
    migration = (
        ROOT
        / "app/migrations/versions/20260714_0005_company_research_chat.py"
    ).read_text()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "USING hnsw (embedding vector_cosine_ops)" in migration
    assert "USING gin (to_tsvector('english', text))" in migration
