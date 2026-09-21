from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EmailMessage:
    subject: str
    body: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    attachment_name: str
    attachment: bytes


class EmailGateway(Protocol):
    def send(self, message: EmailMessage) -> str: ...
