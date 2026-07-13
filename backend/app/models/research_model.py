from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    LargeBinary,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, SQLModel

from app.models.user_model import utc_now


class Filing(SQLModel, table=True):
    __tablename__ = "filing"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "accession_number",
            name="uq_filing_company_accession",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    accession_number: str = Field(max_length=20, index=True)
    form: str = Field(max_length=16)
    fiscal_period: str | None = Field(default=None, max_length=32)
    filed_at: date
    report_date: date
    primary_document: str = Field(max_length=255)
    source_url: str = Field(sa_column=Column(Text(), nullable=False))
    content_hash: str | None = Field(default=None, max_length=64)
    retrieved_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class FilingArtifact(SQLModel, table=True):
    __tablename__ = "filing_artifact"
    __table_args__ = (
        CheckConstraint(
            "compressed_size >= 0",
            name="ck_filing_artifact_compressed_size",
        ),
        CheckConstraint(
            "uncompressed_size >= 0",
            name="ck_filing_artifact_uncompressed_size",
        ),
    )

    filing_id: UUID = Field(
        foreign_key="filing.id",
        ondelete="CASCADE",
        primary_key=True,
    )
    content_type: str = Field(max_length=128)
    compressed_body: bytes = Field(
        sa_column=Column(LargeBinary(), nullable=False),
    )
    compressed_size: int
    uncompressed_size: int
    sha256: str = Field(max_length=64)


class FilingSection(SQLModel, table=True):
    __tablename__ = "filing_section"
    __table_args__ = (
        UniqueConstraint(
            "filing_id",
            "ordinal",
            name="uq_filing_section_filing_ordinal",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    filing_id: UUID = Field(
        foreign_key="filing.id",
        ondelete="CASCADE",
        index=True,
    )
    heading: str = Field(max_length=255)
    source_anchor: str = Field(max_length=255)
    ordinal: int
    text: str = Field(sa_column=Column(Text(), nullable=False))


class CompanyIntelligenceSnapshot(SQLModel, table=True):
    __tablename__ = "company_intelligence_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "filing_id",
            "schema_version",
            "prompt_version",
            "model_id",
            name="uq_company_intelligence_snapshot_version",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: int = Field(
        foreign_key="company.id",
        ondelete="CASCADE",
        index=True,
    )
    filing_id: UUID = Field(
        foreign_key="filing.id",
        ondelete="CASCADE",
        index=True,
    )
    status: str = Field(max_length=32, index=True)
    evidence_coverage: str = Field(max_length=32)
    schema_version: str = Field(max_length=64)
    prompt_version: str = Field(max_length=64)
    model_id: str = Field(max_length=128)
    content_en: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    content_zh: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    overall_confidence: str | None = Field(default=None, max_length=16)
    generated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    verified_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class EvidenceCitation(SQLModel, table=True):
    __tablename__ = "evidence_citation"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    snapshot_id: UUID = Field(
        foreign_key="company_intelligence_snapshot.id",
        ondelete="CASCADE",
        index=True,
    )
    filing_id: UUID = Field(
        foreign_key="filing.id",
        ondelete="CASCADE",
        index=True,
    )
    section_label: str = Field(max_length=255)
    source_anchor: str = Field(max_length=255)
    excerpt: str = Field(max_length=1000)
    source_url: str = Field(sa_column=Column(Text(), nullable=False))
    verification_verdict: str = Field(max_length=32)
