import base64
from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image as PillowImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
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

BLACK = colors.HexColor("#000000")
NAVY = colors.HexColor("#10254A")
BODY = colors.HexColor("#24344D")
RED = colors.HexColor("#E3182D")
LIGHT_BLUE = colors.HexColor("#EAF3FC")
PALE_BLUE = colors.HexColor("#F7FAFD")
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
            pagesize=LETTER,
            rightMargin=0.7 * 25.4 * mm,
            leftMargin=0.7 * 25.4 * mm,
            topMargin=64 * mm,
            bottomMargin=40 * mm,
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
                    Spacer(1, 6 / 72 * 25.4 * mm),
                    Paragraph(heading, styles["SectionRT"]),
                    Spacer(1, 3 / 72 * 25.4 * mm),
                    self._details_table(report, styles, fields),
                ]
            )
        story.extend(
            [
                PageBreak(),
                Paragraph("Inspection photographs", styles["SectionRT"]),
                Spacer(1, 4 / 72 * 25.4 * mm),
                Paragraph(
                    "Photographs captured as supporting evidence for this "
                    "technical claim.",
                    styles["BodyRT"],
                ),
                Spacer(1, 3 * mm),
                self._photos(report, styles),
            ]
        )
        document.build(
            story, onFirstPage=self._page_branding, onLaterPages=self._page_branding
        )
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
                fontSize=10.5,
                leading=13,
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
                fontSize=10.5,
                leading=14,
                textColor=BODY,
            ),
            "MetaLabel": style(
                "MetaLabel",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=8.5,
                leading=10.5,
                textColor=MUTED,
                spaceAfter=1.5 * mm,
            ),
            "MetaValue": style(
                "MetaValue",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=9.5,
                leading=11.5,
                textColor=NAVY,
            ),
            "FieldLabel": style(
                "FieldLabel",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=9,
                leading=11,
                textColor=NAVY,
            ),
            "FieldValue": style(
                "FieldValue",
                "BodyText",
                fontName=REGULAR_FONT,
                fontSize=9,
                leading=11,
                textColor=BODY,
            ),
            "PhotoLabel": style(
                "PhotoLabel",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=9.5,
                leading=11.5,
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
            colWidths=[60.1 * mm] * 3,
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
                Paragraph("FIELD", styles["FieldLabel"]),
                Paragraph("RECORDED VALUE", styles["FieldLabel"]),
            ]
        ]
        for index in range(0, len(fields), 2):
            left_label, left_key = fields[index]
            row = [
                Paragraph(escape(left_label), styles["FieldLabel"]),
                Paragraph(escape(self._value(report, left_key)), styles["FieldValue"]),
            ]
            if index + 1 < len(fields):
                right_label, right_key = fields[index + 1]
                row.extend(
                    [
                        Paragraph(escape(right_label), styles["FieldLabel"]),
                        Paragraph(
                            escape(self._value(report, right_key)),
                            styles["FieldValue"],
                        ),
                    ]
                )
            else:
                row.extend(["", ""])
            rows.append(row)
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_BLUE),
            ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3.5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 0.75 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0.75 * mm),
        ]
        for row_index in range(2, len(rows), 2):
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), PALE_BLUE))
        table = Table(
            rows,
            colWidths=[35 * mm, 55.15 * mm, 35 * mm, 55.15 * mm],
            repeatRows=1,
        )
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
                    image_buffer, width=80 * mm, height=26 * mm, kind="proportional"
                )
                name = str(photo.get("label") or photo.get("category", "Photo"))
                card = Table(
                    [
                        [Paragraph(escape(name.upper()), styles["PhotoLabel"])],
                        [picture],
                    ],
                    colWidths=[86 * mm],
                    rowHeights=[7 * mm, 29 * mm],
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
            rows, colWidths=[90.15 * mm, 90.15 * mm], rowHeights=[38 * mm] * len(rows)
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
    def _page_branding(canvas, document):
        settings = get_settings()
        asset_root = Path(__file__).resolve().parents[3] / "assets"
        header_path = Path(
            settings.royal_tyres_report_header_path
            or asset_root / "royal-tyres-report-header.png"
        )
        footer_path = Path(
            settings.royal_tyres_report_footer_path
            or asset_root / "royal-tyres-report-footer.png"
        )
        canvas.saveState()
        side_margin = 0.7 * 25.4 * mm
        available_width = LETTER[0] - 2 * side_margin
        if header_path.is_file():
            with PillowImage.open(header_path) as source:
                header = source.crop((35, 30, 970, 280)).convert("RGB")
                header_buffer = BytesIO()
                header.save(header_buffer, "PNG")
                header_buffer.seek(0)
                header_height = available_width * header.height / header.width
                canvas.drawImage(
                    ImageReader(header_buffer),
                    side_margin,
                    LETTER[1] - 10 * mm - header_height,
                    width=available_width,
                    height=header_height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
        if footer_path.is_file():
            with PillowImage.open(footer_path) as source:
                footer = source.crop((43, 155, 935, 270)).convert("RGB")
                footer_buffer = BytesIO()
                footer.save(footer_buffer, "PNG")
                footer_buffer.seek(0)
                footer_height = available_width * footer.height / footer.width
                canvas.drawImage(
                    ImageReader(footer_buffer),
                    side_margin,
                    8 * mm,
                    width=available_width,
                    height=footer_height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
        canvas.setFont(REGULAR_FONT, 6.8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(LETTER[0] - side_margin, 4 * mm, f"Page {document.page}")
        canvas.restoreState()
