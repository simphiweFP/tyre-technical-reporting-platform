"""Add operational heartbeat tracking."""

import sqlalchemy as sa
from alembic import op

revision = "20260923_05"
down_revision = "20260923_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_heartbeats",
        sa.Column("name", sa.String(length=100), primary_key=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("operational_heartbeats")
