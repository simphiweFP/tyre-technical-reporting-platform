from io import BytesIO

from PIL import Image

from backend.app.modules.document_generation.infrastructure import (
    ReportLabTechnicalReportGenerator,
)
from backend.app.modules.media.infrastructure import TesseractTyreExtractor


def test_tyre_text_parser_extracts_supported_fields():
    values = TesseractTyreExtractor._extract(
        "BRIDGESTONE 205/55 R16 DOT AB12 CD34 3425 SERIAL SN-778899", 0.88
    )
    extracted = {value.field: value.value for value in values}
    assert extracted["brand"] == "Bridgestone"
    assert extracted["tyreSize"] == "205/55 R16"
    assert extracted["rimSize"] == "R16"
    assert extracted["dot"].endswith("3425")


def test_pdf_generator_creates_pdf_with_image():
    image_buffer = BytesIO()
    Image.new("RGB", (300, 180), "#333333").save(image_buffer, "JPEG")
    import base64

    report = {
        "claimReference": "TR-2026-0001",
        "customerName": "Test Customer",
        "brand": "Bridgestone",
        "photos": [
            {
                "category": "dot",
                "label": "DOT",
                "previewUrl": "data:image/jpeg;base64,"
                + base64.b64encode(image_buffer.getvalue()).decode(),
            }
        ],
    }
    result = ReportLabTechnicalReportGenerator().generate(report)
    assert result.startswith(b"%PDF")
    assert len(result) > 1_000


def test_pdf_endpoint_requires_authentication(client):
    response = client.post(
        "/api/v1/reports/generate-pdf",
        json={"report": {"claimReference": "TR-2026-0001"}, "filename": "report.pdf"},
    )
    assert response.status_code == 401
