from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: UUID
    actor: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict[str, Any]
    occurred_at: datetime


class AuditListResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
