from typing import Protocol

from backend.app.modules.media.domain import ImageAnalysis


class ImageTextExtractor(Protocol):
    def analyse(self, content: bytes) -> ImageAnalysis: ...


class AnalyseTyreImage:
    def __init__(self, extractor: ImageTextExtractor):
        self.extractor = extractor

    def execute(self, content: bytes) -> ImageAnalysis:
        if not content:
            raise ValueError("The image is empty")
        return self.extractor.analyse(content)
