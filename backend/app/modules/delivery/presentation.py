from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.delivery.application import ReportDeliveryService
from backend.app.modules.delivery.infrastructure import DeliveryAttempt, Recipient, SmtpEmailGateway
from backend.app.modules.delivery.schemas import DeliveryRequest, DeliveryResponse, RecipientCreate, RecipientResponse
from backend.app.modules.document_generation.application import GenerateTechnicalReport
from backend.app.modules.document_generation.infrastructure import ReportLabTechnicalReportGenerator
from backend.app.modules.identity.dependencies import require_roles
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User

router = APIRouter(tags=["Report delivery"])


@router.get("/recipients", response_model=list[RecipientResponse])
def recipients(
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    query = select(Recipient).order_by(Recipient.company)
    if active_only:
        query = query.where(Recipient.is_active.is_(True))
    return db.scalars(query).all()


@router.post("/recipients", response_model=RecipientResponse, status_code=status.HTTP_201_CREATED)
def create_recipient(
    request: RecipientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    if db.scalar(select(Recipient).where(Recipient.email == str(request.email))):
        raise HTTPException(status_code=409, detail="A recipient with this email already exists")
    recipient = Recipient(
        company=request.company.strip(),
        contact_name=request.contact_name.strip(),
        email=str(request.email).lower(),
        default_cc=str(request.default_cc or "").lower(),
    )
    db.add(recipient)
    db.flush()
    db.add(AuditEvent(actor_id=user.id, action="recipient.created", entity_type="recipient", entity_id=str(recipient.id), details={"email": recipient.email}))
    db.commit()
    db.refresh(recipient)
    return recipient


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
    db.add(AuditEvent(actor_id=user.id, action="recipient.status_changed", entity_type="recipient", entity_id=str(recipient.id), details={"is_active": is_active}))
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
    recipient = db.get(Recipient, request.recipient_id)
    if not recipient or not recipient.is_active:
        raise HTTPException(status_code=422, detail="The selected recipient is not active")
    cc = [str(address).lower() for address in request.cc]
    if recipient.default_cc and recipient.default_cc not in cc:
        cc.append(recipient.default_cc)
    attempt = DeliveryAttempt(
        claim_reference=claim,
        recipient_id=recipient.id,
        recipient_email=recipient.email,
        cc=cc,
        report_payload=request.report,
        status="Pending",
        requested_by=user.id,
    )
    db.add(attempt)
    db.flush()
    return _service(db).deliver(attempt, user.id)


@router.post("/reports/deliveries/{delivery_id}/retry", response_model=DeliveryResponse)
def retry_delivery(
    delivery_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    attempt = db.get(DeliveryAttempt, delivery_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Delivery not found")
    if attempt.status != "Failed":
        raise HTTPException(status_code=409, detail="Only failed deliveries can be retried")
    attempt.attempt_count += 1
    return _service(db).deliver(attempt, user.id)


@router.get("/reports/{claim_reference}/deliveries", response_model=list[DeliveryResponse])
def delivery_history(
    claim_reference: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER, Role.VIEWER)),
):
    query = select(DeliveryAttempt).where(DeliveryAttempt.claim_reference == claim_reference).order_by(DeliveryAttempt.created_at.desc())
    return db.scalars(query).all()


def _service(db: Session) -> ReportDeliveryService:
    return ReportDeliveryService(
        db,
        SmtpEmailGateway(get_settings()),
        GenerateTechnicalReport(ReportLabTechnicalReportGenerator()),
    )
