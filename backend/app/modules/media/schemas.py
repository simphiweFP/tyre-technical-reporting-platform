from pydantic import BaseModel, Field


class ExtractedValueResponse(BaseModel):
    field: str
    value: str
    confidence: float = Field(ge=0, le=1)


class ImageAnalysisResponse(BaseModel):
    values: list[ExtractedValueResponse]
    raw_text: str
    quality_score: float = Field(ge=0, le=1)

