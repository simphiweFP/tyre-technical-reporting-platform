import base64
import re
import hashlib
from datetime import date
from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from backend.app.modules.media.application import (
    ALLOWED_IMAGE_TYPES,
    MAX_IMAGE_BYTES,
    AnalyseInspectionImage,
    GeminiAnalysisFailed,
    InspectionImageTooLarge,
    InvalidInspectionImage,
)
from backend.app.modules.reports.application import TechnicalReportService
from backend.app.modules.reports.customer_lookup import (
    customer_suggestions,
    refresh_customer_cache,
)
from backend.app.modules.reports.infrastructure import (
    ReportImage,
    TechnicalReportRecord,
)
from backend.app.modules.reports.schemas import (
    AnalyticsResponse,
    ImageResponse,
    ReportListResponse,
    ReportReferenceDataResponse,
    ReportResponse,
    ReportUpsertRequest,
    ReportValidationRequest,
    ReportValidationResponse,
)
from backend.app.modules.reports.validation import validate_report

router = APIRouter(prefix="/reports", tags=["Technical reports"])


@router.post("/validate", response_model=ReportValidationResponse)
def validate_technical_report(
    request: ReportValidationRequest,
    _: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    errors = validate_report(request.report, request.step)
    return ReportValidationResponse(valid=not errors, errors=errors)


@router.get("/reference-data", response_model=ReportReferenceDataResponse)
def report_reference_data(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    return TechnicalReportService(db).reference_data(user)


@router.get("/customers", response_model=list[str])
async def search_customers(
    search: str = Query(min_length=1, max_length=120),
    _: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    return await customer_suggestions(search)


@router.post("/customers/refresh")
async def refresh_customers(
    _: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)
    ),
):
    try:
        return await refresh_customer_cache()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Customer refresh failed: {exc}",
        ) from exc


@router.post("/analyse-image")
async def analyse_image_with_ai(
    image: UploadFile = File(...),
    _: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    content = await image.read(MAX_IMAGE_BYTES + 1)
    try:
        return await AnalyseInspectionImage().execute(content, image.content_type)
    except InspectionImageTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except InvalidInspectionImage as exc:
        status_code = 415 if "JPEG" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except GeminiAnalysisFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/analytics/summary", response_model=AnalyticsResponse)
def analytics_summary(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    return TechnicalReportService(db).analytics(user)


@router.get("/records", response_model=ReportListResponse)
def list_reports(
    query: str = "",
    report_status: str = "",
    branch: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    include_archived: bool = False,
    archived_only: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=250),
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    return TechnicalReportService(db).list_reports(
        user,
        query=query,
        report_status=report_status,
        branch=branch,
        date_from=date_from,
        date_to=date_to,
        include_archived=include_archived,
        archived_only=archived_only,
        offset=offset,
        limit=limit,
    )


@router.get("/records/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    record = _required_record(report_id, db)
    TechnicalReportService.ensure_access(record, user)
    return TechnicalReportService(db).response(record)


@router.put("/records/{report_id}", response_model=ReportResponse)
def upsert_report(
    report_id: UUID,
    request: ReportUpsertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    return TechnicalReportService(db).upsert(report_id, request, user)


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
    record = _required_record(report_id, db)
    TechnicalReportService.ensure_access(record, user)
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
        db.delete(previous)
        db.flush()

    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[
        image.content_type
    ]
    stored = ReportImage(
        report_id=report_id,
        category=category,
        original_name=image.filename or f"{category}{suffix}",
        content_type=image.content_type,
        base64_data=base64.b64encode(content).decode("ascii"),
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
    user: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    record = _required_record(report_id, db)
    TechnicalReportService.ensure_access(record, user)
    image = db.get(ReportImage, image_id)
    if not image or image.report_id != report_id:
        raise HTTPException(status_code=404, detail="Image not found")
    try:
        content = base64.b64decode(image.base64_data, validate=True)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=500, detail="Stored image data is invalid"
        ) from exc

    safe_filename = (
        image.original_name.replace("\r", "").replace("\n", "").replace('"', "'")
    )
    return StreamingResponse(
        BytesIO(content),
        media_type=image.content_type,
        headers={"Content-Disposition": f'inline; filename="{safe_filename}"'},
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
    record = _required_record(report_id, db)
    TechnicalReportService.ensure_access(record, user)
    image = db.get(ReportImage, image_id)
    if not image or image.report_id != report_id:
        raise HTTPException(status_code=404, detail="Image not found")
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
    claim = re.sub(
        r"[^A-Za-z0-9_-]", "", str(request.report.get("claimReference") or "report")
    )
    filename = f"Technical_Report_{claim}.pdf"
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _required_record(report_id: UUID, db: Session) -> TechnicalReportRecord:
    record = db.get(TechnicalReportRecord, report_id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return record


def _required_report(report_id: UUID, db: Session) -> ReportResponse:
    return TechnicalReportService(db).response(_required_record(report_id, db))
