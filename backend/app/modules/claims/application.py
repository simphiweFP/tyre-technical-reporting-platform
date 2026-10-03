from collections import Counter, defaultdict
from datetime import date
from math import isfinite
from statistics import mean
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.claims.infrastructure import ClaimCase, CreditInstruction
from backend.app.modules.claims.schemas import ClaimData
from backend.app.modules.identity.domain import Role
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.reports.infrastructure import TechnicalReportRecord

COMMON_FIELDS = {
    "customer_name": "customerName",
    "customer_invoice_number": "customerInvoiceNumber",
    "branch": "branch",
    "brand": "brand",
    "tyre_size": "tyreSize",
    "pattern": "pattern",
    "serial_number": "serialNumber",
}


def check_case(
    db: Session, case_id: UUID, user: User, *, lock: bool = False
) -> ClaimCase:
    query = select(ClaimCase).where(ClaimCase.id == case_id)
    case = db.scalar(query.with_for_update() if lock else query)
    if (
        not case
        or (user.role == Role.CLAIMS_ADMINISTRATOR and case.assigned_to != user.id)
        or (
            user.role == Role.REPORT_CAPTURER
            and db.get(TechnicalReportRecord, case.report_id).created_by != user.id
        )
    ):
        raise HTTPException(status_code=404, detail="Claim not found")
    return case


def required_owner(db: Session, user_id: UUID) -> User:
    owner = db.get(User, user_id)
    if (
        not owner
        or not owner.is_active
        or owner.deleted_at
        or owner.role != Role.CLAIMS_ADMINISTRATOR
    ):
        raise HTTPException(
            status_code=422, detail="Select an active Claims Administrator"
        )
    return owner


def audit(db: Session, user: User, case: ClaimCase, action: str, details: dict):
    db.add(
        AuditEvent(
            actor_id=user.id,
            action=action,
            entity_type="claim_case",
            entity_id=str(case.id),
            details=details,
        )
    )


def initial_data(report: TechnicalReportRecord) -> dict:
    source = report.report_data
    try:
        rtd = float(source.get("remainingTreadDepth"))
        if not isfinite(rtd) or rtd < 0:
            rtd = None
    except (ValueError, TypeError):
        rtd = None
    return ClaimData(
        claim_date=report.created_at.date(),
        damage=str(source.get("claimCode") or source.get("notes") or ""),
        remaining_tread_depth=rtd,
        tyre_size=str(source.get("tyreSize") or source.get("size") or ""),
    ).model_dump(mode="json")


def case_view(db: Session, case: ClaimCase) -> dict:
    report = db.get(TechnicalReportRecord, case.report_id)
    owner = db.get(User, case.assigned_to)
    source = report.report_data
    common = {key: str(source.get(field) or "") for key, field in COMMON_FIELDS.items()}
    data = case.data
    common["tyre_size"] = data.get("tyre_size") or common["tyre_size"]
    rtd, otd = data.get("remaining_tread_depth"), data.get("original_tread_depth")
    remaining = (
        round(float(rtd) / float(otd) * 100, 2) if rtd is not None and otd else None
    )
    accepted = data.get("supplier_status") == "Accepted"
    credit_needed = accepted and (
        data.get("customer_credit_percentage") is None
        or data["customer_credit_percentage"] > 0
    )
    offset_needed = accepted and (
        data.get("accepted_percentage") is None or data["accepted_percentage"] > 0
    )
    return {
        "id": str(case.id),
        "report_id": str(report.id),
        "claim_reference": report.claim_reference,
        **common,
        "data": data,
        "remaining_percentage": remaining,
        "assigned_to": str(case.assigned_to),
        "owner_name": owner.full_name,
        "owner_email": owner.email,
        "handover_notes": case.handover_notes,
        "received_at": case.received_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
        "workflow_status": case.workflow_status,
        "credit_outstanding": credit_needed
        and not (
            (data.get("credit_note_reference") or "").strip()
            and data.get("customer_credit_date")
        ),
        "supplier_offset_outstanding": offset_needed
        and not (
            (data.get("supplier_offset_invoice") or "").strip()
            and data.get("supplier_offset_date")
        ),
        "instructions": [
            {
                "id": str(i.id),
                "data": i.data,
                "created_at": i.created_at.isoformat(),
                "acknowledged_at": i.acknowledged_at.isoformat()
                if i.acknowledged_at
                else None,
            }
            for i in db.scalars(
                select(CreditInstruction)
                .where(CreditInstruction.case_id == case.id)
                .order_by(CreditInstruction.created_at.desc())
            ).all()
        ],
    }


