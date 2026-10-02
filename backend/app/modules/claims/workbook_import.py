"""Read the two source sheets without evaluating spreadsheet formulas."""

import posixpath
import re
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.modules.claims.application import audit, case_view
from backend.app.modules.claims.documents import flat_claim
from backend.app.modules.claims.infrastructure import ClaimCase, CreditInstruction
from backend.app.modules.claims.schemas import ClaimData
from backend.app.modules.identity.infrastructure import User
from backend.app.modules.reports.infrastructure import TechnicalReportRecord

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def read_source_sheets(content: bytes) -> tuple[dict[str, list[dict]], date]:
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 25 * 1024 * 1024:
                raise HTTPException(
                    status_code=413, detail="Workbook expands beyond 25 MB"
                )
            strings = []
            if "xl/sharedStrings.xml" in archive.namelist():
                strings = [
                    "".join(t.text or "" for t in si.findall(".//s:t", NS))
                    for si in ET.fromstring(
                        archive.read("xl/sharedStrings.xml")
                    ).findall("s:si", NS)
                ]
            book = ET.fromstring(archive.read("xl/workbook.xml"))
            props = book.find("s:workbookPr", NS)
            epoch = (
                date(1904, 1, 1)
                if props is not None and props.get("date1904") in {"1", "true"}
                else date(1899, 12, 30)
            )
            relations = {
                r.get("Id"): r.get("Target")
                for r in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            }
            sheets = {}
            for sheet in book.findall("s:sheets/s:sheet", NS):
                name = sheet.get("name")
                if name not in {"Claim Tracker", "Instruction to credit"}:
                    continue
                target = relations[sheet.get(RID)]
                path = (
                    target.lstrip("/")
                    if target.startswith("/")
                    else posixpath.normpath("xl/" + target)
                )
                if not path.startswith("xl/"):
                    raise ValueError("Invalid worksheet path")
                rows = []
                for row in ET.fromstring(archive.read(path)).findall(
                    "s:sheetData/s:row", NS
                ):
                    values = {"_row": int(row.get("r", "0"))}
                    for cell in row.findall("s:c", NS):
                        column = re.sub(r"\d", "", cell.get("r", ""))
                        value_node = cell.find("s:v", NS)
                        value = value_node.text if value_node is not None else None
                        if cell.get("t") == "s" and value is not None:
                            value = strings[int(value)]
                        elif cell.get("t") == "inlineStr":
                            value = "".join(
                                t.text or "" for t in cell.findall(".//s:t", NS)
                            )
                        values[column] = value
                    rows.append(values)
                    if len(rows) > 10000:
                        raise HTTPException(
                            status_code=413,
                            detail="Import at most 10,000 worksheet rows",
                        )
                sheets[name] = rows
            if "Claim Tracker" not in sheets:
                raise ValueError("The workbook must contain the Claim Tracker sheet")
            return sheets, epoch
    except (BadZipFile, KeyError, ValueError, ET.ParseError) as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid Claims Management workbook: {exc}"
        ) from exc


