from sqlalchemy.engine import Engine
from sqlmodel import create_engine

DATABASE_CONNECTION_RECYCLE_SECONDS = 300


def create_database_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_recycle=DATABASE_CONNECTION_RECYCLE_SECONDS,
    )
