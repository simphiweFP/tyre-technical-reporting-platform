from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    ADMINISTRATOR = "administrator"
    REPORT_CAPTURER = "report_capturer"
    VIEWER = "viewer"


@dataclass(frozen=True, slots=True)
class UserIdentity:
    id: UUID
    email: str
    full_name: str
    job_title: str | None
    role: Role
    branch_id: UUID | None
    is_active: bool

