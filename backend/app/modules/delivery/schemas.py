from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RecipientCreate(BaseModel):
    company: str = Field(min_length=2, max_length=150)
    contact_name: str = Field(default="", max_length=150)
    email: EmailStr
    default_cc: EmailStr | None = None


class RecipientResponse(BaseModel):
    id: UUID
    company: str
    contact_name: str
    email: EmailStr
    default_cc: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)
