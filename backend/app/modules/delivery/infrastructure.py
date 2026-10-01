import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage as SmtpMessage
from email.utils import make_msgid
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.config import Settings
from backend.app.core.database import Base
from backend.app.modules.delivery.domain import EmailMessage


class Recipient(Base):
    __tablename__ = "report_recipients"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    company: Mapped[str] = mapped_column(String(150))
    contact_name: Mapped[str] = mapped_column(String(150), default="")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    default_cc: Mapped[str] = mapped_column(Text, default="")
    branch_code: Mapped[str] = mapped_column(String(20), default="All Branches")
    category: Mapped[str] = mapped_column(String(100), default="All Categories")
    escalation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class DeliveryAttempt(Base):
    __tablename__ = "report_delivery_attempts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    claim_reference: Mapped[str] = mapped_column(String(80), index=True)
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("report_recipients.id"), index=True
    )
    recipient_email: Mapped[str] = mapped_column(String(255))
    cc: Mapped[list] = mapped_column(JSON, default=list)
    report_payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_pdf_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    follow_ups: Mapped[list] = mapped_column(JSON, default=list)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class SmtpEmailGateway:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, message: EmailMessage) -> str:
        email = SmtpMessage()
        email["Subject"] = message.subject
        email["From"] = f"{self.settings.email_from_name} <{self.settings.email_from}>"
        email["To"] = ", ".join(message.to)
        email["Message-ID"] = make_msgid()
        if message.in_reply_to:
            email["In-Reply-To"] = message.in_reply_to
        if message.references:
            email["References"] = message.references
        if message.cc:
            email["Cc"] = ", ".join(message.cc)
        email.set_content(message.body)
        if message.attachment is not None:
            email.add_attachment(
                message.attachment,
                maintype="application",
                subtype="pdf",
                filename=message.attachment_name,
            )
        with smtplib.SMTP(
            self.settings.smtp_host, self.settings.smtp_port, timeout=20
        ) as client:
            client.ehlo()
            if self.settings.smtp_use_tls:
                client.starttls()
                client.ehlo()
            if self.settings.smtp_username:
                client.login(self.settings.smtp_username, self.settings.smtp_password)
            client.send_message(email)
        return str(email["Message-ID"])
