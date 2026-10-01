"""Store sent follow-up email history on delivery attempts."""

import sqlalchemy as sa
from alembic import op

revision = "20261001_10"
down_revision = "20261001_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("report_delivery_attempts") as batch:
        batch.add_column(
            sa.Column("follow_ups", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("report_delivery_attempts") as batch:
        batch.drop_column("follow_ups")
