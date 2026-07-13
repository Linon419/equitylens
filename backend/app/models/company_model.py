from datetime import datetime

from sqlalchemy import Column, DateTime, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.user_model import utc_now


class Company(SQLModel, table=True):
    __tablename__ = "company"

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(max_length=16, unique=True, index=True)
    cik: str = Field(max_length=10, unique=True, index=True)
    name: str = Field(max_length=255, index=True)
    exchange: str | None = Field(default=None, max_length=64)
    sector: str | None = Field(default=None, max_length=128)
    industry: str | None = Field(default=None, max_length=255)
    description: str | None = Field(
        default=None,
        sa_column=Column(Text(), nullable=True),
    )
    profile_fetched_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Watchlist(SQLModel, table=True):
    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "company_id",
            name="uq_watchlist_user_company",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
    )
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
