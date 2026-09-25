from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.modules.administration.infrastructure import (
    OperationalHeartbeat,
    SystemSetting,
)
from backend.app.modules.administration.schemas import (
    DEFAULT_SETTINGS,
    OperationsStatusResponse,
    SystemSettingsResponse,
    SystemSettingsUpdate,
)
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.auditing.schemas import AuditEventResponse, AuditListResponse
from backend.app.modules.delivery.infrastructure import DeliveryAttempt
from backend.app.modules.identity.dependencies import require_roles
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.reports.infrastructure import TechnicalReportRecord
from backend.app.modules.reports.storage import ReportFileStorage

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/operations", response_model=OperationsStatusResponse)
def operations_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    db.execute(text("SELECT 1"))
    ReportFileStorage().ensure_ready()
    heartbeat = db.get(OperationalHeartbeat, "delivery-worker")
    worker_status = "not_started"
    if heartbeat:
        last_seen = heartbeat.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=UTC)
        worker_status = (
            "healthy"
            if last_seen >= datetime.now(UTC) - timedelta(seconds=30)
            else "stale"
        )
    counts = dict(
        db.execute(
            select(DeliveryAttempt.status, func.count(DeliveryAttempt.id)).group_by(
                DeliveryAttempt.status
            )
        ).all()
    )
    oldest = db.scalar(
        select(func.min(DeliveryAttempt.created_at)).where(
            DeliveryAttempt.status.in_(("Pending", "Retrying"))
        )
    )
    return OperationsStatusResponse(
        status="healthy" if worker_status == "healthy" else "degraded",
        database="healthy",
        file_storage="healthy",
        delivery_worker=worker_status,
        worker_last_seen_at=heartbeat.last_seen_at if heartbeat else None,
        pending_deliveries=counts.get("Pending", 0),
        retrying_deliveries=counts.get("Retrying", 0),
        failed_deliveries=counts.get("Failed", 0),
        oldest_pending_at=oldest,
    )


@router.get("/settings", response_model=SystemSettingsResponse)
def get_system_settings(
    db: Session = Depends(get_db), _: User = Depends(require_roles(Role.ADMINISTRATOR))
):
    values = dict(DEFAULT_SETTINGS)
    values.update(
        {item.key: item.value for item in db.scalars(select(SystemSetting)).all()}
    )
    return values


@router.put("/settings", response_model=SystemSettingsResponse)
def update_system_settings(
    request: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    for key, value in request.model_dump().items():
        setting = db.get(SystemSetting, key) or SystemSetting(key=key, value=value)
        setting.value = value
        db.add(setting)
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action="settings.updated",
            entity_type="system",
            details={"fields": sorted(request.model_dump())},
        )
    )
    db.commit()
    return request


@router.get("/audit-events", response_model=AuditListResponse)
def audit_events(
    query: str = "",
    days: int = Query(default=7, ge=1, le=3650),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=250),
    db: Session = Depends(get_db),
    current: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    statement = (
        select(AuditEvent, User)
        .outerjoin(User, User.id == AuditEvent.actor_id)
        .where(AuditEvent.occurred_at >= datetime.now(UTC) - timedelta(days=days))
        .order_by(AuditEvent.occurred_at.desc())
    )
    if current.role == Role.REPORT_CAPTURER:
        owned = db.scalars(
            select(TechnicalReportRecord).where(
                TechnicalReportRecord.created_by == current.id
            )
        ).all()
        owned_refs = [str(record.id) for record in owned] + [
            record.claim_reference for record in owned
        ]
        if not owned_refs:
            return AuditListResponse(items=[], total=0)
        statement = statement.where(
            AuditEvent.entity_type == "technical_report",
            AuditEvent.entity_id.in_(owned_refs),
        )
    rows = db.execute(statement).all()
    if query.strip():
        term = query.strip().casefold()
        rows = [
            (event, user)
            for event, user in rows
            if any(
                term in str(value or "").casefold()
                for value in (
                    event.action,
                    event.entity_id,
                    user.full_name if user else "",
                    user.email if user else "",
                    (event.details or {}).get("claim_reference"),
                    (event.details or {}).get("status"),
                )
            )
        ]
    items = [
        AuditEventResponse(
            id=event.id,
            actor=user.full_name if user else "System",
            action=event.action,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            details=event.details,
            occurred_at=event.occurred_at,
        )
        for event, user in rows[offset : offset + limit]
    ]
    return AuditListResponse(items=items, total=len(rows))
