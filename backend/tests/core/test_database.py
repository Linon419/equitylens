from unittest.mock import patch

from app.core.database import (
    DATABASE_CONNECTION_RECYCLE_SECONDS,
    create_database_engine,
)


def test_database_engine_checks_and_recycles_pooled_connections() -> None:
    with patch("app.core.database.create_engine") as create_engine:
        create_database_engine("postgresql+psycopg2://app:secret@db/app")

    create_engine.assert_called_once_with(
        "postgresql+psycopg2://app:secret@db/app",
        pool_pre_ping=True,
        pool_recycle=DATABASE_CONNECTION_RECYCLE_SECONDS,
    )
