"""Add Google identities and rotating authentication sessions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_0002"
down_revision: str | None = "20260713_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=True)
    op.add_column("user", sa.Column("avatar_url", sa.String(), nullable=True))
    op.add_column(
        "user",
        sa.Column(
            "preferred_locale",
            sa.String(length=5),
            server_default="en-US",
            nullable=False,
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_user_preferred_locale",
        "user",
        "preferred_locale IN ('en-US', 'zh-CN')",
    )

    op.create_table(
        "external_identity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "provider_subject",
            name="uq_external_identity_provider_subject",
        ),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            name="uq_external_identity_user_provider",
        ),
    )
    op.create_index(
        "ix_external_identity_user_id",
        "external_identity",
        ["user_id"],
    )

    op.create_table(
        "auth_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_family_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["auth_session.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])
    op.create_index(
        "ix_auth_session_token_family_id",
        "auth_session",
        ["token_family_id"],
    )


def downgrade() -> None:
    null_passwords = op.get_bind().execute(
        sa.text('SELECT count(*) FROM "user" WHERE hashed_password IS NULL')
    ).scalar_one()
    if null_passwords:
        raise RuntimeError(
            "Link or remove federated users before downgrading authentication schema"
        )
    op.drop_index("ix_auth_session_token_family_id", table_name="auth_session")
    op.drop_index("ix_auth_session_user_id", table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_index("ix_external_identity_user_id", table_name="external_identity")
    op.drop_table("external_identity")
    op.drop_constraint("ck_user_preferred_locale", "user", type_="check")
    op.drop_column("user", "updated_at")
    op.drop_column("user", "created_at")
    op.drop_column("user", "preferred_locale")
    op.drop_column("user", "avatar_url")
    op.alter_column(
        "user",
        "hashed_password",
        existing_type=sa.String(),
        nullable=False,
    )
