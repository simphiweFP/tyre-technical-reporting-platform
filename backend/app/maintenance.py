from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from backend.app.core.config import get_settings
from backend.app.core.database import SessionLocal
from backend.app.modules.reports.infrastructure import (
    ReportImage,
    TechnicalReportRecord,
)


def purge_expired_archived_reports() -> int:
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().report_retention_days)
    removed = 0
    with SessionLocal() as db:
        reports = db.scalars(
            select(TechnicalReportRecord).where(
                TechnicalReportRecord.archived.is_(True),
                TechnicalReportRecord.updated_at < cutoff,
            )
        ).all()
        for report in reports:
            for image in db.scalars(
                select(ReportImage).where(ReportImage.report_id == report.id)
            ):
                Path(image.file_path).unlink(missing_ok=True)
            db.delete(report)
            removed += 1
        db.commit()
    return removed


if __name__ == "__main__":
    print(f"Purged {purge_expired_archived_reports()} expired archived reports")
