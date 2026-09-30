"""Add immutable delivery snapshots and soft-delete timestamp."""

import sqlalchemy as sa
from alembic import op

revision = "20260930_08"
down_revision = "20260927_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("report_delivery_attempts") as batch:
        batch.add_column(
            sa.Column("email_subject", sa.String(length=500), nullable=True)
        )
        batch.add_column(sa.Column("email_body", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("attachment_name", sa.String(length=255), nullable=True)
        )
        batch.add_column(sa.Column("sent_pdf_base64", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("sent_pdf_sha256", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index(
            "ix_report_delivery_attempts_deleted_at",
            ["deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("report_delivery_attempts") as batch:
        batch.drop_index("ix_report_delivery_attempts_deleted_at")
        batch.drop_column("deleted_at")
        batch.drop_column("sent_pdf_sha256")
        batch.drop_column("sent_pdf_base64")
        batch.drop_column("attachment_name")
        batch.drop_column("email_body")
        batch.drop_column("email_subject")
