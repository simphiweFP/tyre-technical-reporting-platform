from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DeliveryRequest(BaseModel):
    recipient_email: EmailStr
    report: dict[str, Any]
    cc: list[EmailStr] = Field(default_factory=list, max_length=5)


class DeliveryResponse(BaseModel):
    id: UUID
    claim_reference: str
    document_type: str = "technical"
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


class FollowUpRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
