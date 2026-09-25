from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.delivery.application import ReportDeliveryService
from backend.app.modules.delivery.domain import EmailMessage
from backend.app.modules.delivery.infrastructure import (
    DeliveryAttempt,
    Recipient,
    SmtpEmailGateway,
)
from backend.app.modules.delivery.schemas import (
    DeliveryListResponse,
    DeliveryRequest,
    DeliveryResponse,
    RecipientCreate,
    RecipientResponse,
    RecipientUpdate,
)
from backend.app.modules.document_generation.application import GenerateTechnicalReport
from backend.app.modules.document_generation.infrastructure import (
    ReportLabTechnicalReportGenerator,
)
from backend.app.modules.identity.dependencies import require_roles
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.reports.infrastructure import TechnicalReportRecord

router = APIRouter(tags=["Report delivery"])


def _store_cc(addresses) -> str:
    return ",".join(dict.fromkeys(str(address).lower() for address in addresses))


def _read_cc(addresses: str) -> list[str]:
    return [address.strip() for address in addresses.split(",") if address.strip()]


@router.get("/recipients", response_model=list[RecipientResponse])
def recipients(
    active_only: bool = Query(default=True),
    branch: str = "",
    category: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    query = select(Recipient).order_by(Recipient.company)
    if active_only:
        query = query.where(Recipient.is_active.is_(True))
    if branch:
        query = query.where(Recipient.branch_code.in_(("All Branches", branch)))
    if category:
        query = query.where(Recipient.category.in_(("All Categories", category)))
    return db.scalars(query).all()


@router.post(
    "/recipients", response_model=RecipientResponse, status_code=status.HTTP_201_CREATED
)
def create_recipient(
    request: RecipientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    if db.scalar(select(Recipient).where(Recipient.email == str(request.email))):
        raise HTTPException(
            status_code=409, detail="A recipient with this email already exists"
        )
    recipient = Recipient(
        company=request.company.strip(),
        contact_name=request.contact_name.strip(),
        email=str(request.email).lower(),
        default_cc=_store_cc(request.default_cc),
        branch_code=request.branch_code.strip(),
        category=request.category.strip(),
        escalation_enabled=request.escalation_enabled,
    )
    db.add(recipient)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="recipient.created",
            entity_type="recipient",
            entity_id=str(recipient.id),
            details={"email": recipient.email},
        )
    )
    db.commit()
    db.refresh(recipient)
    return recipient


