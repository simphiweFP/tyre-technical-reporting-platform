from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class ClaimCase(Base):
    __tablename__ = "claim_cases"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("technical_reports.id"), unique=True, index=True
    )
    assigned_to: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    handed_over_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    workflow_status: Mapped[str] = mapped_column(String(30), default="Received")
    handover_notes: Mapped[str] = mapped_column(String(5000), default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class CreditInstruction(Base):
    __tablename__ = "claim_credit_instructions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("claim_cases.id"), index=True)
    assigned_to: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    data: Mapped[dict] = mapped_column(JSON)
