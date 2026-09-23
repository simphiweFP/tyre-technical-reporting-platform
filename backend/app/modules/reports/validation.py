from typing import Any


REQUIRED_PHOTOS = {
    "dot": "DOT photo is required.",
    "serialNumber": "Serial number photo is required.",
    "entireTyreDot": "Entire tyre DOT-side photo is required.",
    "entireTyreOpposite": "Entire tyre opposite-side photo is required.",
    "issue1": "Issue photo is required.",
    "bead1": "Bead photo is required.",
    "internalCarcass1": "Internal carcass photo is required.",
    "treadDepth1": "Tread depth photo is required.",
    "treadPattern": "Tread pattern photo is required.",
    "vehicle": "Vehicle photo is required.",
}


def validate_report(report: dict[str, Any], step: int = 3) -> dict[str, str]:
    errors: dict[str, str] = {}
    if step in {0, 3}:
        for field, message in {
            "salesperson": "Salesperson is required.",
            "customerName": "Customer name is required.",
            "branch": "Branch selection is required.",
        }.items():
            if not str(report.get(field) or "").strip():
                errors[field] = message
    if step in {1, 3}:
        captured = {
            str(photo.get("category"))
            for photo in report.get("photos", [])
            if isinstance(photo, dict)
        }
        for category, message in REQUIRED_PHOTOS.items():
            if category not in captured:
                errors[f"photos.{category}"] = message
    if step in {2, 3}:
        for field, message in {
            "brand": "Brand is required.",
            "dot": "DOT is required.",
            "serialNumber": "Serial number is required.",
        }.items():
            if not str(report.get(field) or "").strip():
                errors[field] = message
    return errors
