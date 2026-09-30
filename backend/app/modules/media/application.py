from io import BytesIO

import httpx
from PIL import Image as PillowImage
from PIL import UnidentifiedImageError

from backend.app.modules.media.infrastructure import GeminiTyreExtractor

MAX_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class InvalidInspectionImage(ValueError):
    pass


class InspectionImageTooLarge(ValueError):
    pass


class GeminiAnalysisFailed(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AnalyseInspectionImage:
    def __init__(self, extractor: GeminiTyreExtractor | None = None):
        self.extractor = extractor or GeminiTyreExtractor()

    async def execute(
        self,
        content: bytes,
        content_type: str | None,
    ) -> dict[str, str]:
        mime_type = content_type or "image/jpeg"
        if mime_type not in ALLOWED_IMAGE_TYPES:
            raise InvalidInspectionImage("Only JPEG, PNG and WebP images are supported")
        if len(content) > MAX_IMAGE_BYTES:
            raise InspectionImageTooLarge("The image exceeds the 8 MB limit")

        try:
            PillowImage.open(BytesIO(content)).verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise InvalidInspectionImage("The uploaded file is not a valid image") from exc

        try:
            return await self.extractor.analyse(content, mime_type)
        except httpx.HTTPStatusError as exc:
            raise GeminiAnalysisFailed(
                f"Gemini OCR request failed with HTTP {exc.response.status_code}",
                exc.response.status_code,
            ) from exc
        except RuntimeError as exc:
            raise GeminiAnalysisFailed(str(exc)) from exc
