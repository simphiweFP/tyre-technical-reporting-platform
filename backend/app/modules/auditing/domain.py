from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: UUID
    actor_id: UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict
    occurred_at: datetime
