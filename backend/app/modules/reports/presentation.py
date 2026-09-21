from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.app.modules.document_generation.application import GenerateTechnicalReport
from backend.app.modules.document_generation.infrastructure import ReportLabTechnicalReportGenerator
from backend.app.modules.document_generation.schemas import TechnicalReportPdfRequest
from backend.app.modules.identity.dependencies import require_roles
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.media.application import AnalyseTyreImage
from backend.app.modules.media.infrastructure import TesseractTyreExtractor
from backend.app.modules.media.schemas import ExtractedValueResponse, ImageAnalysisResponse

router = APIRouter(prefix="/reports", tags=["Technical reports"])
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/analyse-image", response_model=ImageAnalysisResponse)
async def analyse_image(
    image: UploadFile = File(...),
    _: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG and WebP images are supported")
    content = await image.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="The image exceeds the 8 MB limit")
    try:
        result = AnalyseTyreImage(TesseractTyreExtractor()).execute(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ImageAnalysisResponse(
        values=[ExtractedValueResponse(field=value.field, value=value.value, confidence=value.confidence) for value in result.values],
        raw_text=result.raw_text,
        quality_score=result.quality_score,
    )


@router.post("/generate-pdf")
def generate_pdf(
    request: TechnicalReportPdfRequest,
    _: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)),
):
    pdf = GenerateTechnicalReport(ReportLabTechnicalReportGenerator()).execute(request.report)
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{request.filename}"'},
    )

