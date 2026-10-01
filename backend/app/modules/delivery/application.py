import base64
import hashlib
import smtplib
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.delivery.domain import EmailGateway, EmailMessage
from backend.app.modules.delivery.infrastructure import DeliveryAttempt, Recipient
from backend.app.modules.document_generation.application import GenerateTechnicalReport
from backend.app.modules.reports.infrastructure import (
    ReportImage,
    TechnicalReportRecord,
)

PHOTO_LABELS = {
    "dot": "DOT",
    "serialNumber": "SERIAL NUMBER",
    "entireTyreDot": "ENTIRE TYRE (sw DOT)",
    "entireTyreOpposite": "ENTIRE TYRE (sw opposite DOT)",
    "issue1": "ISSUE 1",
    "issue2": "ISSUE 2",
    "bead1": "BEAD 1",
    "bead2": "BEAD 2",
    "fullView": "FULL VIEW",
    "internalCarcass1": "INTERNAL CARCASS 1",
    "internalCarcass2": "INTERNAL CARCASS 2",
    "treadDepth1": "TREAD DEPTH 1",
    "treadDepth2": "TREAD DEPTH 2",
    "treadDepth3": "TREAD DEPTH 3",
    "treadPattern": "TREAD PATTERN",
    "vehicle": "VEHICLE",
}


def _delivery_error_message(exc: Exception, recipient_email: str) -> str:
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        details = exc.recipients.get(recipient_email) or next(
            iter(exc.recipients.values()),
            None,
        )
        smtp_detail = ""
        if details:
            code, message = details
            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="replace")
            smtp_detail = f" SMTP {code}: {message}"
        return (
            f"The recipient email address {recipient_email} could not receive the message."
            f"{smtp_detail}"
        )

    if isinstance(exc, smtplib.SMTPDataError):
        return (
            f"The mail server rejected the message for {recipient_email}. "
            f"SMTP {exc.smtp_code}: "
            f"{exc.smtp_error.decode('utf-8', errors='replace') if isinstance(exc.smtp_error, bytes) else exc.smtp_error}"
        )

    if isinstance(exc, smtplib.SMTPSenderRefused):
        return (
            "The sending mailbox was rejected by the mail server. "
            f"SMTP {exc.smtp_code}: "
            f"{exc.smtp_error.decode('utf-8', errors='replace') if isinstance(exc.smtp_error, bytes) else exc.smtp_error}"
        )

    return str(exc)[:1000] or exc.__class__.__name__


