import base64
import csv
import hashlib
from datetime import UTC, date, datetime
from io import BytesIO, StringIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.claims.application import (
    audit,
    case_view,
    check_case,
    filter_views,
    initial_data,
    metrics,
    required_owner,
    visible_cases,
)
from backend.app.modules.claims.documents import (
    EXTRA_COLUMNS,
    INSTRUCTION_COLUMNS,
    SCORECARD_COLUMNS,
    TRACKER_COLUMNS,
    document_filename,
    flat_claim,
    generate_document,
)
from backend.app.modules.claims.infrastructure import ClaimCase, CreditInstruction
from backend.app.modules.claims.schemas import (
    ClaimUpdate,
    DocumentSendRequest,
    HandoverRequest,
    InstructionRequest,
    ReassignRequest,
)
from backend.app.modules.claims.supplier_lookup import search_suppliers
from backend.app.modules.delivery.infrastructure import DeliveryAttempt
from backend.app.modules.delivery.presentation import _service
from backend.app.modules.delivery.schemas import DeliveryResponse
from backend.app.modules.document_generation.infrastructure import (
    ReportLabTechnicalReportGenerator,
)
from backend.app.modules.identity.dependencies import require_roles
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.reports.infrastructure import (
    ReportImage,
    TechnicalReportRecord,
)

router = APIRouter(prefix="/claims", tags=["Claims management"])
read_access = require_roles(
    Role.ADMINISTRATOR, Role.CLAIMS_ADMINISTRATOR, Role.REPORT_CAPTURER
)
write_access = require_roles(Role.ADMINISTRATOR, Role.CLAIMS_ADMINISTRATOR)


@router.get("/suppliers")
def suppliers(search: str = "", user: User = Depends(read_access)):
    return {"items": search_suppliers(search)}


@router.get("/owners")
def owners(db: Session = Depends(get_db), user: User = Depends(read_access)):
    return [
        {"id": str(u.id), "full_name": u.full_name, "email": u.email}
        for u in db.scalars(
            select(User).where(
                User.role == Role.CLAIMS_ADMINISTRATOR,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        ).all()
    ]


@router.get("/available-reports")
def available_reports(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    query = select(TechnicalReportRecord).where(
        TechnicalReportRecord.status != "Draft",
        TechnicalReportRecord.archived.is_(False),
        ~TechnicalReportRecord.id.in_(select(ClaimCase.report_id)),
    )
    if user.role == Role.REPORT_CAPTURER:
        query = query.where(TechnicalReportRecord.created_by == user.id)
    return [
        {
            "id": str(r.id),
            "claim_reference": r.claim_reference,
            "customer_name": r.customer_name,
            "branch": r.branch_name,
        }
        for r in db.scalars(
            query.order_by(TechnicalReportRecord.created_at.desc())
        ).all()
    ]


@router.post("/handover", status_code=201)
def handover(
    request: HandoverRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR, Role.REPORT_CAPTURER)),
):
    report = db.scalar(
        select(TechnicalReportRecord)
        .where(TechnicalReportRecord.id == request.report_id)
        .with_for_update()
    )
    if (
        not report
        or report.archived
        or (user.role == Role.REPORT_CAPTURER and report.created_by != user.id)
    ):
        raise HTTPException(status_code=404, detail="Report not found")
    if report.status == "Draft":
        raise HTTPException(
            status_code=422, detail="Submit the technical report before handover"
        )
    if db.scalar(select(ClaimCase).where(ClaimCase.report_id == report.id)):
        raise HTTPException(
            status_code=409, detail="This report has already been handed over"
        )
    required_owner(db, request.assigned_to)
    case = ClaimCase(
        report_id=report.id,
        assigned_to=request.assigned_to,
        handed_over_by=user.id,
        handover_notes=request.notes,
        data=initial_data(report),
    )
    db.add(case)
    db.flush()
    audit(
        db,
        user,
        case,
        "claim.handed_over",
        {
            "claim_reference": report.claim_reference,
            "assigned_to": str(case.assigned_to),
            "notes": request.notes,
        },
    )
    db.commit()
    return case_view(db, case)


def _views(db, user, search="", supplier="", branch="", date_from=None, date_to=None):
    if date_from and date_to and date_to < date_from:
        raise HTTPException(status_code=422, detail="End date must follow start date")
    return filter_views(
        [case_view(db, c) for c in visible_cases(db, user)],
        search,
        supplier,
        branch,
        date_from,
        date_to,
    )


