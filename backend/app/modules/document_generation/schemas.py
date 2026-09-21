from typing import Any

from pydantic import BaseModel, Field


class TechnicalReportPdfRequest(BaseModel):
    report: dict[str, Any]
    filename: str = Field(default="technical-report.pdf", pattern=r"^[A-Za-z0-9_.-]+\.pdf$")

