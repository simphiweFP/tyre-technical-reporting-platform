"""Add soft delete timestamps to admin-managed records."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_09"
down_revision = "20260930_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("branches") as batch:
        batch.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index("ix_branches_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index("ix_users_deleted_at", ["deleted_at"], unique=False)

    with op.batch_alter_table("report_recipients") as batch:
        batch.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_index(
            "ix_report_recipients_deleted_at",
            ["deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("report_recipients") as batch:
        batch.drop_index("ix_report_recipients_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_deleted_at")
        batch.drop_column("deleted_at")

    with op.batch_alter_table("branches") as batch:
        batch.drop_index("ix_branches_deleted_at")
        batch.drop_column("deleted_at")
