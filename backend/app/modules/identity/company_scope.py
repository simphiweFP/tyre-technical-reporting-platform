"""Apply RT-Auth company/warehouse assignments to existing branch-based data."""

from collections import Counter

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, event, func, or_, select
from sqlalchemy.orm import Session, with_loader_criteria

from backend.app.core.config import get_settings
from backend.app.modules.auditing.infrastructure import AuditEvent
from backend.app.modules.branches.infrastructure import Branch
from backend.app.modules.claims.infrastructure import ClaimCase, CreditInstruction
from backend.app.modules.delivery.infrastructure import DeliveryAttempt
from backend.app.modules.reports.infrastructure import (
    ReportImage,
    TechnicalReportRecord,
)


def apply_scope(db, claims):
    allowed = []
    branch_ids = []
    branches = db.scalars(select(Branch)).all()
    names = Counter(branch.name for branch in branches)
    for branch in branches:
        if not branch.is_active or branch.deleted_at:
            continue
        scope = get_settings().auth_branch_scopes.get(branch.code)
        if not scope:
            continue
        company, warehouse = scope.get("company"), scope.get("warehouse")
        if company in claims["companies"] and warehouse in claims["warehouses"].get(
            company, []
        ):
            allowed.append(branch.code)
            if names[branch.name] == 1:
                allowed.append(branch.name)
            branch_ids.append(branch.id)
    db.info["company_branches"] = tuple(allowed)
    db.info["company_branch_ids"] = tuple(branch_ids)


@event.listens_for(Session, "do_orm_execute")
def restrict_reads(execute_state):
    allowed = execute_state.session.info.get("company_branches")
    if allowed is None:
        return
    records = select(TechnicalReportRecord.id).where(
        TechnicalReportRecord.branch_name.in_(allowed)
    )
    refs = select(TechnicalReportRecord.claim_reference).where(
        TechnicalReportRecord.branch_name.in_(allowed)
    )
    cases = select(ClaimCase.id).where(ClaimCase.report_id.in_(records))
    report_ids = select(
        func.replace(cast(TechnicalReportRecord.id, String), "-", "")
    ).where(TechnicalReportRecord.branch_name.in_(allowed))
    case_ids = select(func.replace(cast(ClaimCase.id, String), "-", "")).where(
        ClaimCase.report_id.in_(records)
    )
    delivery_ids = select(
        func.replace(cast(DeliveryAttempt.id, String), "-", "")
    ).where(DeliveryAttempt.claim_reference.in_(refs))
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            AuditEvent,
            or_(
                and_(
                    AuditEvent.entity_type == "technical_report",
                    or_(
                        AuditEvent.entity_id.in_(refs),
                        func.replace(AuditEvent.entity_id, "-", "").in_(report_ids),
                    ),
                ),
                and_(
                    AuditEvent.entity_type == "claim_case",
                    func.replace(AuditEvent.entity_id, "-", "").in_(case_ids),
                ),
                and_(
                    AuditEvent.entity_type == "delivery_attempt",
                    func.replace(AuditEvent.entity_id, "-", "").in_(delivery_ids),
                ),
                and_(
                    AuditEvent.entity_type == "user",
                    AuditEvent.actor_id
                    == execute_state.session.info.get("company_user_id"),
                ),
            ),
            include_aliases=True,
        ),
        with_loader_criteria(
            TechnicalReportRecord,
            TechnicalReportRecord.branch_name.in_(allowed),
            include_aliases=True,
        ),
        with_loader_criteria(
            Branch,
            Branch.id.in_(execute_state.session.info["company_branch_ids"]),
            include_aliases=True,
        ),
        with_loader_criteria(
            ReportImage, ReportImage.report_id.in_(records), include_aliases=True
        ),
        with_loader_criteria(
            ClaimCase, ClaimCase.report_id.in_(records), include_aliases=True
        ),
        with_loader_criteria(
            CreditInstruction,
            CreditInstruction.case_id.in_(cases),
            include_aliases=True,
        ),
        with_loader_criteria(
            DeliveryAttempt,
            DeliveryAttempt.claim_reference.in_(refs),
            include_aliases=True,
        ),
    )


@event.listens_for(Session, "before_flush")
def restrict_writes(db, *_):
    allowed = db.info.get("company_branches")
    if allowed is None:
        return
    for record in db.new.union(db.dirty).union(db.deleted):
        if (
            isinstance(record, TechnicalReportRecord)
            and record.branch_name not in allowed
        ):
            raise HTTPException(403, "This branch is outside your company access")
        if (
            isinstance(record, Branch)
            and record.id not in db.info["company_branch_ids"]
        ):
            raise HTTPException(403, "Branch access is managed through RT-Auth")
