"""RT-Auth server-side login transactions and sessions."""

import sqlalchemy as sa
from alembic import op

revision = "20261003_13"
down_revision = "20261002_12"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_users_rt_auth_subject",
        "users",
        ["external_subject"],
        unique=True,
        sqlite_where=sa.text("external_provider = 'rt-auth'"),
        postgresql_where=sa.text("external_provider = 'rt-auth'"),
    )
    op.create_table(
        "company_auth_logins",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("verifier", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "company_auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("refresh_ciphertext", sa.Text(), nullable=False),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("claims", sa.JSON(), nullable=False),
        sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_company_auth_sessions_user_id", "company_auth_sessions", ["user_id"]
    )


def downgrade():
    op.drop_index("uq_users_rt_auth_subject", table_name="users")
    op.drop_table("company_auth_sessions")
    op.drop_table("company_auth_logins")
