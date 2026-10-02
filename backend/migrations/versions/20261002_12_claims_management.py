"""Claims handover, credit instructions and document delivery types."""

import sqlalchemy as sa
from alembic import op

revision = "20261002_12"
down_revision = "20261002_11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "claim_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "report_id",
            sa.Uuid(),
            sa.ForeignKey("technical_reports.id"),
            nullable=False,
        ),
        sa.Column("assigned_to", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "handed_over_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workflow_status", sa.String(30), nullable=False),
        sa.Column("handover_notes", sa.String(5000), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_claim_cases_report_id", "claim_cases", ["report_id"], unique=True
    )
    op.create_index("ix_claim_cases_assigned_to", "claim_cases", ["assigned_to"])
    op.create_table(
        "claim_credit_instructions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "case_id", sa.Uuid(), sa.ForeignKey("claim_cases.id"), nullable=False
        ),
        sa.Column("assigned_to", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_claim_credit_instructions_case_id", "claim_credit_instructions", ["case_id"]
    )
    op.create_index(
        "ix_claim_credit_instructions_assigned_to",
        "claim_credit_instructions",
        ["assigned_to"],
    )
    op.add_column(
        "report_delivery_attempts",
        sa.Column(
            "document_type", sa.String(40), nullable=False, server_default="technical"
        ),
    )


def downgrade():
    op.drop_column("report_delivery_attempts", "document_type")
    op.drop_table("claim_credit_instructions")
    op.drop_table("claim_cases")