@router.get("")
def list_claims(
    search: str = "",
    supplier: str = "",
    branch: str = "",
    decision: str = "",
    workflow_status: str = "",
    credit_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=250),
    db: Session = Depends(get_db),
    user: User = Depends(read_access),
):
    items = _views(db, user, search, supplier, branch, date_from, date_to)
    items = [
        i
        for i in items
        if (not credit_only or i["data"]["supplier_status"] in {"Accepted", "Rejected"})
        and (not decision or i["data"]["supplier_status"] == decision)
        and (not workflow_status or i["workflow_status"] == workflow_status)
    ]
    return {"items": items[offset : offset + limit], "total": len(items)}


@router.get("/metrics")
def claim_metrics(
    supplier: str = "",
    branch: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(read_access),
):
    return metrics(
        _views(
            db,
            user,
            supplier=supplier,
            branch=branch,
            date_from=date_from,
            date_to=date_to,
        )
    )


def _csv_response(rows, columns, filename):
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([label for label, _ in columns])
    for row in rows:
        # Prevent spreadsheet formula execution in manually entered values.
        values = []
        for _, key in columns:
            value = row.get(key)
            if isinstance(value, str) and value.lstrip().startswith(
                ("=", "+", "-", "@")
            ):
                value = "'" + value
            values.append("" if value is None else value)
        writer.writerow(values)
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/{section}")
def export(
    section: str,
    supplier: str = "",
    branch: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(read_access),
):
    items = _views(
        db, user, supplier=supplier, branch=branch, date_from=date_from, date_to=date_to
    )
    if section == "tracker":
        return _csv_response(
            [flat_claim(i) for i in items],
            [*TRACKER_COLUMNS, *EXTRA_COLUMNS],
            "Claim_Tracker.csv",
        )
    if section == "credit":
        rows = []
        for i in items:
            if i["data"]["supplier_status"] in {"Accepted", "Rejected"}:
                row = flat_claim(i)
                row["supplier"] = row.get("instruction_supplier") or row["supplier"]
                row["action"] = (
                    "Send Rejection report"
                    if row["supplier_status"] == "Rejected"
                    else ""
                )
                rows.append(row)
        return _csv_response(
            rows,
            [
                *INSTRUCTION_COLUMNS,
                ("Rejection report action", "action"),
                *EXTRA_COLUMNS,
            ],
            "Instruction_to_Credit.csv",
        )
    values = metrics(items)
    if section == "scorecard":
        return _csv_response(
            values["scorecard"], SCORECARD_COLUMNS, "Supplier_Scorecard.csv"
        )
    if section == "metrics":
        rows = [
            {"metric": key, "value": value}
            for key, value in values.items()
            if key != "scorecard"
        ]
        return _csv_response(
            rows, [("Metric", "metric"), ("Value", "value")], "Other_Metrics.csv"
        )
    raise HTTPException(status_code=404, detail="Unknown workbook section")


@router.get("/scorecard/pdf")
def scorecard_pdf(
    supplier: str = "",
    branch: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(read_access),
):
    data = metrics(
        _views(
            db,
            user,
            supplier=supplier,
            branch=branch,
            date_from=date_from,
            date_to=date_to,
        )
    )
    data["period_label"] = (
        f"Claim dates: {date_from or 'all'} to {date_to or 'today'} "
        f"· Branch: {branch or 'all'} · Supplier: {supplier or 'all'}"
    )
    pdf = generate_document("scorecard", data)
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="Supplier_Scorecard.pdf"'
        },
    )


@router.post("/scorecard/send", response_model=DeliveryResponse)
def send_scorecard(
    request: DocumentSendRequest,
    supplier: str = "",
    branch: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(write_access),
):
    data = metrics(
        _views(
            db,
            user,
            supplier=supplier,
            branch=branch,
            date_from=date_from,
            date_to=date_to,
        )
    )
    data["period_label"] = (
        f"Claim dates: {date_from or 'all'} to {date_to or 'today'} "
        f"· Branch: {branch or 'all'} · Supplier: {supplier or 'all'}"
    )
    claim = f"Scorecard_{date.today().isoformat()}"
    return _send(
        db,
        user,
        claim,
        "scorecard",
        generate_document("scorecard", data),
        document_filename("scorecard", date.today().isoformat()),
        request,
    )


@router.post("/import")
async def import_claims(
    assigned_to: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    from backend.app.modules.claims.workbook_import import import_workbook

    owner = required_owner(db, assigned_to)
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail="Upload a workbook smaller than 10 MB"
        )
    return import_workbook(db, content, owner, user)


