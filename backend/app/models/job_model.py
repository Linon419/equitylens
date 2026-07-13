from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.user_model import utc_now


class IngestionJob(SQLModel, table=True):
    __tablename__ = "ingestion_job"
    __table_args__ = (
        UniqueConstraint(
            "deduplication_key",
            name="uq_ingestion_job_deduplication",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_type: str = Field(default="company_intelligence", max_length=64)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    requested_by_type: str = Field(max_length=16)
    requested_by_hash: str = Field(max_length=64, index=True)
    deduplication_key: str = Field(max_length=255)
    state: str = Field(max_length=32, index=True)
    current_step: str = Field(max_length=32)
    provider_run_id: str | None = Field(default=None, max_length=255)
    attempt_count: int = 0
    retry_eligible: bool = True
    error_code: str | None = Field(default=None, max_length=64)
    snapshot_id: UUID | None = Field(
        default=None,
        foreign_key="company_intelligence_snapshot.id",
        ondelete="SET NULL",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AgentDailyUsage(SQLModel, table=True):
    __tablename__ = "agent_daily_usage"
    __table_args__ = (
        UniqueConstraint(
            "principal_type",
            "principal_hash",
            "usage_date",
            name="uq_agent_daily_usage_principal_date",
        ),
        CheckConstraint(
            "accepted_count >= 0",
            name="ck_agent_usage_nonnegative",
        ),
        CheckConstraint(
            "accepted_count <= daily_limit",
            name="ck_agent_usage_limit",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    principal_type: str = Field(max_length=16, index=True)
    principal_hash: str = Field(max_length=64, index=True)
    usage_date: date = Field(index=True)
    accepted_count: int = 0
    daily_limit: int
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
