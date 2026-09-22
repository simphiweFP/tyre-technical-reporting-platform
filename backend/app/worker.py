import logging
import time
from datetime import UTC, datetime

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.core.database import SessionLocal
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


def process_due_deliveries() -> int:
    with SessionLocal() as db:
        due = db.scalars(
            select(DeliveryAttempt)
            .where(
                DeliveryAttempt.status.in_(("Pending", "Retrying")),
                DeliveryAttempt.next_attempt_at <= datetime.now(UTC),
            )
            .order_by(DeliveryAttempt.next_attempt_at)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        service = ReportDeliveryService(
            db,
            SmtpEmailGateway(get_settings()),
            GenerateTechnicalReport(ReportLabTechnicalReportGenerator()),
        )
        for attempt in due:
            service.deliver(attempt, attempt.requested_by)
        return len(due)


def run() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    while True:
        count = process_due_deliveries()
        if count:
            logger.info("processed_delivery_batch count=%s", count)
        time.sleep(5)


if __name__ == "__main__":
    run()
