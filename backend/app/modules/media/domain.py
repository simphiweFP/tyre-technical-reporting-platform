from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractedValue:
    field: str
    value: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ImageAnalysis:
    values: tuple[ExtractedValue, ...]
    raw_text: str
    quality_score: float
