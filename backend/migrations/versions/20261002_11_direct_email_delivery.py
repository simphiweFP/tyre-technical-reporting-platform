"""Allow report delivery directly to an entered email address."""

import sqlalchemy as sa
from alembic import op

revision = "20261002_11"
down_revision = "20261001_10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("report_delivery_attempts") as batch:
        batch.alter_column(
            "recipient_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("report_delivery_attempts") as batch:
        batch.alter_column(
            "recipient_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )
