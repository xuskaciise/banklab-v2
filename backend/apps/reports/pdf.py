"""PDF rendering shared by the receipt and the reports (reportlab, A4).

`PRIMARY` ... `SOFT`, `draw_watermark` and `draw_header` are the branding pieces of the
receipt; `render_report` lays a `Report` out as multi-page tables with a repeated column
header and "Page x of y" in the footer.
"""

from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .doc import Report, cell_text

# Colours from docs/design/theme.md (PDF cannot read the web CSS tokens).
PRIMARY = colors.HexColor("#1E3A8A")  # bank-primary
NAVY = colors.HexColor("#0F2942")  # bank-navy
SUCCESS = colors.HexColor("#047857")  # fin-success-dark
DANGER = colors.HexColor("#B91C1C")  # fin-danger
MUTED = colors.HexColor("#64748B")  # text-muted
LINE = colors.HexColor("#E2E8F0")  # border
SOFT = colors.HexColor("#F1F5F9")  # surface

HEADER_BLOCK = 36 * mm  # top margin of report pages (brand header sits inside it)
FOOTER_BLOCK = 20 * mm
SIDE = 15 * mm
STRONG = ("header", "subtotal", "total")
NUMERIC = ("money", "int")


def draw_watermark(pdf, width, height):
    pdf.saveState()
    pdf.setFillColor(colors.Color(0.5, 0.5, 0.5, alpha=0.08))
    pdf.setFont("Helvetica-Bold", 110)
    pdf.translate(width / 2, height / 2)
    pdf.rotate(35)
    pdf.drawCentredString(0, -30, "TRAINING")
    pdf.restoreState()


def draw_header(pdf, bank_name, branch, width, height, left, right):
    """Bank logo placeholder, name, branch and the primary rule; returns the y below it."""
    y = height - 22 * mm
    pdf.setFillColor(PRIMARY)  # logo placeholder: rounded square with initials
    pdf.roundRect(left, y - 4 * mm, 14 * mm, 14 * mm, 3 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 13)
    initials = "".join(w[0] for w in bank_name.split()[:2]).upper()
    pdf.drawCentredString(left + 7 * mm, y + 0.5 * mm, initials)
    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(left + 18 * mm, y + 3 * mm, bank_name)
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(MUTED)
    pdf.drawString(left + 18 * mm, y - 2.5 * mm, "Training bank - not a real bank")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(NAVY)
    if branch:
        pdf.drawRightString(right, y + 3 * mm, f"{branch.name} ({branch.code})")
        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(MUTED)
        pdf.drawRightString(right, y - 2.5 * mm, branch.address or "No address on file")
    pdf.setFillColor(PRIMARY)
    pdf.rect(left, y - 9 * mm, right - left, 1.6 * mm, fill=1, stroke=0)
    return y - 20 * mm


class _NumberedCanvas(canvas.Canvas):
    """Defers page output so the footer can say "Page x of y"."""

    footer_text = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._footer(total)
            super().showPage()
        super().save()

    def _footer(self, total):
        left, right = SIDE, self._pagesize[0] - SIDE
        self.setStrokeColor(LINE)
        self.line(left, 16 * mm, right, 16 * mm)
        self.setFont("Helvetica", 8)
        self.setFillColor(MUTED)
        self.drawString(left, 11 * mm, self.footer_text)
        self.drawRightString(right, 11 * mm, f"Page {self._pageNumber} of {total}")
        self.drawString(
            left, 7 * mm, "Training bank - not a real bank. Not valid as a financial document."
        )


def _para(text, *, bold=False, right=False, color=NAVY) -> Paragraph:
    style = ParagraphStyle(
        "c",
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=8,
        leading=10,
        textColor=color,
        alignment=2 if right else 0,
    )
    return Paragraph(escape(text), style)


def _col_widths(section, width) -> list[float]:
    """Weight-based widths, but numeric columns are never narrower than their widest value,
    so large amounts (e.g. 5,000,000,000.00) stay on one line."""
    cols = section.columns
    need = {}
    for i, c in enumerate(cols):
        if c.kind in NUMERIC:
            texts = [c.label] + [cell_text(r.get(c.key), c.kind) for r in section.rows]
            need[i] = max(stringWidth(t, "Helvetica-Bold", 8) for t in texts) + 14
    fixed = sum(need.values())
    rest = [i for i in range(len(cols)) if i not in need]
    rest_w = sum(cols[i].weight for i in rest) or 1
    free = max(width - fixed, 0)
    widths = [need.get(i, free * cols[i].weight / rest_w) for i in range(len(cols))]
    scale = width / sum(widths)
    return [w * scale for w in widths]


def _section_table(section, width) -> Table:
    cols = section.columns
    widths = _col_widths(section, width)
    data = [[_para(c.label, bold=True, right=c.kind in NUMERIC, color=colors.white) for c in cols]]
    styles = []
    for i, row in enumerate(section.rows, start=1):
        strong = row.get("style") in STRONG
        data.append(
            [
                _para(cell_text(row.get(c.key), c.kind), bold=strong, right=c.kind in NUMERIC)
                for c in cols
            ]
        )
        if strong:
            styles.append(("BACKGROUND", (0, i), (-1, i), SOFT))
        if row.get("style") in ("subtotal", "total"):
            styles.append(("LINEABOVE", (0, i), (-1, i), 0.6, NAVY))
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                *styles,
            ]
        )
    )
    return table


def render_report(report: Report, branch=None) -> bytes:
    """`branch` is the bank's main `Branch` (or None) for the page header."""
    size = landscape(A4) if report.landscape else A4
    width, height = size
    left, right = SIDE, width - SIDE
    when = timezone.localtime(report.generated_at or timezone.now())
    by = f" by {report.generated_by}" if report.generated_by else ""
    footer = f"{report.title}  |  Generated {when:%d %b %Y, %I:%M %p}{by}"

    class Canvas(_NumberedCanvas):
        footer_text = footer

    def on_page(pdf, _doc):
        draw_watermark(pdf, width, height)
        draw_header(pdf, report.bank_name, branch, width, height, left, right)

    buf = BytesIO()
    doc = BaseDocTemplate(
        buf,
        pagesize=size,
        title=report.title,
        author=report.bank_name,
        leftMargin=left,
        rightMargin=SIDE,
        topMargin=HEADER_BLOCK,
        bottomMargin=FOOTER_BLOCK,
    )
    frame = Frame(
        left,
        FOOTER_BLOCK,
        right - left,
        height - HEADER_BLOCK - FOOTER_BLOCK,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=on_page)])
    title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=NAVY)
    sub = ParagraphStyle("s", fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED)
    sec = ParagraphStyle("g", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=PRIMARY)
    story = [Paragraph(escape(report.title.upper()), title)]
    if report.period:
        story.append(Paragraph(escape(report.period), sub))
    story.append(Paragraph(f"Generated {when:%d %b %Y, %I:%M %p}{escape(by)}", sub))
    story.append(Spacer(1, 3 * mm))
    for label, value, kind in report.summary:
        story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(cell_text(value, kind))}", sub))
    if report.summary:
        story.append(Spacer(1, 3 * mm))
    for section in report.sections:
        story.append(Paragraph(escape(section.title), sec))
        story.append(Spacer(1, 1.5 * mm))
        if section.rows:
            story.append(_section_table(section, right - left))
        else:
            story.append(Paragraph("No data for this selection.", sub))
        story.append(Spacer(1, 6 * mm))
    doc.build(story, canvasmaker=Canvas)
    return buf.getvalue()
