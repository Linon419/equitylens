from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class ExternalIdentity(SQLModel, table=True):
    __tablename__ = "external_identity"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_external_identity_provider_subject",
        ),
        UniqueConstraint(
            "user_id",
            "provider",
            name="uq_external_identity_user_provider",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    provider: str = Field(max_length=32)
    provider_subject: str = Field(max_length=255)
    provider_email: str = Field(max_length=320)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    last_login_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_session"
    __table_args__ = (Index("ix_auth_session_token_family_id", "token_family_id"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(max_length=64)
    token_family_id: UUID = Field(default_factory=uuid4)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    rotated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    replaced_by_id: UUID | None = Field(
        default=None,
        foreign_key="auth_session.id",
    )
