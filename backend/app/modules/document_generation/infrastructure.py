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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from backend.app.core.config import get_settings

BLACK = colors.HexColor("#000000")
NAVY = colors.HexColor("#10254A")
BODY = colors.HexColor("#24344D")
RED = colors.HexColor("#E3182D")
TEAL = colors.HexColor("#18B99A")
LIGHT_BLUE = colors.HexColor("#EAF3FC")
PALE_BLUE = colors.HexColor("#F7FAFD")
BORDER = colors.HexColor("#D9D9D9")
MUTED = colors.HexColor("#69778C")
REGULAR_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"
ITALIC_FONT = "Helvetica-Oblique"


def _register_fonts() -> None:
    global REGULAR_FONT, BOLD_FONT, ITALIC_FONT

    candidates = [
        (
            Path("/usr/share/fonts/truetype/dejavu"),
            "DejaVuSans.ttf",
            "DejaVuSans-Bold.ttf",
            "DejaVuSans-Oblique.ttf",
        ),
        (
            Path("C:/Windows/Fonts"),
            "arial.ttf",
            "arialbd.ttf",
            "ariali.ttf",
        ),
    ]

    for font_root, regular_name, bold_name, italic_name in candidates:
        regular_path = font_root / regular_name
        bold_path = font_root / bold_name
        italic_path = font_root / italic_name

        if not (regular_path.is_file() and bold_path.is_file()):
            continue

        REGULAR_FONT = "RoyalTyresSans"
        BOLD_FONT = "RoyalTyresSansBold"

        if REGULAR_FONT not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(REGULAR_FONT, str(regular_path)))
        if BOLD_FONT not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(BOLD_FONT, str(bold_path)))

        if italic_path.is_file():
            ITALIC_FONT = "RoyalTyresSansItalic"
            if ITALIC_FONT not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(ITALIC_FONT, str(italic_path)))

        return


