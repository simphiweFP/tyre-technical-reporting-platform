from datetime import UTC, date, datetime, time
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.branches.infrastructure import Branch
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.reports.customer_lookup import load_json_customers
from backend.app.modules.reports.infrastructure import (
    ReportImage,
    TechnicalReportRecord,
)
from backend.app.modules.reports.schemas import (
    AnalyticsResponse,
    ImageResponse,
    ReferenceOption,
    ReportListResponse,
    ReportReferenceDataResponse,
    ReportResponse,
    ReportUpsertRequest,
)
from backend.app.modules.reports.validation import validate_report


class TechnicalReportService:
    def __init__(self, db: Session):
        self.db = db

    def reference_data(self, user: User) -> ReportReferenceDataResponse:
        branches = self.db.scalars(
            select(Branch)
            .where(
                Branch.is_active.is_(True),
                Branch.deleted_at.is_(None),
            )
            .order_by(Branch.name)
        ).all()
        records_query = select(TechnicalReportRecord).where(
            TechnicalReportRecord.archived.is_(False)
        )
        if user.role == Role.REPORT_CAPTURER:
            records_query = records_query.where(
                TechnicalReportRecord.created_by == user.id
            )
        records = self.db.scalars(records_query).all()

        def report_values(field: str) -> list[str]:
            return sorted(
                {
                    str(record.report_data.get(field) or "").strip()
                    for record in records
                    if str(record.report_data.get(field) or "").strip()
                }
            )

        brands = sorted(
            set(report_values("brand"))
            | {
                "Bridgestone",
                "Continental",
                "Dunlop",
                "Goodyear",
                "Hankook",
                "Michelin",
            }
        )
        return ReportReferenceDataResponse(
            branches=[
                ReferenceOption(value=branch.code, label=branch.name)
                for branch in branches
            ],
            customers=load_json_customers() or report_values("customerName"),
            categories=["Manufacturing", "Road hazard", "Service related"],
            brands=brands,
            patterns=report_values("pattern"),
            tyre_positions=[
                "Front left",
                "Front right",
                "Rear left",
                "Rear right",
                "Spare",
            ],
        )

    def analytics(self, user: User) -> AnalyticsResponse:
        records_query = select(TechnicalReportRecord).where(
            TechnicalReportRecord.archived.is_(False)
        )
        if user.role == Role.REPORT_CAPTURER:
            records_query = records_query.where(
                TechnicalReportRecord.created_by == user.id
            )
        records = self.db.scalars(records_query).all()

        def group(attribute: str) -> dict[str, int]:
            result: dict[str, int] = {}
            for record in records:
                value = str(getattr(record, attribute) or "Unspecified")
                result[value] = result.get(value, 0) + 1
            return dict(sorted(result.items(), key=lambda item: (-item[1], item[0])))

        by_month: dict[str, int] = {}
        for record in records:
            month = record.created_at.strftime("%Y-%m")
            by_month[month] = by_month.get(month, 0) + 1

        return AnalyticsResponse(
            total=len(records),
            drafts=sum(record.status == "Draft" for record in records),
            completed=sum(
                record.status in {"Submitted", "Email Sent"} for record in records
            ),
            email_failed=sum(record.status == "Email Failed" for record in records),
            by_status=group("status"),
            by_branch=group("branch_name"),
            by_brand=group("tyre_brand"),
            by_category=group("category"),
            by_month=dict(sorted(by_month.items())),
        )

    def list_reports(
        self,
        user: User,
        *,
        query: str = "",
        report_status: str = "",
        branch: str = "",
        date_from: date | None = None,
        date_to: date | None = None,
        include_archived: bool = False,
        archived_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> ReportListResponse:
        statement = select(TechnicalReportRecord).order_by(
            TechnicalReportRecord.updated_at.desc()
        )
        if user.role == Role.REPORT_CAPTURER:
            statement = statement.where(TechnicalReportRecord.created_by == user.id)
        if archived_only:
            statement = statement.where(TechnicalReportRecord.archived.is_(True))
        elif not include_archived:
            statement = statement.where(TechnicalReportRecord.archived.is_(False))

        if branch:
            matched_branch = self.db.scalar(
                select(Branch).where(
                    Branch.deleted_at.is_(None),
                    or_(Branch.code == branch, Branch.name == branch),
                )
            )
            branch_values = {branch}
            if matched_branch:
                branch_values.update({matched_branch.code, matched_branch.name})
            statement = statement.where(
                TechnicalReportRecord.branch_name.in_(branch_values)
            )

        if date_from:
            statement = statement.where(
                TechnicalReportRecord.created_at
                >= datetime.combine(date_from, time.min)
            )
        if date_to:
            statement = statement.where(
                TechnicalReportRecord.created_at <= datetime.combine(date_to, time.max)
            )

        records = self.db.scalars(statement).all()
        if query.strip():
            term = query.strip().casefold()

            def matches(record: TechnicalReportRecord) -> bool:
                data = record.report_data or {}
                values = (
                    record.claim_reference,
                    record.customer_name,
                    record.invoice_number,
                    record.serial_number,
                    record.tyre_brand,
                    data.get("dot"),
                    data.get("pattern"),
                    data.get("vehicleMakeModel"),
                )
                return any(term in str(value or "").casefold() for value in values)

            records = [record for record in records if matches(record)]

        status_counts: dict[str, int] = {}
        for record in records:
            status_counts[record.status] = status_counts.get(record.status, 0) + 1

        matching_total = len(records)
        if report_status:
            records = [record for record in records if record.status == report_status]

        return ReportListResponse(
            items=[
                self.response(record)
                for record in records[offset : offset + limit]
            ],
            total=len(records),
            matching_total=matching_total,
            status_counts=status_counts,
        )

    def upsert(
        self,
        report_id: UUID,
        request: ReportUpsertRequest,
        user: User,
    ) -> ReportResponse:
        data = request.report
        if data.get("status") != "Draft":
            errors = validate_report(data, 3)
            if errors:
                raise HTTPException(status_code=422, detail={"fields": errors})

        record = self.db.get(TechnicalReportRecord, report_id)
        created = record is None
        if record:
            self.ensure_access(record, user)

        if (
            record
            and request.expected_updated_at
            and self.as_utc(record.updated_at)
            != self.as_utc(request.expected_updated_at)
        ):
            raise HTTPException(
                status_code=409,
                detail="Report changed on the server while this device was offline",
            )

        if created:
            duplicate = self.db.scalar(
                select(TechnicalReportRecord).where(
                    TechnicalReportRecord.claim_reference
                    == str(data.get("claimReference", ""))
                )
            )
            if duplicate:
                raise HTTPException(
                    status_code=409, detail="Claim reference already exists"
                )
            record = TechnicalReportRecord(
                id=report_id,
                claim_reference=str(data.get("claimReference") or report_id),
                created_by=user.id,
            )

        record.status = str(data.get("status") or "Draft")
        record.customer_name = str(data.get("customerName") or "")
        record.invoice_number = str(data.get("customerInvoiceNumber") or "")
        record.serial_number = str(data.get("serialNumber") or "")
        record.tyre_brand = str(data.get("brand") or "")
        record.category = str(data.get("category") or "")
        record.branch_name = str(data.get("branch") or "")
        record.report_data = {**data, "photos": []}
        record.updated_at = datetime.now(UTC)
        self.db.add(record)
        self.db.add(
            AuditEvent(
                actor_id=user.id,
                action="report.created" if created else "report.updated",
                entity_type="technical_report",
                entity_id=str(report_id),
                details={
                    "claim_reference": record.claim_reference,
                    "status": record.status,
                },
            )
        )
        self.db.commit()
        self.db.refresh(record)
        return self.response(record)

    def response(self, record: TechnicalReportRecord) -> ReportResponse:
        images = self.db.scalars(
            select(ReportImage)
            .where(ReportImage.report_id == record.id)
            .order_by(ReportImage.captured_at)
        ).all()
        return ReportResponse(
            id=record.id,
            report={
                **record.report_data,
                "id": str(record.id),
                "claimReference": record.claim_reference,
                "status": record.status,
                "photos": [
                    ImageResponse.model_validate(image).model_dump(mode="json")
                    for image in images
                ],
            },
            archived=record.archived,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def ensure_access(record: TechnicalReportRecord, user: User) -> None:
        if user.role == Role.REPORT_CAPTURER and record.created_by != user.id:
            raise HTTPException(status_code=404, detail="Report not found")

    @staticmethod
    def as_utc(value: datetime) -> datetime:
        return (
            value.replace(tzinfo=UTC)
            if value.tzinfo is None
            else value.astimezone(UTC)
        )
