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
from backend.app.modules.reports.storage import ReportFileStorage


class ReportDeliveryService:
    def __init__(
        self, db: Session, gateway: EmailGateway, generator: GenerateTechnicalReport
    ):
        self.db = db
        self.gateway = gateway
        self.generator = generator

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
            storage = ReportFileStorage()
            images = self.db.scalars(
                select(ReportImage)
                .where(ReportImage.report_id == report_record.id)
                .order_by(ReportImage.captured_at)
            ).all()
            report = {
                **report_record.report_data,
                "photos": [
                    {
                        "category": image.category,
                        "label": image.category.replace("_", " ").title(),
                        "filePath": str(storage.resolve(image.file_path)),
                    }
                    for image in images
                ],
            }
        pdf = self.generator.execute(report)
        claim = attempt.claim_reference
        message = EmailMessage(
            subject=f"Royal Tyres technical report {claim}",
            body=(
                f"Please find the Royal Tyres technical report {claim} attached.\n\n"
                "This is an automated delivery."
            ),
            to=(recipient.email,),
            cc=tuple(attempt.cc),
            attachment_name=f"{claim}.pdf",
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
            attempt.status = (
                "Retrying"
                if attempt.attempt_count < settings.max_delivery_attempts
                else "Failed"
            )
            attempt.error_message = str(exc)[:1000]
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
