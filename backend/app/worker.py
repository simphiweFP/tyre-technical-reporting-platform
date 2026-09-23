import json
import logging
import signal
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import UUID

from sqlalchemy import or_, select

from backend.app.core.config import get_settings
from backend.app.core.database import SessionLocal
from backend.app.modules.administration.infrastructure import OperationalHeartbeat
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.delivery.application import ReportDeliveryService
from backend.app.modules.delivery.infrastructure import (
    DeliveryAttempt,
    SmtpEmailGateway,
)
from backend.app.modules.document_generation.application import GenerateTechnicalReport
from backend.app.modules.document_generation.infrastructure import (
    ReportLabTechnicalReportGenerator,
)

logger = logging.getLogger("delivery-worker")
stop_event = Event()


def update_heartbeat(processed: int = 0, errors: int = 0) -> None:
    with SessionLocal() as db:
        heartbeat = db.get(OperationalHeartbeat, "delivery-worker")
        if not heartbeat:
            heartbeat = OperationalHeartbeat(name="delivery-worker")
        heartbeat.last_seen_at = datetime.now(UTC)
        heartbeat.details = {"processed": processed, "errors": errors}
        db.add(heartbeat)
        db.commit()


def mark_processing_failure(delivery_id: UUID, error: Exception) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        attempt = db.get(DeliveryAttempt, delivery_id)
        if not attempt:
            return
        attempt.attempt_count += 1
        attempt.last_attempt_at = datetime.now(UTC)
        attempt.error_message = f"Delivery processing error: {error}"[:1000]
        attempt.status = (
            "Retrying"
            if attempt.attempt_count < settings.max_delivery_attempts
            else "Failed"
        )
        attempt.next_attempt_at = datetime.now(UTC) + timedelta(
            minutes=settings.delivery_retry_minutes * attempt.attempt_count
        )
        db.add(
            AuditEvent(
                actor_id=attempt.requested_by,
                action=(
                    "report.email_processing_retry"
                    if attempt.status == "Retrying"
                    else "report.email_processing_failed"
                ),
                entity_type="technical_report",
                entity_id=attempt.claim_reference,
                details={"delivery_id": str(attempt.id), "error": str(error)[:250]},
            )
        )
        db.commit()


def process_due_deliveries() -> tuple[int, int]:
    with SessionLocal() as db:
        due = db.scalars(
            select(DeliveryAttempt)
            .where(
                or_(
                    (
                        DeliveryAttempt.status.in_(("Pending", "Retrying"))
                        & (DeliveryAttempt.next_attempt_at <= datetime.now(UTC))
                    ),
                    (
                        (DeliveryAttempt.status == "Processing")
                        & (
                            DeliveryAttempt.last_attempt_at
                            <= datetime.now(UTC) - timedelta(minutes=10)
                        )
                    ),
                )
            )
            .order_by(DeliveryAttempt.next_attempt_at)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        claimed_at = datetime.now(UTC)
        for attempt in due:
            attempt.status = "Processing"
            attempt.last_attempt_at = claimed_at
        db.commit()
        delivery_ids = [attempt.id for attempt in due]

    processed = 0
    errors = 0
    for delivery_id in delivery_ids:
        try:
            with SessionLocal() as db:
                attempt = db.get(DeliveryAttempt, delivery_id)
                if not attempt or attempt.status != "Processing":
                    continue
                service = ReportDeliveryService(
                    db,
                    SmtpEmailGateway(get_settings()),
                    GenerateTechnicalReport(ReportLabTechnicalReportGenerator()),
                )
                service.deliver(attempt, attempt.requested_by)
                processed += 1
        except Exception as exc:
            errors += 1
            logger.exception(
                json.dumps(
                    {
                        "event": "delivery_processing_error",
                        "delivery_id": str(delivery_id),
                    }
                )
            )
            mark_processing_failure(delivery_id, exc)
    return processed, errors


def request_stop(signum, _frame) -> None:
    logger.info(json.dumps({"event": "worker_stopping", "signal": signum}))
    stop_event.set()


def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logger.info(json.dumps({"event": "worker_started"}))
    while not stop_event.is_set():
        processed, errors = process_due_deliveries()
        update_heartbeat(processed, errors)
        if processed or errors:
            logger.info(
                json.dumps(
                    {
                        "event": "delivery_batch_completed",
                        "processed": processed,
                        "errors": errors,
                    }
                )
            )
        stop_event.wait(5)
    logger.info(json.dumps({"event": "worker_stopped"}))


if __name__ == "__main__":
    run()
