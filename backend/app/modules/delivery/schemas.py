from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RecipientCreate(BaseModel):
    company: str = Field(min_length=2, max_length=150)
    contact_name: str = Field(default="", max_length=150)
    email: EmailStr
    default_cc: list[EmailStr] = Field(default_factory=list, max_length=10)
    branch_code: str = Field(default="All Branches", max_length=20)
    category: str = Field(default="All Categories", max_length=100)
    escalation_enabled: bool = True


class RecipientUpdate(RecipientCreate):
    is_active: bool = True


class RecipientResponse(BaseModel):
    id: UUID
    company: str
    contact_name: str
    email: EmailStr
    default_cc: list[EmailStr]
    branch_code: str
    category: str
    escalation_enabled: bool
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

    @field_validator("default_cc", mode="before")
    @classmethod
    def parse_default_cc(cls, value):
        if isinstance(value, str):
            return [address.strip() for address in value.split(",") if address.strip()]
        return value or []


class DeliveryRequest(BaseModel):
    recipient_id: UUID
    report: dict[str, Any]
    cc: list[EmailStr] = Field(default_factory=list, max_length=5)


class DeliveryResponse(BaseModel):
    id: UUID
    claim_reference: str
    recipient_email: str
    cc: list[str]
    status: str
    attempt_count: int
    message_id: str | None
    error_message: str | None
    created_at: datetime
    last_attempt_at: datetime
    next_attempt_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DeliveryListResponse(BaseModel):
    items: list[DeliveryResponse]
    total: int
