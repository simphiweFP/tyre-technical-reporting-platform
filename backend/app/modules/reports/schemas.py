from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportUpsertRequest(BaseModel):
    report: dict[str, Any]


class ImageResponse(BaseModel):
    id: UUID
    category: str
    original_name: str
    content_type: str
    sha256: str
    byte_size: int
    captured_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportResponse(BaseModel):
    id: UUID
    report: dict[str, Any]
    archived: bool
    created_at: datetime
    updated_at: datetime


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int = Field(ge=0)


class AnalyticsResponse(BaseModel):
    total: int
    drafts: int
    completed: int
    email_failed: int
    by_status: dict[str, int]
    by_branch: dict[str, int]
    by_brand: dict[str, int]
    by_category: dict[str, int]
    by_month: dict[str, int]


class ReferenceOption(BaseModel):
    value: str
    label: str


class ReportReferenceDataResponse(BaseModel):
    branches: list[ReferenceOption]
    salespeople: list[str]
    customers: list[str]
    categories: list[str]
    brands: list[str]
    patterns: list[str]
    tyre_positions: list[str]
