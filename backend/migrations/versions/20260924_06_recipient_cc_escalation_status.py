"""Support multiple default CC addresses and escalation status."""

import sqlalchemy as sa
from alembic import op

revision = "20260924_06"
down_revision = "20260923_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("report_recipients") as batch:
        batch.alter_column(
            "default_cc",
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=False,
        )
        batch.add_column(
            sa.Column(
                "escalation_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch.drop_column("escalation_hours")


def downgrade() -> None:
    with op.batch_alter_table("report_recipients") as batch:
        batch.add_column(
            sa.Column(
                "escalation_hours",
                sa.Integer(),
                nullable=False,
                server_default="24",
            )
        )
        batch.drop_column("escalation_enabled")
        batch.alter_column(
            "default_cc",
            existing_type=sa.Text(),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