def import_workbook(db: Session, content: bytes, owner: User, user: User) -> dict:
    sheets, epoch = read_source_sheets(content)
    instructions = {
        str(r.get("B") or "").strip(): r
        for r in sheets.get("Instruction to credit", [])
        if re.fullmatch(r"I\d{6}", str(r.get("B") or "").strip())
    }
    imported, skipped, warnings = 0, 0, []

    def text(row, col):
        value = row.get(col)
        return "" if value in (None, "-", "") else str(value).strip()

    def number(row, col, percent=False):
        value = text(row, col)
        if not value:
            return None
        parsed = float(value.rstrip("%"))
        return (
            parsed * 100
            if percent and not value.endswith("%") and abs(parsed) <= 1
            else parsed
        )

    def day(row, col):
        value = text(row, col)
        if not value:
            return None
        try:
            return (epoch + timedelta(days=float(value))).isoformat()
        except ValueError:
            return date.fromisoformat(value[:10]).isoformat()

    for row in sheets["Claim Tracker"]:
        reference = text(row, "B")
        if not re.fullmatch(r"I\d{6}", reference):
            if row["_row"] >= 4 and any(text(row, c) for c in ("C", "D", "P")):
                skipped += 1
                warnings.append(
                    f"Tracker row {row['_row']}: add a unique I000001-format "
                    "reference before importing."
                )
            continue
        if db.scalar(
            select(TechnicalReportRecord.id).where(
                TechnicalReportRecord.claim_reference == reference
            )
        ):
            skipped += 1
            warnings.append(f"{reference}: already exists; no data overwritten.")
            continue
        try:
            status = text(row, "P") or "Under review"
            feedback = text(row, "Q") if status == "Rejected" else ""
            raw = {
                "claim_date": day(row, "A"),
                "supplier": text(row, "C"),
                "tyre_size": text(row, "H"),
                "damage": text(row, "K"),
                "remaining_tread_depth": number(row, "L"),
                "original_tread_depth": number(row, "M"),
                "supplier_submitted_date": day(row, "O"),
                "supplier_status": status,
                "accepted_percentage": 0
                if status == "Rejected"
                else number(row, "Q", True),
                "supplier_feedback_date": day(row, "R"),
                "supplier_feedback_comments": feedback,
                "customer_credit_percentage": number(row, "S", True),
                "credit_note_reference": text(row, "T"),
                "customer_credit_date": day(row, "U"),
                "supplier_offset_invoice": text(row, "V"),
                "supplier_offset_date": day(row, "W"),
            }
            instruction = instructions.get(reference)
            if instruction:
                raw["instruction_supplier"] = text(instruction, "C")
                if raw["customer_credit_percentage"] is None:
                    raw["customer_credit_percentage"] = number(instruction, "M", True)
                raw["credit_note_reference"] = raw["credit_note_reference"] or text(
                    instruction, "N"
                )
                raw["customer_credit_date"] = raw["customer_credit_date"] or day(
                    instruction, "O"
                )
                if text(instruction, "L") and text(instruction, "L") != status:
                    warnings.append(
                        f"{reference}: tracker decision retained; "
                        "instruction sheet decision differs."
                    )
            data = ClaimData.model_validate(raw).model_dump(mode="json")
        except (ValueError, TypeError, ValidationError) as exc:
            skipped += 1
            warnings.append(
                f"{reference}: row {row['_row']} needs correction: {str(exc)[:250]}"
            )
            continue
        report_data = {
            "claimReference": reference,
            "status": "Submitted",
            "customerName": text(row, "D"),
            "customerInvoiceNumber": text(row, "E"),
            "branch": text(row, "F"),
            "brand": text(row, "G"),
            "tyreSize": text(row, "H"),
            "pattern": text(row, "I"),
            "serialNumber": text(row, "J"),
            "claimCode": text(row, "K"),
            "remainingTreadDepth": text(row, "L"),
            "photos": [],
            "import_source": "Claims Management workbook",
            "import_tracker_row": row,
        }
        report = TechnicalReportRecord(
            claim_reference=reference,
            status="Submitted",
            report_data=report_data,
            customer_name=text(row, "D"),
            invoice_number=text(row, "E"),
            branch_name=text(row, "F"),
            tyre_brand=text(row, "G"),
            serial_number=text(row, "J"),
            created_by=user.id,
            created_at=datetime.combine(
                date.fromisoformat(data["claim_date"]), datetime.min.time(), UTC
            ),
        )
        db.add(report)
        db.flush()
        case = ClaimCase(
            report_id=report.id,
            assigned_to=owner.id,
            handed_over_by=user.id,
            handover_notes="Imported from Claims Management workbook",
            data=data,
            workflow_status="In progress",
        )
        db.add(case)
        db.flush()
        audit(
            db,
            user,
            case,
            "claim.workbook_imported",
            {
                "claim_reference": reference,
                "tracker_row": row["_row"],
                "instruction_source_row": instruction or {},
            },
        )
        if (
            instruction
            and status == "Accepted"
            and data["customer_credit_percentage"] is not None
        ):
            snapshot = flat_claim(case_view(db, case))
            snapshot.pop("instructions", None)
            snapshot.update(
                {
                    "claim_date": day(instruction, "A"),
                    "claim_reference": reference,
                    "supplier": text(instruction, "C"),
                    "customer_name": text(instruction, "D"),
                    "customer_invoice_number": text(instruction, "E"),
                    "branch": text(instruction, "F"),
                    "brand": text(instruction, "G"),
                    "tyre_size": text(instruction, "H"),
                    "pattern": text(instruction, "I"),
                    "serial_number": text(instruction, "J"),
                    "damage": text(instruction, "K"),
                    "supplier_status": text(instruction, "L"),
                    "customer_credit_percentage": number(instruction, "M", True),
                    "credit_note_reference": text(instruction, "N"),
                    "customer_credit_date": day(instruction, "O"),
                }
            )
            db.add(
                CreditInstruction(
                    case_id=case.id,
                    assigned_to=owner.id,
                    created_by=user.id,
                    data=snapshot,
                )
            )
        imported += 1
    db.commit()
    warnings.append(
        "Scorecards and Other Metrics are recalculated from imported claims; "
        "workbook summary figures are not treated as source claims."
    )
    return {"imported": imported, "skipped": skipped, "warnings": warnings}
