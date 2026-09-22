import pytest

from backend.app.modules.media.infrastructure import TesseractTyreExtractor


@pytest.mark.parametrize(
    ("ocr_text", "expected"),
    [
        (
            "MICHELIN 205 / 55 R 16 DOT AB12 CD34 3425",
            {"brand": "Michelin", "rimSize": "R16"},
        ),
        ("GOODYEAR 265/65 ZR17 DOT XY9 1026", {"brand": "Goodyear", "rimSize": "R17"}),
        (
            "DUNLOP SERIAL: SN-889922 195/60R15",
            {"brand": "Dunlop", "serialNumber": "SN-889922"},
        ),
        ("CONTINENTAL 225 45 R18", {"brand": "Continental", "rimSize": "R18"}),
    ],
)
def test_ocr_parser_handles_spacing_noise_and_supported_brands(ocr_text, expected):
    values = {
        item.field: item.value
        for item in TesseractTyreExtractor._extract(ocr_text, 0.72)
    }
    for field, value in expected.items():
        assert values[field] == value
