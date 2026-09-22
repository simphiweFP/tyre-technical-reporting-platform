from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BranchDetails:
    id: UUID
    code: str
    name: str
    is_active: bool
