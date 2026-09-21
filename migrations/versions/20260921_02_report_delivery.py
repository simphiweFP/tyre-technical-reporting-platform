"""Create report recipients and delivery history."""
from alembic import op
import sqlalchemy as sa

revision = "20260921_02"
down_revision = "20260921_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_recipients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(150), nullable=False),
        sa.Column("contact_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("default_cc", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_report_recipients_email", "report_recipients", ["email"])
    op.create_table(
        "report_delivery_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("claim_reference", sa.String(80), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("cc", sa.JSON(), nullable=False),
        sa.Column("report_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["report_recipients.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_delivery_attempts_claim_reference", "report_delivery_attempts", ["claim_reference"])
    op.create_index("ix_report_delivery_attempts_recipient_id", "report_delivery_attempts", ["recipient_id"])
    op.create_index("ix_report_delivery_attempts_requested_by", "report_delivery_attempts", ["requested_by"])
    op.create_index("ix_report_delivery_attempts_status", "report_delivery_attempts", ["status"])


def downgrade() -> None:
    op.drop_table("report_delivery_attempts")
    op.drop_table("report_recipients")
