"""Continue technical reports in the claims queue without duplicate handovers."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.modules.claims.application import audit, case_view, initial_data
from backend.app.modules.claims.documents import INSTRUCTION_COLUMNS, flat_claim
from backend.app.modules.claims.infrastructure import ClaimCase, CreditInstruction
from backend.app.modules.delivery.infrastructure import DeliveryAttempt
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.reports.infrastructure import TechnicalReportRecord


def sent_report_query():
    return select(DeliveryAttempt.claim_reference).where(
        DeliveryAttempt.document_type == "technical",
        DeliveryAttempt.status == "Sent",
    )


def report_has_sent_email(db: Session, report: TechnicalReportRecord) -> bool:
    return (
        db.scalar(
            sent_report_query()
            .where(DeliveryAttempt.claim_reference == report.claim_reference)
            .limit(1)
        )
        is not None
    )


def continue_report(
    db: Session, report: TechnicalReportRecord, actor: User, previous_data=None
):
    if (
        report.archived
        or report.status not in {"Submitted", "Email Sent", "Email Failed"}
        or not get_settings().claims_auto_handover_enabled
    ):
        return None
    db.flush()
    db.scalar(
        select(TechnicalReportRecord)
        .where(TechnicalReportRecord.id == report.id)
        .with_for_update()
    )
    existing = db.scalar(select(ClaimCase).where(ClaimCase.report_id == report.id))
    if existing:
        if previous_data is not None and existing.workflow_status != "Closed":
            current = initial_data(report)
            old = TechnicalReportRecord(
                report_data=previous_data, created_at=report.created_at
            )
            previous = initial_data(old)
            data = dict(existing.data)
            for key in ("damage", "remaining_tread_depth", "tyre_size"):
                if data.get(key) == previous.get(key):
                    data[key] = current[key]
            if data != existing.data:
                existing.data = data
                existing.updated_at = datetime.now(UTC)
                audit(
                    db,
                    actor,
                    existing,
                    "claim.technical_details_synced",
                    {"claim_reference": report.claim_reference},
                )
            ensure_credit_instruction(db, existing, actor)
        return existing
    if not report_has_sent_email(db, report):
        return None
    owners = db.scalars(
        select(User).where(
            User.role == Role.CLAIMS_ADMINISTRATOR,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    ).all()
    default_email = get_settings().seed_claims_admin_email.strip().lower()
    owner = next((u for u in owners if u.email == default_email), None)
    if owner is None and len(owners) == 1:
        owner = owners[0]
    if owner is None:
        return None
    case = ClaimCase(
        report_id=report.id,
        assigned_to=owner.id,
        handed_over_by=actor.id,
        handover_notes="Automatic handover after the technical report email was sent",
        data=initial_data(report),
    )
    db.add(case)
    db.flush()
    audit(
        db,
        actor,
        case,
        "claim.auto_handed_over",
        {"claim_reference": report.claim_reference, "assigned_to": str(owner.id)},
    )
    return case


def continue_existing_reports(db: Session):
    reports = db.scalars(
        select(TechnicalReportRecord)
        .where(
            TechnicalReportRecord.archived.is_(False),
            TechnicalReportRecord.status.in_(
                ["Submitted", "Email Sent", "Email Failed"]
            ),
            TechnicalReportRecord.claim_reference.in_(sent_report_query()),
            ~TechnicalReportRecord.id.in_(select(ClaimCase.report_id)),
        )
        .order_by(TechnicalReportRecord.created_at)
    ).all()
    for report in reports:
        actor = db.get(User, report.created_by)
        if actor:
            continue_report(db, report, actor)


def ensure_credit_instruction(db: Session, case: ClaimCase, actor: User):
    data = case.data
    if (
        data.get("supplier_status") != "Accepted"
        or data.get("customer_credit_percentage") is None
        or case.workflow_status == "Closed"
    ):
        return
    snapshot = flat_claim(case_view(db, case))
    snapshot.pop("instructions", None)
    snapshot["supplier"] = data.get("instruction_supplier") or data["supplier"]
    keys = [key for _, key in INSTRUCTION_COLUMNS] + ["assigned_to"]
    latest = db.scalar(
        select(CreditInstruction)
        .where(CreditInstruction.case_id == case.id)
        .order_by(CreditInstruction.created_at.desc())
    )
    if latest and all(latest.data.get(k) == snapshot.get(k) for k in keys):
        return
    instruction = CreditInstruction(
        case_id=case.id,
        assigned_to=case.assigned_to,
        created_by=actor.id,
        data={**snapshot, "instruction_notes": "Created automatically on save"},
    )
    db.add(instruction)
    db.flush()
    audit(
        db,
        actor,
        case,
        "claim.credit_instruction_auto_issued",
        {
            "instruction_id": str(instruction.id),
            "assigned_to": str(case.assigned_to),
            "customer_credit_percentage": data["customer_credit_percentage"],
        },
    )