@router.put("/recipients/{recipient_id}", response_model=RecipientResponse)
def update_recipient(
    recipient_id: UUID,
    request: RecipientUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    recipient = db.get(Recipient, recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    duplicate = db.scalar(
        select(Recipient).where(
            Recipient.email == str(request.email).lower(),
            Recipient.id != recipient.id,
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409, detail="A recipient with this email already exists"
        )
    for field, value in request.model_dump().items():
        if field == "email":
            value = str(value or "").lower()
        elif field == "default_cc":
            value = _store_cc(value)
        setattr(recipient, field, value)
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="recipient.updated",
            entity_type="recipient",
            entity_id=str(recipient.id),
            details={},
        )
    )
    db.commit()
    db.refresh(recipient)
    return recipient


@router.post("/recipients/{recipient_id}/test")
def test_recipient(
    recipient_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    recipient = db.get(Recipient, recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    SmtpEmailGateway(get_settings()).send(
        EmailMessage(
            subject="Royal Tyres delivery test",
            body=(
                "This confirms that technical-report email delivery is "
                "configured correctly."
            ),
            to=(recipient.email,),
            cc=(),
        )
    )
    return {"message": f"Test email sent to {recipient.email}"}


@router.patch("/recipients/{recipient_id}/status", response_model=RecipientResponse)
def set_recipient_status(
    recipient_id: UUID,
    is_active: bool,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    recipient = db.get(Recipient, recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    recipient.is_active = is_active
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="recipient.status_changed",
            entity_type="recipient",
            entity_id=str(recipient.id),
            details={"is_active": is_active},
        )
    )
    db.commit()
    db.refresh(recipient)
    return recipient


@router.post("/reports/deliver", response_model=DeliveryResponse)
def deliver_report(
    request: DeliveryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    claim = str(request.report.get("claimReference") or "").strip()
    if not claim:
        raise HTTPException(status_code=422, detail="A claim reference is required")
    record = db.scalar(
        select(TechnicalReportRecord).where(
            TechnicalReportRecord.claim_reference == claim
        )
    )
    if not record:
        raise HTTPException(
            status_code=422, detail="Save the report before scheduling delivery"
        )
    if user.role == Role.REPORT_CAPTURER and record.created_by != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    if record.status == "Draft":
        raise HTTPException(
            status_code=422,
            detail="The report must pass API validation before delivery",
        )
    recipient = db.get(Recipient, request.recipient_id)
    if not recipient or not recipient.is_active:
        raise HTTPException(
            status_code=422, detail="The selected recipient is not active"
        )
    report_branch = str(record.report_data.get("branch") or "")
    report_category = str(record.report_data.get("category") or "")
    if recipient.branch_code not in {"All Branches", report_branch}:
        raise HTTPException(
            status_code=422, detail="Recipient is not configured for this branch"
        )
    if recipient.category not in {"All Categories", report_category}:
        raise HTTPException(
            status_code=422,
            detail="Recipient is not configured for this claim category",
        )
    cc = [str(address).lower() for address in request.cc]
    for address in _read_cc(recipient.default_cc):
        if address not in cc:
            cc.append(address)
    attempt = DeliveryAttempt(
        claim_reference=claim,
        recipient_id=recipient.id,
        recipient_email=recipient.email,
        cc=cc,
        report_payload={"claimReference": claim},
        status="Pending",
        requested_by=user.id,
    )
    db.add(attempt)
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="report.email_queued",
            entity_type="technical_report",
            entity_id=claim,
            details={"recipient": recipient.email},
        )
    )
    db.commit()
    db.refresh(attempt)
    return attempt


@router.post("/reports/deliveries/{delivery_id}/retry", response_model=DeliveryResponse)
def retry_delivery(
    delivery_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    attempt = db.get(DeliveryAttempt, delivery_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if user.role == Role.REPORT_CAPTURER:
        record = db.scalar(
            select(TechnicalReportRecord).where(
                TechnicalReportRecord.claim_reference == attempt.claim_reference,
                TechnicalReportRecord.created_by == user.id,
            )
        )
        if not record:
            raise HTTPException(status_code=404, detail="Delivery not found")
    if attempt.status not in {"Failed", "Retrying"}:
        raise HTTPException(
            status_code=409, detail="Only failed deliveries can be retried"
        )
    from datetime import UTC, datetime

    attempt.status = "Pending"
    attempt.next_attempt_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="report.email_requeued",
            entity_type="technical_report",
            entity_id=attempt.claim_reference,
            details={"delivery_id": str(attempt.id)},
        )
    )
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get(
    "/reports/{claim_reference}/deliveries", response_model=list[DeliveryResponse]
)
def delivery_history(
    claim_reference: str,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    if user.role == Role.REPORT_CAPTURER:
        record = db.scalar(
            select(TechnicalReportRecord).where(
                TechnicalReportRecord.claim_reference == claim_reference,
                TechnicalReportRecord.created_by == user.id,
            )
        )
        if not record:
            raise HTTPException(status_code=404, detail="Report not found")
    query = (
        select(DeliveryAttempt)
        .where(DeliveryAttempt.claim_reference == claim_reference)
        .order_by(DeliveryAttempt.created_at.desc())
    )
    return db.scalars(query).all()


@router.get("/deliveries", response_model=DeliveryListResponse)
def list_deliveries(
    query: str = "",
    delivery_status: str = "",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=250),
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)
    ),
):
    statement = select(DeliveryAttempt).order_by(DeliveryAttempt.created_at.desc())
    if user.role == Role.REPORT_CAPTURER:
        owned_claims = select(TechnicalReportRecord.claim_reference).where(
            TechnicalReportRecord.created_by == user.id
        )
        statement = statement.where(DeliveryAttempt.claim_reference.in_(owned_claims))
    if delivery_status:
        statement = statement.where(DeliveryAttempt.status == delivery_status)
    if query:
        term = f"%{query.strip()}%"
        statement = statement.where(
            DeliveryAttempt.claim_reference.ilike(term)
            | DeliveryAttempt.recipient_email.ilike(term)
        )
    items = db.scalars(statement).all()
    return DeliveryListResponse(items=items[offset : offset + limit], total=len(items))


def _service(db: Session) -> ReportDeliveryService:
    return ReportDeliveryService(
        db,
        SmtpEmailGateway(get_settings()),
        GenerateTechnicalReport(ReportLabTechnicalReportGenerator()),
    )
