from collections.abc import Generator

import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models import Company, User


def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture
def chat_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_sqlite_foreign_keys)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Company(
                    id=1,
                    symbol="AAPL",
                    cik="0000320193",
                    name="Apple Inc.",
                ),
                Company(
                    id=2,
                    symbol="MSFT",
                    cik="0000789019",
                    name="Microsoft Corp.",
                ),
                User(id=7, email="investor-7@example.com"),
                User(id=8, email="investor-8@example.com"),
            ]
        )
        session.commit()
        yield session