def visible_cases(db: Session, user: User) -> list[ClaimCase]:
    query = select(ClaimCase).order_by(ClaimCase.received_at.desc())
    if user.role == Role.CLAIMS_ADMINISTRATOR:
        query = query.where(ClaimCase.assigned_to == user.id)
    elif user.role == Role.REPORT_CAPTURER:
        query = query.where(
            ClaimCase.report_id.in_(
                select(TechnicalReportRecord.id).where(
                    TechnicalReportRecord.created_by == user.id
                )
            )
        )
    return db.scalars(query).all()


def filter_views(
    views: list[dict], search="", supplier="", branch="", date_from=None, date_to=None
):
    result = []
    for item in views:
        d = item["data"]
        day = date.fromisoformat(d["claim_date"])
        if date_from and day < date_from or date_to and day > date_to:
            continue
        if supplier and d.get("supplier", "").casefold() != supplier.casefold():
            continue
        if branch and item["branch"].casefold() != branch.casefold():
            continue
        haystack = " ".join(
            str(item.get(k, ""))
            for k in [
                "claim_reference",
                "customer_name",
                "brand",
                "branch",
                "serial_number",
            ]
        )
        if (
            search.strip().casefold()
            not in (haystack + " " + d.get("supplier", "")).casefold()
        ):
            continue
        result.append(item)
    return result


def metrics(views: list[dict]) -> dict:
    groups = defaultdict(list)
    for item in views:
        groups[item["data"].get("supplier") or "Unassigned"].append(item)
    cards = []
    for supplier, items in sorted(groups.items()):
        accepted = sum(i["data"].get("supplier_status") == "Accepted" for i in items)
        rejected = sum(i["data"].get("supplier_status") == "Rejected" for i in items)
        response_days, resolution_days, recovered = [], [], 0.0
        missing_amounts = 0
        for item in items:
            d = item["data"]
            for a, b, target in [
                ("supplier_submitted_date", "supplier_feedback_date", response_days),
                ("claim_date", "customer_credit_date", resolution_days),
            ]:
                if b == "customer_credit_date" and not (
                    d.get("credit_note_reference") or ""
                ).strip():
                    continue
                if d.get(a) and d.get(b):
                    days = (date.fromisoformat(d[b]) - date.fromisoformat(d[a])).days
                    if days >= 0:
                        target.append(days)
            if (d.get("supplier_offset_invoice") or "").strip() and d.get(
                "supplier_offset_date"
            ):
                if d.get("supplier_recovered_amount") is None:
                    missing_amounts += 1
                else:
                    recovered += d["supplier_recovered_amount"]
        cards.append(
            {
                "supplier": supplier,
                "total_claims": len(items),
                "acceptance_rate": round(accepted / len(items) * 100, 2),
                "rejection_rate": round(rejected / len(items) * 100, 2),
                "average_response_days": round(mean(response_days), 1)
                if response_days
                else None,
                "average_resolution_days": round(mean(resolution_days), 1)
                if resolution_days
                else None,
                "response_sample_size": len(response_days),
                "resolution_sample_size": len(resolution_days),
                "credit_value_recovered": round(recovered, 2),
                "missing_recovery_amounts": missing_amounts,
            }
        )
    suppliers = Counter(
        i["data"].get("supplier") for i in views if i["data"].get("supplier")
    )
    customers = Counter(i["customer_name"] for i in views if i["customer_name"])

    def extremes(counts, most):
        if not counts:
            return []
        target = (max if most else min)(counts.values())
        return [
            {"name": name, "count": count}
            for name, count in sorted(counts.items())
            if count == target
        ]

    return {
        "scorecard": cards,
        "total_claims": len(views),
        "under_review": sum(
            i["data"].get("supplier_status") == "Under review" for i in views
        ),
        "outstanding_supplier_offsets": sum(
            i["supplier_offset_outstanding"] for i in views
        ),
        "credit_notes_not_passed": sum(i["credit_outstanding"] for i in views),
        "most_supplier": extremes(suppliers, True),
        "least_supplier": extremes(suppliers, False),
        "most_customer": extremes(customers, True),
        "least_customer": extremes(customers, False),
    }
