from uuid import uuid4

import pytest

from backend.app.modules.reports.storage import ReportFileStorage


def test_file_server_storage_returns_relative_business_path(tmp_path):
    storage = ReportFileStorage(tmp_path / "company-share")
    report_id = uuid4()

    stored_path = storage.store_image(
        report_id=report_id,
        claim_reference="CLAIM/1000258",
        category="serial number",
        digest="a" * 64,
        suffix=".jpg",
        content=b"image-content",
    )

    assert not stored_path.startswith(str(tmp_path))
    assert "CLAIM-1000258" in stored_path
    assert str(report_id) in stored_path
    assert storage.resolve(stored_path).read_bytes() == b"image-content"


def test_file_server_storage_rejects_paths_outside_share(tmp_path):
    storage = ReportFileStorage(tmp_path / "company-share")

    with pytest.raises(ValueError, match="outside REPORT_FILE_ROOT"):
        storage.resolve("../../private.txt")
