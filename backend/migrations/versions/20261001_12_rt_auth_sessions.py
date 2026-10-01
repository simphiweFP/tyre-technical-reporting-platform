"""Add opaque RT-Auth application sessions."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_12"
down_revision = "20261001_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rt_auth_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("roles", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("companies", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("warehouses", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_rt_auth_sessions_session_token_hash",
        "rt_auth_sessions",
        ["session_token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_rt_auth_sessions_user_id",
        "rt_auth_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_rt_auth_sessions_expires_at",
        "rt_auth_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_rt_auth_sessions_revoked_at",
        "rt_auth_sessions",
        ["revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_rt_auth_sessions_revoked_at", table_name="rt_auth_sessions")
    op.drop_index("ix_rt_auth_sessions_expires_at", table_name="rt_auth_sessions")
    op.drop_index("ix_rt_auth_sessions_user_id", table_name="rt_auth_sessions")
    op.drop_index(
        "ix_rt_auth_sessions_session_token_hash",
        table_name="rt_auth_sessions",
    )
    op.drop_table("rt_auth_sessions")
