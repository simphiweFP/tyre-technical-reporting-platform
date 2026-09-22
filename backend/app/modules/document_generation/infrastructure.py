import base64
from io import BytesIO
from pathlib import Path

from PIL import Image as PillowImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.app.core.config import get_settings


class ReportLabTechnicalReportGenerator:
    def generate(self, report: dict) -> bytes:
        output = BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            rightMargin=12 * mm,
            leftMargin=12 * mm,
            topMargin=11 * mm,
            bottomMargin=11 * mm,
            title=f"Technical Report {report.get('claimReference', '')}",
        )
        styles = getSampleStyleSheet()
        small = ParagraphStyle(
            "Small", parent=styles["BodyText"], fontSize=7, leading=9
        )
        label = ParagraphStyle(
            "Label",
            parent=small,
            textColor=colors.HexColor("#667078"),
            fontName="Helvetica-Bold",
        )
        photo_label = ParagraphStyle(
            "PhotoLabel", parent=small, alignment=TA_CENTER, fontName="Helvetica-Bold"
        )
        story = [self._header(report, styles), Spacer(1, 5 * mm)]
        story.append(
            Table(
                [
                    [
                        self._details(report, label, small),
                        self._photos(report, photo_label),
                    ]
                ],
                colWidths=[78 * mm, 181 * mm],
                hAlign="LEFT",
                style=TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ]
                ),
            )
        )
        document.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return output.getvalue()

    def _header(self, report: dict, styles) -> Table:
        title = ParagraphStyle(
            "TitleRT",
            parent=styles["Title"],
            fontSize=16,
            leading=18,
            textColor=colors.HexColor("#1B1D1F"),
        )
        reference = report.get("claimReference", "Pending")
        date = str(report.get("updatedAt", ""))[:10]
        settings = get_settings()
        logo_path = (
            Path(settings.royal_tyres_logo_path)
            if settings.royal_tyres_logo_path
            else None
        )
        brand = (
            Image(str(logo_path), width=50 * mm, height=15 * mm, kind="proportional")
            if logo_path and logo_path.is_file()
            else Paragraph("<b>ROYAL TYRES</b>", title)
        )
        table = Table(
            [
                [
                    brand,
                    Paragraph("TECHNICAL REPORT", title),
                    Paragraph(
                        f"<b>Claim ref:</b> {reference}<br/>"
                        f"<b>Date:</b> {date}<br/>"
                        f"{settings.royal_tyres_company_details}",
                        styles["BodyText"],
                    ),
                ]
            ],
            colWidths=[65 * mm, 125 * mm, 65 * mm],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#D71920")),
                    ("TEXTCOLOR", (0, 0), (0, 0), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#BEC4C8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                ]
            )
        )
        return table

    @staticmethod
    def _details(report: dict, label_style, value_style) -> Table:
        fields = [
            ("Internal / External", "internalExternal"),
            ("Salesperson / Technician", "salesperson"),
            ("Customer", "customerName"),
            ("Invoice number", "customerInvoiceNumber"),
            ("Category", "category"),
            ("Inspected location", "inspectedLocation"),
            ("Fitted / Loose", "fittedLoose"),
            ("Brand", "brand"),
            ("Rim size", "rimSize"),
            ("Pattern", "pattern"),
            ("DOT", "dot"),
            ("Serial number", "serialNumber"),
            ("Claim code", "claimCode"),
            ("Remaining tread depth", "remainingTreadDepth"),
            ("Inspected pressure", "inspectedPressure"),
            ("Tyre mileage", "tyreMileage"),
            ("Tyre position", "tyrePosition"),
            ("Nature of repair", "natureOfRepair"),
            ("Vehicle", "vehicleMakeModel"),
            ("Vehicle mileage", "vehicleMileage"),
            ("Goods transported", "goodsTransported"),
            ("Other relevant information", "notes"),
        ]
        rows = [
            [
                Paragraph(name, label_style),
                Paragraph(str(report.get(key) or "—"), value_style),
            ]
            for name, key in fields
        ]
        table = Table(rows, colWidths=[31 * mm, 45 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D5D9DC")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF4F8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.1 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.1 * mm),
                ]
            )
        )
        return table

    def _photos(self, report: dict, label_style) -> Table:
        cells = []
        for photo in report.get("photos", []):
            try:
                if photo.get("filePath"):
                    source = PillowImage.open(str(photo["filePath"])).convert("RGB")
                else:
                    encoded = str(photo.get("previewUrl", "")).split(",", 1)[-1]
                    raw = base64.b64decode(encoded)
                    source = PillowImage.open(BytesIO(raw)).convert("RGB")
                source.thumbnail((430, 300))
                image_buffer = BytesIO()
                source.save(image_buffer, "JPEG", quality=82)
                image_buffer.seek(0)
                picture = Image(
                    image_buffer, width=48 * mm, height=34 * mm, kind="proportional"
                )
                cells.append(
                    Table(
                        [
                            [
                                Paragraph(
                                    str(
                                        photo.get("label")
                                        or photo.get("category", "Photo")
                                    ),
                                    label_style,
                                )
                            ],
                            [picture],
                        ],
                        colWidths=[55 * mm],
                        rowHeights=[6 * mm, 34 * mm],
                        style=TableStyle(
                            [
                                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ("TOPPADDING", (0, 0), (-1, -1), 0),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                            ]
                        ),
                    )
                )
            except Exception:
                continue
        if not cells:
            cells = [Paragraph("No photographs supplied", label_style)]
        rows = [cells[index : index + 3] for index in range(0, len(cells), 3)]
        while rows and len(rows[-1]) < 3:
            rows[-1].append("")
        table = Table(rows, colWidths=[59 * mm] * 3, rowHeights=[43 * mm] * len(rows))
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#AEB6BC")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ]
            )
        )
        return table

    @staticmethod
    def _footer(canvas, document):
        settings = get_settings()
        canvas.saveState()
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor("#727A80"))
        canvas.drawString(12 * mm, 6 * mm, settings.royal_tyres_pdf_disclaimer[:150])
        canvas.drawRightString(
            landscape(A4)[0] - 12 * mm, 6 * mm, f"Page {document.page}"
        )
        canvas.restoreState()
