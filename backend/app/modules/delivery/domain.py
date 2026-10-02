from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmailMessage:
    subject: str
    body: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    attachment_name: str | None = None
    attachment: bytes | None = None
    in_reply_to: str | None = None
    references: str | None = None
    attachment_content_type: str = "application/pdf"


class EmailGateway(Protocol):
    def send(self, message: EmailMessage) -> str: ...
