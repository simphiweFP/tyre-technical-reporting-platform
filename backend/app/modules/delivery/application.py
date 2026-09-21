from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.delivery.domain import EmailGateway, EmailMessage
from backend.app.modules.delivery.infrastructure import DeliveryAttempt, Recipient
from backend.app.modules.document_generation.application import GenerateTechnicalReport


class ReportDeliveryService:
    def __init__(self, db: Session, gateway: EmailGateway, generator: GenerateTechnicalReport):
        self.db = db
        self.gateway = gateway
        self.generator = generator

    def deliver(self, attempt: DeliveryAttempt, actor_id) -> DeliveryAttempt:
        recipient = self.db.get(Recipient, attempt.recipient_id)
        if not recipient or not recipient.is_active:
            raise ValueError("The selected recipient is not active")
        pdf = self.generator.execute(attempt.report_payload)
        claim = attempt.claim_reference
        message = EmailMessage(
            subject=f"Royal Tyres technical report {claim}",
            body=f"Please find the Royal Tyres technical report {claim} attached.\n\nThis is an automated delivery.",
            to=(recipient.email,),
            cc=tuple(attempt.cc),
            attachment_name=f"{claim}.pdf",
            attachment=pdf,
        )
        attempt.attempt_count = max(1, attempt.attempt_count)
        attempt.last_attempt_at = datetime.now(UTC)
        try:
            attempt.message_id = self.gateway.send(message)
            attempt.status = "Sent"
            attempt.error_message = None
        except Exception as exc:
            attempt.status = "Failed"
            attempt.error_message = str(exc)[:1000]
        self.db.add(
            AuditEvent(
                actor_id=actor_id,
                action="report.email_sent" if attempt.status == "Sent" else "report.email_failed",
                entity_type="technical_report",
                entity_id=claim,
                details={"delivery_id": str(attempt.id), "recipient": recipient.email, "attempt": attempt.attempt_count},
            )
        )
        self.db.commit()
        self.db.refresh(attempt)
        return attempt
