from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, DateTime, Numeric, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.user_model import utc_now


def optional_money_column() -> Column[Decimal]:
    return Column(Numeric(30, 8), nullable=True)


class MarketSnapshot(SQLModel, table=True):
    __tablename__ = "market_snapshot"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    price: Decimal | None = Field(
        default=None,
        sa_column=optional_money_column(),
    )
    previous_close: Decimal | None = Field(
        default=None,
        sa_column=optional_money_column(),
    )
    price_change: Decimal | None = Field(
        default=None,
        sa_column=optional_money_column(),
    )
    price_change_percent: Decimal | None = Field(
        default=None,
        sa_column=optional_money_column(),
    )
    market_cap: Decimal | None = Field(
        default=None,
        sa_column=optional_money_column(),
    )
    trailing_eps: Decimal | None = Field(
        default=None,
        sa_column=optional_money_column(),
    )
    trailing_pe: Decimal | None = Field(
        default=None,
        sa_column=optional_money_column(),
    )
    forward_pe: Decimal | None = Field(
        default=None,
        sa_column=optional_money_column(),
    )
    currency: str = Field(default="USD", max_length=8)
    provider: str = Field(max_length=32)
    observed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    fetched_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    missing_reasons: dict[str, str] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )


class FinancialMetric(SQLModel, table=True):
    __tablename__ = "financial_metric"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "metric_key",
            "period_key",
            "accession_number",
            name="uq_financial_metric_source_period",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    metric_key: str = Field(max_length=64, index=True)
    fiscal_year: int
    fiscal_period: str = Field(max_length=8)
    period_key: str = Field(max_length=32)
    start_date: date | None = None
    end_date: date
    value: Decimal = Field(
        sa_column=Column(Numeric(30, 4), nullable=False),
    )
    unit: str = Field(max_length=16)
    taxonomy_tag: str = Field(max_length=255)
    accession_number: str = Field(max_length=20)
    filed_at: date
    source_url: str = Field(sa_column=Column(Text(), nullable=False))
    fetched_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
