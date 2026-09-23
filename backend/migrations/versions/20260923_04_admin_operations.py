"""Add branch routing, recipient rules and persisted system settings."""

import sqlalchemy as sa
from alembic import op

revision = "20260923_04"
down_revision = "20260921_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("branches", sa.Column("routing_email", sa.String(255), nullable=True))
    op.execute("UPDATE branches SET routing_email = '' WHERE routing_email IS NULL")
    with op.batch_alter_table("branches") as batch:
        batch.alter_column("routing_email", nullable=False)
    op.add_column(
        "report_recipients", sa.Column("branch_code", sa.String(20), nullable=True)
    )
    op.add_column(
        "report_recipients", sa.Column("category", sa.String(100), nullable=True)
    )
    op.add_column(
        "report_recipients", sa.Column("escalation_hours", sa.Integer(), nullable=True)
    )
    op.execute(
        "UPDATE report_recipients "
        "SET branch_code='All Branches', category='All Categories', "
        "escalation_hours=24"
    )
    with op.batch_alter_table("report_recipients") as batch:
        batch.alter_column("branch_code", nullable=False)
        batch.alter_column("category", nullable=False)
        batch.alter_column("escalation_hours", nullable=False)
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_column("report_recipients", "escalation_hours")
    op.drop_column("report_recipients", "category")
    op.drop_column("report_recipients", "branch_code")
    op.drop_column("branches", "routing_email")
