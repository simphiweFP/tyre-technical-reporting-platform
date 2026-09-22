"""Add persistent reports, local media metadata and password recovery."""

import sqlalchemy as sa
from alembic import op

revision = "20260921_03"
down_revision = "20260921_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("external_provider", sa.String(40), nullable=True))
    op.add_column("users", sa.Column("external_subject", sa.String(255), nullable=True))
    op.create_index("ix_users_external_subject", "users", ["external_subject"])
    op.add_column(
        "report_delivery_attempts",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE report_delivery_attempts SET next_attempt_at = last_attempt_at")
    with op.batch_alter_table("report_delivery_attempts") as batch:
        batch.alter_column("next_attempt_at", nullable=False)
    op.create_index(
        "ix_report_delivery_attempts_next_attempt_at",
        "report_delivery_attempts",
        ["next_attempt_at"],
    )
    op.create_table(
        "technical_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_reference", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("serial_number", sa.String(120), nullable=False),
        sa.Column("tyre_brand", sa.String(100), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("branch_name", sa.String(120), nullable=False),
        sa.Column("report_data", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_reference"),
    )
    for column in (
        "claim_reference",
        "status",
        "customer_name",
        "invoice_number",
        "serial_number",
        "tyre_brand",
        "category",
        "branch_name",
        "created_by",
        "archived",
    ):
        op.create_index(f"ix_technical_reports_{column}", "technical_reports", [column])
    op.create_table(
        "report_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"], ["technical_reports.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_path"),
    )
    op.create_index("ix_report_images_report_id", "report_images", ["report_id"])
    op.create_index("ix_report_images_category", "report_images", ["category"])
    op.create_index("ix_report_images_sha256", "report_images", ["sha256"])
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"]
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"]
    )


def downgrade() -> None:
    op.drop_table("password_reset_tokens")
    op.drop_table("report_images")
    op.drop_table("technical_reports")
    op.drop_index(
        "ix_report_delivery_attempts_next_attempt_at",
        table_name="report_delivery_attempts",
    )
    op.drop_column("report_delivery_attempts", "next_attempt_at")
    op.drop_index("ix_users_external_subject", table_name="users")
    op.drop_column("users", "external_subject")
    op.drop_column("users", "external_provider")
