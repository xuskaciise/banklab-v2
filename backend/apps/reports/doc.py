"""Neutral report document: one data function builds it, JSON / PDF / XLSX render it."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

ZERO = Decimal("0.00")
KINDS = ("text", "money", "int", "date")


@dataclass
class Column:
    key: str
    label: str
    kind: str = "text"  # text | money | int | date
    weight: float = 1.0  # relative width in the PDF


@dataclass
class Section:
    """A table. Rows are dicts keyed by column key; the optional `style` key marks
    "header" / "subtotal" / "total" rows (bold in PDF and XLSX)."""

    title: str
    columns: list[Column]
    rows: list[dict] = field(default_factory=list)
    currency: str = ""


@dataclass
class Report:
    slug: str
    title: str
    bank_name: str
    branch: str = ""
    period: str = ""
    generated_at: datetime | None = None
    generated_by: str = ""
    summary: list[tuple[str, object, str]] = field(default_factory=list)  # label, value, kind
    sections: list[Section] = field(default_factory=list)
    landscape: bool = False

    @property
    def filename(self) -> str:
        return f"{self.slug}-{(self.generated_at or datetime.now()):%Y%m%d}"


def money(value) -> Decimal:
    return Decimal(value).quantize(ZERO)


def cell_text(value, kind: str) -> str:
    """Display text of a cell (PDF and JSON share the money format `1,234.50` / `1234.50`)."""
    if value is None or value == "":
        return ""
    if kind == "money":
        return f"{money(value):,.2f}"
    if kind == "date" and isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y") if not isinstance(value, datetime) else str(value)
    return str(value)


def _json_value(value, kind: str):
    if value is None:
        return None
    if kind == "money":
        return str(money(value))
    if kind == "date" and isinstance(value, date):
        return value.isoformat()
    if kind == "int":
        return int(value)
    return str(value)


def to_json(report: Report) -> dict:
    return {
        "slug": report.slug,
        "title": report.title,
        "bank_name": report.bank_name,
        "branch": report.branch,
        "period": report.period,
        "generated_at": report.generated_at,
        "generated_by": report.generated_by,
        "summary": [
            {"label": label, "value": _summary_text(value, kind), "kind": kind}
            for label, value, kind in report.summary
        ],
        "sections": [
            {
                "title": s.title,
                "currency": s.currency,
                "columns": [{"key": c.key, "label": c.label, "kind": c.kind} for c in s.columns],
                "rows": [
                    {
                        **{c.key: _json_value(r.get(c.key), c.kind) for c in s.columns},
                        "style": r.get("style", ""),
                    }
                    for r in s.rows
                ],
            }
            for s in report.sections
        ],
    }


def _summary_text(value, kind: str) -> str:
    v = _json_value(value, kind)
    return "" if v is None else str(v)
