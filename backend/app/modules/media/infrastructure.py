import re

import cv2
import numpy as np
import pytesseract
from PIL import Image

from backend.app.modules.media.domain import ExtractedValue, ImageAnalysis

KNOWN_BRANDS = (
    "BRIDGESTONE",
    "CONTINENTAL",
    "DUNLOP",
    "FIRESTONE",
    "GOODYEAR",
    "HANKOOK",
    "MICHELIN",
    "PIRELLI",
    "SUMITOMO",
    "YOKOHAMA",
)


class TesseractTyreExtractor:
    def analyse(self, content: bytes) -> ImageAnalysis:
        encoded = np.frombuffer(content, dtype=np.uint8)
        source = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if source is None:
            raise ValueError("The uploaded file is not a readable image")

        grey = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)
        grey = cv2.bilateralFilter(grey, 7, 45, 45)
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(grey)
        threshold = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 8
        )
        data = pytesseract.image_to_data(
            Image.fromarray(threshold),
            output_type=pytesseract.Output.DICT,
            config="--psm 11",
        )
        words = [word.strip().upper() for word in data["text"] if word.strip()]
        confidences = [float(value) for value in data["conf"] if float(value) >= 0]
        raw_text = " ".join(words)
        quality = round(
            min(
                1.0, (sum(confidences) / len(confidences) / 100) if confidences else 0.0
            ),
            2,
        )
        values = self._extract(raw_text, quality)
        return ImageAnalysis(
            values=tuple(values), raw_text=raw_text[:500], quality_score=quality
        )

    @staticmethod
    def _extract(text: str, quality: float) -> list[ExtractedValue]:
        values: list[ExtractedValue] = []
        size = re.search(r"\b(\d{3})\s*[/ ]\s*(\d{2})\s*(?:R|ZR)\s*(\d{2})\b", text)
        if size:
            values.append(
                ExtractedValue(
                    "tyreSize",
                    f"{size.group(1)}/{size.group(2)} R{size.group(3)}",
                    quality,
                )
            )
            values.append(ExtractedValue("rimSize", f"R{size.group(3)}", quality))
        dot = re.search(r"\bDOT\s*[:\-]?\s*([A-Z0-9 ]{6,18}?\d{4})\b", text)
        if dot:
            values.append(
                ExtractedValue(
                    "dot", f"DOT {re.sub(r'\s+', ' ', dot.group(1)).strip()}", quality
                )
            )
        serial = re.search(r"\b(?:SERIAL|S/N|SN)\s*[:\-]?\s*([A-Z0-9\-]{5,24})\b", text)
        if serial:
            values.append(
                ExtractedValue("serialNumber", serial.group(1), quality * 0.9)
            )
        brand = next((brand for brand in KNOWN_BRANDS if brand in text), None)
        if brand:
            values.append(
                ExtractedValue("brand", brand.title(), min(0.98, quality + 0.08))
            )
        return values
