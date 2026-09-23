from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SystemSettingsResponse(BaseModel):
    company_name: str
    ocr_confidence_threshold: int
    pdf_template: str
    offline_sync_enabled: bool
    offline_sync_minutes: int
    smtp_server: str


class SystemSettingsUpdate(SystemSettingsResponse):
    company_name: str = Field(min_length=2, max_length=200)
    ocr_confidence_threshold: int = Field(ge=0, le=100)
    offline_sync_minutes: int = Field(ge=1, le=1440)


DEFAULT_SETTINGS: dict[str, Any] = {
    "company_name": "Royal Tyres (Pty) Ltd",
    "ocr_confidence_threshold": 85,
    "pdf_template": "Technical Report v1.0",
    "offline_sync_enabled": True,
    "offline_sync_minutes": 5,
    "smtp_server": "smtp.royaltyres.co.za",
}


class OperationsStatusResponse(BaseModel):
    status: str
    database: str
    file_storage: str
    delivery_worker: str
    worker_last_seen_at: datetime | None
    pending_deliveries: int
    retrying_deliveries: int
    failed_deliveries: int
    oldest_pending_at: datetime | None
