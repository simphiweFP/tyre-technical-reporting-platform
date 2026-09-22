import os
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from backend.app.core.config import get_settings


class ReportFileStorage:
    """Stores report files on a persistent company-managed filesystem share."""

    def __init__(self, root: str | Path | None = None):
        configured_root = root or get_settings().report_file_root
        self.root = Path(configured_root).expanduser().resolve()

    def ensure_ready(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if not os.access(self.root, os.R_OK | os.W_OK):
            raise OSError(f"Report file storage is not accessible: {self.root}")

    def store_image(
        self,
        *,
        report_id: UUID,
        claim_reference: str,
        category: str,
        digest: str,
        suffix: str,
        content: bytes,
    ) -> str:
        self.ensure_ready()
        now = datetime.now(UTC)
        claim_folder = self._safe_segment(claim_reference, fallback="unassigned")
        category_name = self._safe_segment(category, fallback="image")
        relative = Path(
            str(now.year),
            f"{now.month:02d}",
            claim_folder,
            str(report_id),
            f"{category_name}-{digest[:16]}{suffix}",
        )
        destination = self.resolve(relative.as_posix())
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(f"{destination.suffix}.uploading")
        temporary.write_bytes(content)
        temporary.replace(destination)
        return relative.as_posix()

    def resolve(self, stored_path: str) -> Path:
        path = Path(stored_path)
        if path.is_absolute():
            # Supports records written before paths became relative, but only when
            # they still point inside the configured company share.
            candidate = path.resolve()
        else:
            candidate = (self.root / path).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Stored report path is outside REPORT_FILE_ROOT")
        return candidate

    def delete(self, stored_path: str) -> None:
        self.resolve(stored_path).unlink(missing_ok=True)

    @staticmethod
    def _safe_segment(value: str, *, fallback: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip(".-_")
        return (cleaned or fallback)[:80]