@router.get("/{case_id}")
def get_claim(
    case_id: UUID, db: Session = Depends(get_db), user: User = Depends(read_access)
):
    return case_view(db, check_case(db, case_id, user))


@router.put("/{case_id}")
def update_claim(
    case_id: UUID,
    request: ClaimUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(write_access),
):
    case = check_case(db, case_id, user, lock=True)
    expected = (
        request.expected_updated_at.replace(tzinfo=UTC)
        if request.expected_updated_at.tzinfo is None
        else request.expected_updated_at
    )
    current = (
        case.updated_at.replace(tzinfo=UTC)
        if case.updated_at.tzinfo is None
        else case.updated_at
    )
    if current != expected:
        raise HTTPException(
            status_code=409, detail="This claim changed. Reload before saving."
        )
    if not request.data.supplier.strip():
        raise HTTPException(status_code=422, detail="Enter or select a supplier")
    before = {"data": case.data, "workflow_status": case.workflow_status}
    case.data = request.data.model_dump(mode="json")
    case.workflow_status = request.workflow_status
    view = case_view(db, case)
    if request.workflow_status == "Closed":
        if (
            case.data["supplier_status"] == "Under review"
            or view["credit_outstanding"]
            or view["supplier_offset_outstanding"]
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Resolve supplier feedback, customer credit and "
                    "supplier offsets before closing"
                ),
            )
        if case.data["supplier_status"] == "Accepted" and (
            case.data["accepted_percentage"] is None
            or case.data["customer_credit_percentage"] is None
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Record acceptance and customer credit percentages before closing"
                ),
            )
    case.updated_at = datetime.now(UTC)
    audit(
        db,
        user,
        case,
        "claim.updated",
        {
            "before": before,
            "after": {"data": case.data, "workflow_status": case.workflow_status},
        },
    )
    db.commit()
    return case_view(db, case)


@router.post("/{case_id}/reassign")
def reassign(
    case_id: UUID,
    request: ReassignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMINISTRATOR)),
):
    case = check_case(db, case_id, user)
    required_owner(db, request.assigned_to)
    old = str(case.assigned_to)
    case.assigned_to = request.assigned_to
    case.updated_at = datetime.now(UTC)
    for instruction in db.scalars(
        select(CreditInstruction).where(
            CreditInstruction.case_id == case.id,
            CreditInstruction.acknowledged_at.is_(None),
        )
    ).all():
        instruction.assigned_to = request.assigned_to
    audit(
        db,
        user,
        case,
        "claim.reassigned",
        {"from": old, "to": str(case.assigned_to), "notes": request.notes},
    )
    db.commit()
    return case_view(db, case)


@router.post("/{case_id}/instructions", status_code=201)
def issue_instruction(
    case_id: UUID,
    request: InstructionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(write_access),
):
    case = check_case(db, case_id, user)
    view = case_view(db, case)
    if (
        case.data["supplier_status"] != "Accepted"
        or case.data.get("customer_credit_percentage") is None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Record an accepted decision and manual customer "
                "credit percentage first"
            ),
        )
    snapshot = flat_claim(view)
    snapshot.pop("instructions", None)
    snapshot["supplier"] = (
        request.supplier.strip()
        or case.data.get("instruction_supplier")
        or case.data["supplier"]
    )
    snapshot["instruction_notes"] = request.notes
    instruction = CreditInstruction(
        case_id=case.id, assigned_to=case.assigned_to, created_by=user.id, data=snapshot
    )
    db.add(instruction)
    db.flush()
    audit(
        db,
        user,
        case,
        "claim.credit_instruction_issued",
        {
            "instruction_id": str(instruction.id),
            "assigned_to": str(case.assigned_to),
            "customer_credit_percentage": snapshot["customer_credit_percentage"],
        },
    )
    db.commit()
    return case_view(db, case)


@router.post("/{case_id}/instructions/{instruction_id}/receive")
def receive_instruction(
    case_id: UUID,
    instruction_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(write_access),
):
    case = check_case(db, case_id, user)
    instruction = db.get(CreditInstruction, instruction_id)
    if not instruction or instruction.case_id != case.id:
        raise HTTPException(status_code=404, detail="Instruction not found")
    if user.role != Role.ADMINISTRATOR and instruction.assigned_to != user.id:
        raise HTTPException(
            status_code=403, detail="This instruction is assigned to another user"
        )
    if not instruction.acknowledged_at:
        instruction.acknowledged_at = datetime.now(UTC)
        audit(
            db,
            user,
            case,
            "claim.credit_instruction_received",
            {"instruction_id": str(instruction.id)},
        )
        db.commit()
    return case_view(db, case)


