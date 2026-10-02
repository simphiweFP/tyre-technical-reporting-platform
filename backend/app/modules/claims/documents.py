from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from backend.app.modules.document_generation import infrastructure as report_style

TRACKER_COLUMNS = [
    ("Date", "claim_date"),
    ("Claim Reference", "claim_reference"),
    ("Supplier", "supplier"),
    ("Customer name", "customer_name"),
    ("Customer Invoice no.", "customer_invoice_number"),
    ("Branch", "branch"),
    ("Brand", "brand"),
    ("Tyre size", "tyre_size"),
    ("Pattern", "pattern"),
    ("Serial number", "serial_number"),
    ("Damage", "damage"),
    ("Remaining Tread depth (RTD) mm", "remaining_tread_depth"),
    ("Original Tread depth (OTD) mm", "original_tread_depth"),
    ("Percentage remaining", "remaining_percentage"),
    ("Submitted to Supplier", "supplier_submitted_date"),
    ("Status", "supplier_status"),
    ("% Accepted", "accepted_percentage"),
    ("Supplier feedback date", "supplier_feedback_date"),
    ("% to Credit", "customer_credit_percentage"),
    ("Credit note /Invoice ref", "credit_note_reference"),
    ("Customer credit date", "customer_credit_date"),
    ("Supplier Offset Invoice no.", "supplier_offset_invoice"),
    ("Supplier offset date", "supplier_offset_date"),
]
INSTRUCTION_COLUMNS = [
    *TRACKER_COLUMNS[:11],
    ("Status", "supplier_status"),
    ("% to Credit", "customer_credit_percentage"),
    ("Credit note /Invoice ref", "credit_note_reference"),
    ("Date credit passed", "customer_credit_date"),
]
EXTRA_COLUMNS = [
    ("Supplier feedback comments", "supplier_feedback_comments"),
    ("Customer credit amount (ZAR)", "customer_credit_amount"),
    ("Supplier recovered amount (ZAR)", "supplier_recovered_amount"),
    ("Instruction supplier", "instruction_supplier"),
]
SCORECARD_COLUMNS = [
    ("Supplier", "supplier"),
    ("Total Claims", "total_claims"),
    ("Acceptance Rate %", "acceptance_rate"),
    ("Avg Response Days", "average_response_days"),
    ("Avg Resolution Days", "average_resolution_days"),
    ("Credit Value Recovered (ZAR)", "credit_value_recovered"),
    ("Rejection Rate %", "rejection_rate"),
]


def flat_claim(view: dict) -> dict:
    return {**view, **view["data"]}


def document_filename(kind: str, claim: str) -> str:
    prefix = {
        "tracker": "Claim_Tracker",
        "credit": "Instruction_to_Credit",
        "rejection": "Rejection_Report",
        "technical": "Technical_Report",
        "scorecard": "Supplier_Scorecard",
    }[kind]
    safe = "".join(c for c in claim if c.isalnum() or c in "_-")
    return f"{prefix}_{safe}.pdf"


def generate_document(kind: str, data: dict) -> bytes:
    report_style._register_fonts()
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = report_style.REGULAR_FONT
    styles["Title"].fontName = report_style.BOLD_FONT
    normal = styles["BodyText"]
    normal.fontSize = 9

    def p(value):
        return Paragraph(
            escape(str(value if value is not None and value != "" else "—")), normal
        )

    result = BytesIO()
    page = landscape(A4) if kind == "scorecard" else A4
    doc = SimpleDocTemplate(
        result,
        pagesize=page,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=32 * mm,
        bottomMargin=20 * mm,
    )
    title = {
        "tracker": "Claim Tracker",
        "credit": "Instruction to Credit",
        "rejection": "Claim Rejection Report",
        "scorecard": "Supplier Scorecard",
    }[kind]
    story = [Paragraph(title, styles["Title"]), Spacer(1, 5 * mm)]
    if kind == "scorecard":
        story.append(p(data.get("period_label", "All recorded claims")))
        rows = [[p(label) for label, _ in SCORECARD_COLUMNS]]
        rows += [
            [p(row.get(key)) for _, key in SCORECARD_COLUMNS]
            for row in data["scorecard"]
        ]
        if len(rows) == 1:
            rows.append([p("No claims in this period"), *[p("") for _ in range(6)]])
        table = Table(rows, colWidths=[doc.width / 7] * 7, repeatRows=1)
        story += [
            table,
            Spacer(1, 5 * mm),
            p(
                "Acceptance and rejection rates use all claims in the selected "
                "period. Response days: supplier submission to feedback. "
                "Resolution days: claim receipt to customer credit. Only "
                "completed supplier offsets contribute to recovered value."
            ),
        ]
        for row in data["scorecard"]:
            if row.get("missing_recovery_amounts"):
                story.append(
                    p(
                        f"{row['supplier']}: {row['missing_recovery_amounts']} "
                        "completed offsets have no recovery amount."
                    )
                )
    else:
        columns = INSTRUCTION_COLUMNS if kind == "credit" else TRACKER_COLUMNS
        rows = [
            [p(label), p(data.get(key))] for label, key in [*columns, *EXTRA_COLUMNS]
        ]
        if kind == "credit":
            rows += [
                [p("Issued to"), p(data.get("owner_name"))],
                [p("Instruction notes"), p(data.get("instruction_notes"))],
            ]
        table = Table(
            rows, colWidths=[doc.width * 0.43, doc.width * 0.57], repeatRows=0
        )
        story.append(table)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef0ff")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d9dce8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    def header_footer(canvas, document):
        canvas.saveState()
        logo = Path(__file__).resolve().parents[3] / "assets/email/royal-tyres-logo.png"
        if logo.exists():
            canvas.drawImage(
                str(logo),
                16 * mm,
                page[1] - 27 * mm,
                width=42 * mm,
                height=24 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        canvas.setFillColor(colors.HexColor("#2f3398"))
        canvas.setFont(report_style.REGULAR_FONT, 9)
        canvas.drawRightString(
            page[0] - 16 * mm, page[1] - 16 * mm, "Royal Tyres · Claims Management"
        )
        canvas.setFont(report_style.REGULAR_FONT, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(
            16 * mm, 15 * mm, "Confidential · Royal Tyres claims and credit records"
        )
        canvas.drawRightString(page[0] - 16 * mm, 15 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return result.getvalue()
