import hashlib
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.document_generation.application import GenerateTechnicalReport
from backend.app.modules.document_generation.infrastructure import (
    ReportLabTechnicalReportGenerator,
)
from backend.app.modules.document_generation.schemas import TechnicalReportPdfRequest
from backend.app.modules.identity.dependencies import require_roles
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.media.application import AnalyseTyreImage
from backend.app.modules.media.infrastructure import TesseractTyreExtractor
from backend.app.modules.media.schemas import (
    ExtractedValueResponse,
    ImageAnalysisResponse,
)
from backend.app.modules.reports.infrastructure import (
    ReportImage,
    TechnicalReportRecord,
)
from backend.app.modules.reports.schemas import (
    AnalyticsResponse,
    ImageResponse,
    ReportListResponse,
    ReportResponse,
    ReportUpsertRequest,
)

router = APIRouter(prefix="/reports", tags=["Technical reports"])
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.get("/analytics/summary", response_model=AnalyticsResponse)
def analytics_summary(
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    records = db.scalars(
        select(TechnicalReportRecord).where(TechnicalReportRecord.archived.is_(False))
    ).all()

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


@router.get("/records", response_model=ReportListResponse)
def list_reports(
    query: str = "",
    report_status: str = "",
    branch: str = "",
    include_archived: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=250),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    statement = select(TechnicalReportRecord).order_by(
        TechnicalReportRecord.updated_at.desc()
    )
    if not include_archived:
        statement = statement.where(TechnicalReportRecord.archived.is_(False))
    if report_status:
        statement = statement.where(TechnicalReportRecord.status == report_status)
    if branch:
        statement = statement.where(TechnicalReportRecord.branch_name == branch)
    if query:
        term = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                TechnicalReportRecord.claim_reference.ilike(term),
                TechnicalReportRecord.customer_name.ilike(term),
                TechnicalReportRecord.invoice_number.ilike(term),
                TechnicalReportRecord.serial_number.ilike(term),
                TechnicalReportRecord.tyre_brand.ilike(term),
            )
        )
    records = db.scalars(statement).all()
    total = len(records)
    return ReportListResponse(
        items=[
            _report_response(record, db) for record in records[offset : offset + limit]
        ],
        total=total,
    )


@router.get("/records/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    return _required_report(report_id, db)


@router.put("/records/{report_id}", response_model=ReportResponse)
def upsert_report(
    report_id: UUID,
    request: ReportUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    data = request.report
    record = db.get(TechnicalReportRecord, report_id)
    created = record is None
    if created:
        duplicate = db.scalar(
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
    db.add(record)
    db.add(
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
    db.commit()
    db.refresh(record)
    return _report_response(record, db)


@router.post("/records/{report_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    record = _required_record(report_id, db)
    record.archived = True
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="report.archived",
            entity_type="technical_report",
            entity_id=str(report_id),
            details={"claim_reference": record.claim_reference},
        )
    )
    db.commit()


@router.post(
    "/records/{report_id}/images",
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_report_image(
    report_id: UUID,
    category: str,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    _required_record(report_id, db)
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415, detail="Only JPEG, PNG and WebP images are supported"
        )
    content = await image.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="The image exceeds the 8 MB limit")
    try:
        PillowImage.open(BytesIO(content)).verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=422, detail="The uploaded file is not a valid image"
        ) from exc
    digest = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(ReportImage).where(
            ReportImage.report_id == report_id,
            ReportImage.sha256 == digest,
            ReportImage.category != category,
        )
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="This image is already used in another category"
        )
    previous = db.scalar(
        select(ReportImage).where(
            ReportImage.report_id == report_id, ReportImage.category == category
        )
    )
    if previous:
        Path(previous.file_path).unlink(missing_ok=True)
        db.delete(previous)
        db.flush()
    root = Path(get_settings().media_root).resolve() / str(report_id)
    root.mkdir(parents=True, exist_ok=True)
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[
        image.content_type
    ]
    path = root / f"{category}-{digest[:16]}{suffix}"
    path.write_bytes(content)
    stored = ReportImage(
        report_id=report_id,
        category=category,
        original_name=image.filename or path.name,
        content_type=image.content_type,
        file_path=str(path),
        sha256=digest,
        byte_size=len(content),
    )
    db.add(stored)
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="report.image_uploaded",
            entity_type="technical_report",
            entity_id=str(report_id),
            details={"category": category, "sha256": digest},
        )
    )
    db.commit()
    db.refresh(stored)
    return stored


@router.get("/records/{report_id}/images/{image_id}")
def download_report_image(
    report_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    image = db.get(ReportImage, image_id)
    if not image or image.report_id != report_id or not Path(image.file_path).is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(
        image.file_path, media_type=image.content_type, filename=image.original_name
    )


@router.delete(
    "/records/{report_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_report_image(
    report_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    image = db.get(ReportImage, image_id)
    if not image or image.report_id != report_id:
        raise HTTPException(status_code=404, detail="Image not found")
    Path(image.file_path).unlink(missing_ok=True)
    db.delete(image)
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="report.image_deleted",
            entity_type="technical_report",
            entity_id=str(report_id),
            details={"category": image.category},
        )
    )
    db.commit()


@router.post("/analyse-image", response_model=ImageAnalysisResponse)
async def analyse_image(
    image: UploadFile = File(...),
    _: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415, detail="Only JPEG, PNG and WebP images are supported"
        )
    content = await image.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="The image exceeds the 8 MB limit")
    try:
        result = AnalyseTyreImage(TesseractTyreExtractor()).execute(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImageAnalysisResponse(
        values=[
            ExtractedValueResponse(
                field=value.field, value=value.value, confidence=value.confidence
            )
            for value in result.values
        ],
        raw_text=result.raw_text,
        quality_score=result.quality_score,
    )


@router.post("/generate-pdf")
def generate_pdf(
    request: TechnicalReportPdfRequest,
    _: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    pdf = GenerateTechnicalReport(ReportLabTechnicalReportGenerator()).execute(
        request.report
    )
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{request.filename}"'},
    )


def _required_record(report_id: UUID, db: Session) -> TechnicalReportRecord:
    record = db.get(TechnicalReportRecord, report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return record


def _required_report(report_id: UUID, db: Session) -> ReportResponse:
    return _report_response(_required_record(report_id, db), db)


def _report_response(record: TechnicalReportRecord, db: Session) -> ReportResponse:
    images = db.scalars(
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