class ReportLabTechnicalReportGenerator:
    def generate(self, report: dict) -> bytes:
        _register_fonts()
        output = BytesIO()
        document = BaseDocTemplate(
            output,
            pagesize=LETTER,
            rightMargin=0.7 * 25.4 * mm,
            leftMargin=0.7 * 25.4 * mm,
            topMargin=60 * mm,
            bottomMargin=36 * mm,
            title=f"Technical Claim Report {report.get('claimReference', '')}",
            author="Royal Tyres",
            subject="Tyre technical inspection claim",
        )
        content_frame = Frame(
            document.leftMargin,
            document.bottomMargin,
            document.width,
            document.height,
            id="report-content",
            showBoundary=0,
        )
        document.addPageTemplates(
            [
                PageTemplate(
                    id="royal-tyres-report",
                    frames=[content_frame],
                    onPage=self._first_page_branding,
                    onPageEnd=self._later_page_branding,
                )
            ]
        )
        styles = self._styles()
        story = [
            Paragraph("Tyre Claim Technical Report", styles["TitleRT"]),
            Spacer(1, 7 * mm),
            self._details_table(report, styles, self._all_fields()),
        ]
        story.extend(self._photos(report, styles))
        document.build(story)
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
                fontSize=11.5,
                leading=14,
                textColor=colors.HexColor("#666666"),
            ),
            "FieldValue": style(
                "FieldValue",
                "BodyText",
                fontName=REGULAR_FONT,
                fontSize=11.5,
                leading=14,
                textColor=colors.HexColor("#666666"),
            ),
            "PhotoLabel": style(
                "PhotoLabel",
                "BodyText",
                fontName=BOLD_FONT,
                fontSize=14,
                leading=17,
                textColor=BLACK,
                alignment=TA_LEFT,
            ),
            "PhotoComment": style(
                "PhotoComment",
                "BodyText",
                fontName=REGULAR_FONT,
                fontSize=10,
                leading=13,
                textColor=BLACK,
                alignment=TA_LEFT,
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
        header_style = ParagraphStyle(
            "OriginalHeader",
            parent=styles["FieldLabel"],
            textColor=colors.white,
            fontName=BOLD_FONT,
            fontSize=11.5,
            leading=14,
        )
        rows = [[Paragraph("Field", header_style), Paragraph("Value", header_style)]]
        rows.extend(
            [
                Paragraph(escape(label), styles["FieldLabel"]),
                Paragraph(
                    escape(self._value(report, key, "N/A")), styles["FieldValue"]
                ),
            ]
            for label, key in fields
        )
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), TEAL),
            ("BOX", (0, 0), (-1, -1), 0.35, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.0 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.0 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
        ]
        table = Table(
            rows,
            colWidths=[79.5 * mm, 100.8 * mm],
            repeatRows=1,
        )
        table.setStyle(TableStyle(commands))
        return table

    def _photos(self, report: dict, styles) -> list:
        pages = []
        for photo in report.get("photos", []):
            try:
                if photo.get("filePath"):
                    image_source = str(photo["filePath"])
                    with PillowImage.open(image_source) as source:
                        width, height = source.size
                else:
                    encoded = str(photo.get("previewUrl", "")).split(",", 1)[-1]
                    image_source = BytesIO(base64.b64decode(encoded))
                    with PillowImage.open(image_source) as source:
                        width, height = source.size
                    image_source.seek(0)
                scale = min((75 * mm) / width, (112 * mm) / height)
                picture = Image(
                    image_source, width=width * scale, height=height * scale
                )
                picture.hAlign = "LEFT"
                name = str(photo.get("label") or photo.get("category", "Photo"))
                comment = str(
                    photo.get("comment")
                    or photo.get("aiComment")
                    or (report.get("photoComments") or {}).get(photo.get("category"))
                    or ""
                ).strip()
                page_items = [
                    PageBreak(),
                    Paragraph(escape(name.upper()), styles["PhotoLabel"]),
                    Spacer(1, 4 * mm),
                    picture,
                ]
                if comment:
                    page_items.extend(
                        [
                            Spacer(1, 3 * mm),
                            Paragraph(escape(comment), styles["PhotoComment"]),
                        ]
                    )
                pages.extend(page_items)
            except Exception:
                continue
        if not pages:
            pages.extend(
                [
                    PageBreak(),
                    Paragraph("NO PHOTOGRAPHS SUPPLIED", styles["Empty"]),
                ]
            )
        return pages

    @staticmethod
    def _open_photo(photo: dict) -> PillowImage.Image:
        if photo.get("filePath"):
            return PillowImage.open(str(photo["filePath"])).convert("RGB")
        encoded = str(photo.get("previewUrl", "")).split(",", 1)[-1]
        return PillowImage.open(BytesIO(base64.b64decode(encoded))).convert("RGB")

    @staticmethod
    def _value(report: dict, key: str, fallback: str = "Not recorded") -> str:
        value = report.get(key)
        if key == "updatedAt" and value not in (None, ""):
            return str(value).strip()[:10]
        if key == "returnedWithRim" and isinstance(value, bool):
            return "Yes" if value else "No"
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

    @classmethod
    def _all_fields(cls) -> list[tuple[str, str]]:
        return [
            ("Claim Reference", "claimReference"),
            ("Date", "updatedAt"),
            ("Claim Type", "internalExternal"),
            ("Salesperson", "salesperson"),
            ("Customer Name", "customerName"),
            ("Customer Invoice No.", "customerInvoiceNumber"),
            ("Category", "category"),
            ("Inspected Location", "inspectedLocation"),
            ("Returned with Rim?", "returnedWithRim"),
            ("Fitted / Loose", "fittedLoose"),
            ("Brand", "brand"),
            ("Rim Size", "rimSize"),
            ("Pattern", "pattern"),
            ("DOT", "dot"),
            ("Serial Number", "serialNumber"),
            ("Branch", "branch"),
            ("Claim Code or Description", "claimCode"),
            ("Remaining Tread Depth [mm]", "remainingTreadDepth"),
            ("Inspected Pressure", "inspectedPressure"),
            ("Tyre Mileage", "tyreMileage"),
            ("Tyre Position", "tyrePosition"),
            ("Nature of Repair", "natureOfRepair"),
            ("Vehicle (make/model)", "vehicleMakeModel"),
            ("Vehicle Mileage", "vehicleMileage"),
            ("Goods transport", "goodsTransported"),
            ("Other relevant info", "notes"),
        ]

    @staticmethod
    def _first_page_branding(canvas, document):
        if canvas.getPageNumber() == 1:
            ReportLabTechnicalReportGenerator._page_branding(canvas, document)

    @staticmethod
    def _later_page_branding(canvas, document):
        if canvas.getPageNumber() > 1:
            ReportLabTechnicalReportGenerator._page_branding(canvas, document)

    @staticmethod
    def _page_branding(canvas, document):
        settings = get_settings()
        asset_root = Path(__file__).resolve().parents[3] / "assets"
        header_path = Path(
            settings.royal_tyres_report_header_path
            or asset_root / "royal-tyres-report-header-print.png"
        )
        footer_path = Path(
            settings.royal_tyres_report_footer_path
            or asset_root / "royal-tyres-report-footer-print.png"
        )
        canvas.saveState()
        side_margin = 0.7 * 25.4 * mm
        available_width = LETTER[0] - 2 * side_margin
        if header_path.is_file():
            with PillowImage.open(header_path) as source:
                header_height = available_width * source.height / source.width
                canvas.drawImage(
                    str(header_path),
                    side_margin,
                    LETTER[1] - 10 * mm - header_height,
                    width=available_width,
                    height=header_height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
        if footer_path.is_file():
            with PillowImage.open(footer_path) as source:
                footer_height = available_width * source.height / source.width
                canvas.drawImage(
                    str(footer_path),
                    side_margin,
                    8 * mm,
                    width=available_width,
                    height=footer_height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
        canvas.restoreState()