class ReportDeliveryService:
    def __init__(
        self, db: Session, gateway: EmailGateway, generator: GenerateTechnicalReport
    ):
        self.db = db
        self.gateway = gateway
        self.generator = generator

    def follow_up(
        self,
        attempt: DeliveryAttempt,
        actor_id,
        body: str,
    ) -> str:
        if attempt.status != "Sent":
            raise ValueError("Follow-up is only available for sent emails")

        original_subject = (
            attempt.email_subject
            or f"Royal Tyres technical report {attempt.claim_reference}"
        )
        subject = f"Re: {original_subject}"
        message = EmailMessage(
            subject=subject,
            body=body.strip(),
            to=(attempt.recipient_email,),
            cc=tuple(attempt.cc),
            in_reply_to=attempt.message_id,
            references=attempt.message_id,
        )
        try:
            message_id = self.gateway.send(message)
        except Exception as exc:
            self.db.add(
                AuditEvent(
                    actor_id=actor_id,
                    action="report.email_follow_up_failed",
                    entity_type="delivery_attempt",
                    entity_id=str(attempt.id),
                    details={
                        "claim_reference": attempt.claim_reference,
                        "recipient": attempt.recipient_email,
                        "error": str(exc)[:500],
                    },
                )
            )
            self.db.commit()
            raise

        sent_at = datetime.now(UTC)
        attempt.follow_ups = [
            *(attempt.follow_ups or []),
            {
                "body": body.strip(),
                "sent_at": sent_at.isoformat(),
                "message_id": message_id,
                "in_reply_to": attempt.message_id,
                "recipient": attempt.recipient_email,
                "actor_id": str(actor_id),
            },
        ]
        self.db.add(
            AuditEvent(
                actor_id=actor_id,
                action="report.email_follow_up_sent",
                entity_type="delivery_attempt",
                entity_id=str(attempt.id),
                details={
                    "claim_reference": attempt.claim_reference,
                    "recipient": attempt.recipient_email,
                    "message_id": message_id,
                    "in_reply_to": attempt.message_id,
                },
            )
        )
        self.db.commit()
        return message_id

    def soft_delete(self, attempt: DeliveryAttempt, actor_id) -> None:
        attempt.deleted_at = datetime.now(UTC)
        self.db.add(
            AuditEvent(
                actor_id=actor_id,
                action="report.email_soft_deleted",
                entity_type="delivery_attempt",
                entity_id=str(attempt.id),
                details={"claim_reference": attempt.claim_reference},
            )
        )
        self.db.commit()

    @staticmethod
    def snapshot_pdf(attempt: DeliveryAttempt) -> bytes | None:
        if not attempt.sent_pdf_base64:
            return None
        return base64.b64decode(attempt.sent_pdf_base64)

    def deliver(self, attempt: DeliveryAttempt, actor_id) -> DeliveryAttempt:
        recipient = self.db.get(Recipient, attempt.recipient_id)
        if not recipient or not recipient.is_active:
            raise ValueError("The selected recipient is not active")
        report_record = self.db.scalar(
            select(TechnicalReportRecord).where(
                TechnicalReportRecord.claim_reference == attempt.claim_reference
            )
        )
        report = attempt.report_payload
        if report_record:
            images = self.db.scalars(
                select(ReportImage)
                .where(ReportImage.report_id == report_record.id)
                .order_by(ReportImage.captured_at)
            ).all()
            photo_comments = report_record.report_data.get("photoComments") or {}
            report = {
                **report_record.report_data,
                "photos": [
                    {
                        "category": image.category,
                        "label": PHOTO_LABELS.get(
                            image.category,
                            image.category.replace("_", " ").title(),
                        ),
                        "previewUrl": (
                            f"data:{image.content_type};base64,{image.base64_data}"
                        ),
                        "comment": str(photo_comments.get(image.category) or ""),
                    }
                    for image in images
                ],
            }
        claim = attempt.claim_reference
        subject = attempt.email_subject or f"Royal Tyres technical report {claim}"
        body = attempt.email_body or (
            f"Please find the Royal Tyres technical report {claim} attached.\n\n"
            "This is an automated delivery."
        )
        attachment_name = attempt.attachment_name or f"{claim}.pdf"

        # The first send creates an immutable snapshot. Retries reuse the exact
        # same PDF bytes and email content rather than regenerating a changed report.
        if attempt.sent_pdf_base64:
            pdf = base64.b64decode(attempt.sent_pdf_base64)
        else:
            pdf = self.generator.execute(report)
            attempt.email_subject = subject
            attempt.email_body = body
            attempt.attachment_name = attachment_name
            attempt.sent_pdf_base64 = base64.b64encode(pdf).decode("ascii")
            attempt.sent_pdf_sha256 = hashlib.sha256(pdf).hexdigest()

        message = EmailMessage(
            subject=subject,
            body=body,
            to=(recipient.email,),
            cc=tuple(attempt.cc),
            attachment_name=attachment_name,
            attachment=pdf,
        )
        attempt.attempt_count += 1
        attempt.last_attempt_at = datetime.now(UTC)
        try:
            attempt.message_id = self.gateway.send(message)
            attempt.status = "Sent"
            attempt.error_message = None
            if report_record:
                report_record.status = "Email Sent"
        except Exception as exc:
            settings = get_settings()
            permanent_recipient_failure = isinstance(
                exc,
                (
                    smtplib.SMTPRecipientsRefused,
                    smtplib.SMTPSenderRefused,
                ),
            )
            attempt.status = (
                "Failed"
                if permanent_recipient_failure
                else "Retrying"
                if attempt.attempt_count < settings.max_delivery_attempts
                else "Failed"
            )
            attempt.error_message = _delivery_error_message(
                exc,
                recipient.email,
            )[:1000]
            attempt.next_attempt_at = datetime.now(UTC) + timedelta(
                minutes=settings.delivery_retry_minutes * attempt.attempt_count
            )
            if report_record and attempt.status == "Failed":
                report_record.status = "Email Failed"
        self.db.add(
            AuditEvent(
                actor_id=actor_id,
                action="report.email_sent"
                if attempt.status == "Sent"
                else "report.email_retry_scheduled"
                if attempt.status == "Retrying"
                else "report.email_failed",
                entity_type="technical_report",
                entity_id=claim,
                details={
                    "delivery_id": str(attempt.id),
                    "recipient": recipient.email,
                    "attempt": attempt.attempt_count,
                },
            )
        )
        self.db.commit()
        self.db.refresh(attempt)
        return attempt
