from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ClaimData(BaseModel):
    """Every Claim Tracker column, plus explicit amounts and feedback comments."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    claim_date: date
    supplier: str = Field(default="", max_length=200)
    supplier_code: str = Field(default="", max_length=100)
    tyre_size: str = Field(default="", max_length=100)
    damage: str = Field(default="", max_length=5000)
    remaining_tread_depth: float | None = Field(default=None, ge=0)
    original_tread_depth: float | None = Field(default=None, gt=0)
    supplier_submitted_date: date | None = None
    supplier_status: Literal["Under review", "Accepted", "Rejected"] = "Under review"
    accepted_percentage: float | None = Field(default=None, ge=0, le=100)
    supplier_feedback_date: date | None = None
    supplier_feedback_comments: str = Field(default="", max_length=5000)
    customer_credit_percentage: float | None = Field(default=None, ge=0, le=100)
    credit_note_reference: str = Field(default="", max_length=100)
    customer_credit_date: date | None = None
    supplier_offset_invoice: str = Field(default="", max_length=100)
    supplier_offset_date: date | None = None
    customer_credit_amount: float | None = Field(default=None, ge=0)
    supplier_recovered_amount: float | None = Field(default=None, ge=0)
    currency: Literal["ZAR"] = "ZAR"
    instruction_supplier: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def coherent_decision(self):
        if self.supplier_status != "Under review" and not self.supplier_feedback_date:
            raise ValueError("Supplier feedback date is required for a decision")
        if self.supplier_status == "Rejected":
            if self.accepted_percentage not in (None, 0):
                raise ValueError("Rejected claims cannot have an accepted percentage")
            if self.customer_credit_percentage not in (None, 0):
                raise ValueError(
                    "Rejected claims cannot have a customer credit percentage"
                )
            if not self.supplier_feedback_comments.strip():
                raise ValueError("Enter the supplier's rejection comments")
        if (
            self.remaining_tread_depth is not None
            and self.original_tread_depth is not None
            and self.remaining_tread_depth > self.original_tread_depth
        ):
            raise ValueError("Remaining tread depth cannot exceed original tread depth")
        if bool(self.credit_note_reference.strip()) != bool(self.customer_credit_date):
            raise ValueError("Enter both credit note reference and credit date")
        if bool(self.supplier_offset_invoice.strip()) != bool(
            self.supplier_offset_date
        ):
            raise ValueError("Enter both supplier offset invoice and offset date")
        for start, end, label in [
            (self.claim_date, self.supplier_submitted_date, "Supplier submission"),
            (
                self.supplier_submitted_date or self.claim_date,
                self.supplier_feedback_date,
                "Supplier feedback",
            ),
            (self.claim_date, self.customer_credit_date, "Customer credit"),
            (self.claim_date, self.supplier_offset_date, "Supplier offset"),
        ]:
            if start and end and end < start:
                raise ValueError(f"{label} date cannot precede the starting date")
        return self


class HandoverRequest(BaseModel):
    report_id: UUID
    assigned_to: UUID
    notes: str = Field(default="", max_length=5000)


class ClaimUpdate(BaseModel):
    data: ClaimData
    workflow_status: Literal["Received", "In progress", "Closed"] = "In progress"
    expected_updated_at: datetime


class InstructionRequest(BaseModel):
    supplier: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=5000)


class DocumentSendRequest(BaseModel):
    recipient_email: EmailStr
    cc: list[EmailStr] = Field(default_factory=list, max_length=5)
    body: str = Field(default="", max_length=5000)
    instruction_id: UUID | None = None


class ReassignRequest(BaseModel):
    assigned_to: UUID
    notes: str = Field(default="", max_length=5000)
