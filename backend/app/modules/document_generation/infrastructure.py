import base64
from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image as PillowImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.app.core.config import get_settings

BLACK = colors.HexColor("#111111")
NAVY = colors.HexColor("#122B52")
BODY = colors.HexColor("#34445F")
RED = colors.HexColor("#ED1C2E")
LIGHT_BLUE = colors.HexColor("#DFEBF7")
PALE_BLUE = colors.HexColor("#F4F8FC")
BORDER = colors.HexColor("#D9D9D9")
MUTED = colors.HexColor("#69778C")
REGULAR_FONT = "RoyalTyresSans"
BOLD_FONT = "RoyalTyresSansBold"
ITALIC_FONT = "RoyalTyresSansItalic"


def _register_fonts() -> None:
    font_root = Path("/usr/share/fonts/truetype/dejavu")
    for name, filename in (
        (REGULAR_FONT, "DejaVuSans.ttf"),
        (BOLD_FONT, "DejaVuSans-Bold.ttf"),
        (ITALIC_FONT, "DejaVuSans-Oblique.ttf"),
    ):
        path = font_root / filename
        if name not in pdfmetrics.getRegisteredFontNames() and path.is_file():
            pdfmetrics.registerFont(TTFont(name, str(path)))


class ReportLabTechnicalReportGenerator:
    def generate(self, report: dict) -> bytes:
        _register_fonts()
        output = BytesIO()
        document = SimpleDocTemplate(
            output,
            pagesize=A4,
            rightMargin=17 * mm,
            leftMargin=17 * mm,
            topMargin=16 * mm,
            bottomMargin=17 * mm,
            title=f"Technical Claim Report {report.get('claimReference', '')}",
            author="Royal Tyres",
            subject="Tyre technical inspection claim",
        )
        styles = self._styles()
        story = self._cover(report, styles)
        for heading, fields in (
            ("Claim and customer details", self._claim_fields()),
            ("Tyre inspection", self._inspection_fields()),
            ("Vehicle and findings", self._vehicle_fields()),
        ):
            story.extend(
                [
                    Spacer(1, 5 * mm),
                    Paragraph(heading, styles["SectionRT"]),
                    Spacer(1, 2.5 * mm),
                    self._details_table(report, styles, fields),
                ]
            )
        story.extend(
            [
                PageBreak(),
                Paragraph("Inspection photographs", styles["SectionRT"]),
                Spacer(1, 1.5 * mm),
                Paragraph(
                    "Photographs captured as supporting evidence for this "
                    "technical claim.",
                    styles["BodyRT"],
                ),
                Spacer(1, 4 * mm),
                self._photos(report, styles),
            ]
        )
        document.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return output.getvalue()

    @staticmethod
    def _styles() -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()

        def style(name, parent, **values):
            return ParagraphStyle(name, parent=base[parent], **values)

        return {
            "TitleRT": style(
                "TitleRT",
                "Title",
                fontName=BOLD_FONT,
                fontSize=23,
                leading=27,
                textColor=BLACK,
                alignment=TA_LEFT,
                spaceAfter=0,
            ),
            "AccentRT": style(
                "AccentRT",
                "Heading2",
                fontName=BOLD_FONT,
                fontSize=12.5,
                leading=15,
                textColor=RED,
                spaceBefore=0,
                spaceAfter=0,
            ),
            "SectionRT": style(
                "SectionRT",
                "Heading2",
                fontName=BOLD_FONT,
                fontSize=15,
                leading=18,
                textColor=BLACK,
                spaceBefore=0,
                spaceAfter=0,
            ),
            "BodyRT": style(
                "BodyRT",
                "BodyText",
                fontName=REGULAR_FONT,
                fontSize=9.5,
                leading=13,
                textColor=BODY,
            ),
            "MetaLabel": style(
                "MetaLabel",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=7.5,
                leading=10,
                textColor=MUTED,
                spaceAfter=1.5 * mm,
            ),
            "MetaValue": style(
                "MetaValue",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=10,
                leading=12,
                textColor=NAVY,
            ),
            "FieldLabel": style(
                "FieldLabel",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=7.2,
                leading=8.5,
                textColor=NAVY,
            ),
            "FieldValue": style(
                "FieldValue",
                "BodyText",
                fontName=REGULAR_FONT,
                fontSize=7.8,
                leading=9.2,
                textColor=BODY,
            ),
            "PhotoLabel": style(
                "PhotoLabel",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=8,
                leading=10,
                textColor=NAVY,
                alignment=TA_CENTER,
            ),
            "Empty": style(
                "Empty",
                "BodyText",
                fontName=REGULAR_FONT,
                fontSize=9,
                leading=12,
                textColor=MUTED,
                alignment=TA_CENTER,
            ),
        }

    def _cover(self, report: dict, styles) -> list:
        settings = get_settings()
        logo_path = (
            Path(settings.royal_tyres_logo_path)
            if settings.royal_tyres_logo_path
            else None
        )
        brand = (
            Image(str(logo_path), width=42 * mm, height=13 * mm, kind="proportional")
            if logo_path and logo_path.is_file()
            else Paragraph("ROYAL TYRES", styles["AccentRT"])
        )
        company_style = ParagraphStyle(
            "CompanyRT",
            parent=styles["BodyRT"],
            fontSize=8,
            leading=10,
            alignment=TA_RIGHT,
        )
        brand_row = Table(
            [
                [
                    brand,
                    Paragraph(
                        escape(settings.royal_tyres_company_details), company_style
                    ),
                ]
            ],
            colWidths=[90 * mm, 86 * mm],
        )
        brand_row.setStyle(self._padding_style())
        metadata = Table(
            [
                [
                    self._meta_cell(
                        "Claim reference",
                        self._value(report, "claimReference", "Pending"),
                        styles,
                    ),
                    self._meta_cell(
                        "Report date",
                        self._value(report, "updatedAt", "Not recorded")[:10],
                        styles,
                    ),
                    self._meta_cell(
                        "Status", self._value(report, "status", "Draft"), styles
                    ),
                ]
            ],
            colWidths=[58.6 * mm] * 3,
        )
        metadata.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                    ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                ]
            )
        )
        return [
            brand_row,
            Spacer(1, 7 * mm),
            Paragraph("Royal Tyres Technical Claim Report", styles["TitleRT"]),
            Spacer(1, 2.5 * mm),
            Paragraph("Tyre inspection and supporting evidence", styles["AccentRT"]),
            Spacer(1, 6 * mm),
            metadata,
        ]

    @staticmethod
    def _padding_style() -> TableStyle:
        return TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )

    @staticmethod
    def _meta_cell(label: str, value: str, styles) -> Table:
        cell = Table(
            [
                [Paragraph(escape(label.upper()), styles["MetaLabel"])],
                [Paragraph(escape(value), styles["MetaValue"])],
            ]
        )
        cell.setStyle(ReportLabTechnicalReportGenerator._padding_style())
        return cell

    def _details_table(
        self, report: dict, styles, fields: list[tuple[str, str]]
    ) -> Table:
        rows = [
            [
                Paragraph("FIELD", styles["FieldLabel"]),
                Paragraph("RECORDED VALUE", styles["FieldLabel"]),
            ]
        ]
        rows.extend(
            [
                Paragraph(escape(label), styles["FieldLabel"]),
                Paragraph(escape(self._value(report, key)), styles["FieldValue"]),
            ]
            for label, key in fields
        )
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3.5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.25 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.25 * mm),
        ]
        for row_index in range(2, len(rows), 2):
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), PALE_BLUE))
        table = Table(rows, colWidths=[57 * mm, 119 * mm], repeatRows=1)
        table.setStyle(TableStyle(commands))
        return table

    def _photos(self, report: dict, styles) -> Table | Paragraph:
        cells = []
        for photo in report.get("photos", []):
            try:
                source = self._open_photo(photo)
                source.thumbnail((1200, 800))
                image_buffer = BytesIO()
                source.save(image_buffer, "JPEG", quality=86, optimize=True)
                image_buffer.seek(0)
                picture = Image(
                    image_buffer, width=80 * mm, height=42 * mm, kind="proportional"
                )
                name = str(photo.get("label") or photo.get("category", "Photo"))
                card = Table(
                    [
                        [Paragraph(escape(name.upper()), styles["PhotoLabel"])],
                        [picture],
                    ],
                    colWidths=[84 * mm],
                    rowHeights=[8 * mm, 46 * mm],
                )
                card.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (0, 0), LIGHT_BLUE),
                            ("BOX", (0, 0), (-1, -1), 0.55, BORDER),
                            ("LINEBELOW", (0, 0), (-1, 0), 0.55, BORDER),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
                            ("TOPPADDING", (0, 0), (-1, -1), 1.5 * mm),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * mm),
                        ]
                    )
                )
                cells.append(card)
            except Exception:
                continue
        if not cells:
            return Paragraph("No photographs were supplied.", styles["Empty"])
        rows = [cells[index : index + 2] for index in range(0, len(cells), 2)]
        if len(rows[-1]) == 1:
            rows[-1].append("")
        table = Table(
            rows, colWidths=[88 * mm, 88 * mm], rowHeights=[58 * mm] * len(rows)
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                ]
            )
        )
        return table

    @staticmethod
    def _open_photo(photo: dict) -> PillowImage.Image:
        if photo.get("filePath"):
            return PillowImage.open(str(photo["filePath"])).convert("RGB")
        encoded = str(photo.get("previewUrl", "")).split(",", 1)[-1]
        return PillowImage.open(BytesIO(base64.b64decode(encoded))).convert("RGB")

    @staticmethod
    def _value(report: dict, key: str, fallback: str = "Not recorded") -> str:
        value = report.get(key)
        return str(value).strip() if value not in (None, "") else fallback

    @staticmethod
    def _claim_fields() -> list[tuple[str, str]]:
        return [
            ("Internal or external", "internalExternal"),
            ("Salesperson or technician", "salesperson"),
            ("Customer", "customerName"),
            ("Customer invoice number", "customerInvoiceNumber"),
            ("Category", "category"),
            ("Inspected location", "inspectedLocation"),
            ("Branch", "branch"),
            ("Claim code or description", "claimCode"),
        ]

    @staticmethod
    def _inspection_fields() -> list[tuple[str, str]]:
        return [
            ("Fitted or loose", "fittedLoose"),
            ("Brand", "brand"),
            ("Rim size", "rimSize"),
            ("Pattern", "pattern"),
            ("DOT", "dot"),
            ("Serial number", "serialNumber"),
            ("Remaining tread depth", "remainingTreadDepth"),
            ("Inspected pressure", "inspectedPressure"),
            ("Tyre mileage", "tyreMileage"),
            ("Tyre position", "tyrePosition"),
            ("Nature of repair", "natureOfRepair"),
        ]

    @staticmethod
    def _vehicle_fields() -> list[tuple[str, str]]:
        return [
            ("Vehicle make and model", "vehicleMakeModel"),
            ("Vehicle mileage", "vehicleMileage"),
            ("Goods transported", "goodsTransported"),
            ("Other relevant information", "notes"),
        ]

    @staticmethod
    def _footer(canvas, document):
        settings = get_settings()
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.45)
        canvas.line(17 * mm, 12 * mm, A4[0] - 17 * mm, 12 * mm)
        canvas.setFont(REGULAR_FONT, 6.8)
        canvas.setFillColor(MUTED)
        canvas.drawString(17 * mm, 8 * mm, settings.royal_tyres_pdf_disclaimer[:150])
        canvas.drawRightString(A4[0] - 17 * mm, 8 * mm, f"Page {document.page}")
        canvas.restoreState()
