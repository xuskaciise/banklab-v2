"""Excel export of a `Report` (openpyxl): title rows, bold header, money format, frozen header."""

from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .doc import Report, money

MONEY_FORMAT = "#,##0.00"
HEAD_FILL = PatternFill("solid", fgColor="1E3A8A")
STRONG = ("header", "subtotal", "total")


def safe(v):
    """Neutralise spreadsheet formulas in user-controlled text (CSV/XLSX injection)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", chr(9), chr(13)):
        return "'" + v
    return v


def _value(row, col):
    v = row.get(col.key)
    if col.kind == "money" and v not in (None, ""):
        return money(v)
    if isinstance(v, datetime) and v.tzinfo is not None:
        return v.replace(tzinfo=None)
    return safe(v)


def _write_section(ws, section, widths) -> int:
    """Append one table; returns the row number of its header."""
    ws.append([])
    ws.append([section.title])
    ws.cell(ws.max_row, 1).font = Font(bold=True, size=11)
    cols = section.columns
    header = [c.label for c in cols] + (["Currency"] if section.currency else [])
    ws.append(header)
    header_row = ws.max_row
    for i, label in enumerate(header, start=1):
        cell = ws.cell(header_row, i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        if i <= len(cols) and cols[i - 1].kind in ("money", "int"):
            cell.alignment = Alignment(horizontal="right")
        widths[i] = max(widths.get(i, 10), min(len(label) + 4, 50))
    for row in section.rows:
        values = [_value(row, c) for c in cols]
        if section.currency:
            values.append(section.currency)
        ws.append(values)
        r = ws.max_row
        for i, c in enumerate(cols, start=1):
            cell = ws.cell(r, i)
            if c.kind == "money":
                cell.number_format = MONEY_FORMAT
            elif c.kind == "date" and isinstance(cell.value, date):
                cell.number_format = "yyyy-mm-dd"
            if row.get("style") in STRONG:
                cell.font = Font(bold=True)
        for i, v in enumerate(values, start=1):
            widths[i] = max(widths.get(i, 10), min(len(str(v if v is not None else "")) + 2, 50))
    return header_row


def render_xlsx(report: Report) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = report.slug[:31]
    ws.append([report.bank_name])
    ws.append([report.title])
    ws.append([report.period] if report.period else [])
    stamp = report.generated_at.strftime("%Y-%m-%d %H:%M") if report.generated_at else ""
    by = f" by {report.generated_by}" if report.generated_by else ""
    ws.append([f"Generated {stamp}{by}"])
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"].font = Font(bold=True, size=12)
    for label, value, kind in report.summary:
        shown = money(value) if kind == "money" and value not in (None, "") else safe(value)
        ws.append([label, shown])
        ws.cell(ws.max_row, 1).font = Font(bold=True)
        if kind == "money":
            ws.cell(ws.max_row, 2).number_format = MONEY_FORMAT
    widths: dict[int, int] = {}
    first_header = None
    for section in report.sections:
        header_row = _write_section(ws, section, widths)
        first_header = first_header or header_row
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = w
    if first_header:
        ws.freeze_panes = ws.cell(first_header + 1, 1)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
