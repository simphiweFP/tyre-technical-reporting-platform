from io import BytesIO

from PIL import Image

from backend.app.modules.document_generation.infrastructure import (
    ReportLabTechnicalReportGenerator,
)

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