def _document(db, case, kind, instruction_id=None):
    view = case_view(db, case)
    claim = view["claim_reference"]
    data = flat_claim(view)
    if kind == "technical":
        report = db.get(TechnicalReportRecord, case.report_id)
        data = {
            **report.report_data,
            "claimReference": claim,
            "photos": [
                {
                    "category": i.category,
                    "label": i.category,
                    "previewUrl": f"data:{i.content_type};base64,{i.base64_data}",
                    "comment": report.report_data.get("photoComments", {}).get(
                        i.category, ""
                    ),
                }
                for i in db.scalars(
                    select(ReportImage).where(ReportImage.report_id == report.id)
                ).all()
            ],
        }
        return ReportLabTechnicalReportGenerator().generate(data), document_filename(
            kind, claim
        )
    if kind not in {"tracker", "credit", "rejection"}:
        raise HTTPException(status_code=404, detail="Unknown document type")
    if kind == "rejection" and case.data["supplier_status"] != "Rejected":
        raise HTTPException(
            status_code=422,
            detail="A rejection report requires a rejected supplier decision",
        )
    if kind == "credit":
        instruction = (
            db.get(CreditInstruction, instruction_id)
            if instruction_id
            else db.scalar(
                select(CreditInstruction)
                .where(CreditInstruction.case_id == case.id)
                .order_by(CreditInstruction.created_at.desc())
            )
        )
        if not instruction or instruction.case_id != case.id:
            raise HTTPException(
                status_code=422, detail="Issue a credit instruction first"
            )
        data = instruction.data
    return generate_document(kind, data), document_filename(kind, claim)


@router.get("/{case_id}/documents/{kind}")
def download_document(
    case_id: UUID,
    kind: str,
    instruction_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(read_access),
):
    case = check_case(db, case_id, user)
    pdf, filename = _document(db, case, kind, instruction_id)
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _send(db, user, claim, kind, pdf, filename, request, case=None):
    attempt = DeliveryAttempt(
        claim_reference=claim,
        recipient_id=None,
        recipient_email=str(request.recipient_email),
        cc=[str(e) for e in request.cc],
        requested_by=user.id,
        status="Pending",
        report_payload={"claimReference": claim, "documentType": kind},
        document_type=kind,
        email_subject=f"Royal Tyres {kind.replace('_', ' ')} {claim}",
        email_body=request.body.strip()
        or f"Please find the Royal Tyres {kind.replace('_', ' ')} attached.",
        attachment_name=filename,
        sent_pdf_base64=base64.b64encode(pdf).decode("ascii"),
        sent_pdf_sha256=hashlib.sha256(pdf).hexdigest(),
    )
    db.add(attempt)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=user.id,
            action="claim.document_queued",
            entity_type="delivery_attempt",
            entity_id=str(attempt.id),
            details={
                "document_type": kind,
                "claim_reference": claim,
                "recipient": str(request.recipient_email),
                "case_id": str(case.id) if case else None,
            },
        )
    )
    db.commit()
    try:
        return _service(db).deliver(attempt, user.id)
    except Exception as exc:
        delivery_id = attempt.id
        db.rollback()
        attempt = db.get(DeliveryAttempt, delivery_id)
        attempt.status = "Failed"
        attempt.error_message = str(exc)[:1000] or "Document delivery failed"
        attempt.attempt_count = max(attempt.attempt_count, 1)
        db.commit()
        return attempt


@router.post("/{case_id}/documents/{kind}/send", response_model=DeliveryResponse)
def send_document(
    case_id: UUID,
    kind: str,
    request: DocumentSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(write_access),
):
    case = check_case(db, case_id, user)
    pdf, filename = _document(db, case, kind, request.instruction_id)
    return _send(
        db,
        user,
        case_view(db, case)["claim_reference"],
        kind,
        pdf,
        filename,
        request,
        case,
    )


@router.get("/{case_id}/activity")
def activity(
    case_id: UUID, db: Session = Depends(get_db), user: User = Depends(read_access)
):
    case = check_case(db, case_id, user)
    return [
        {
            "id": str(e.id),
            "action": e.action,
            "occurred_at": e.occurred_at.isoformat(),
            "actor": db.get(User, e.actor_id).full_name if e.actor_id else "System",
            "details": e.details,
        }
        for e in db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.entity_type == "claim_case",
                AuditEvent.entity_id == str(case.id),
            )
            .order_by(AuditEvent.occurred_at.desc())
        ).all()
    ]
