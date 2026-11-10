"""Reports API (read-only): JSON, PDF and XLSX of eight reports, from one builder each.

Student routes `/s/{session_id}/reports/<slug>[.pdf|.xlsx]` need the report's permission in
the caller's own bank (`account.statement`, `report.operational`, `report.financial`,
`gl.view`); "own work only" holders see only their own rows. Staff routes
`/sessions/{session_id}/banks/{bank_id}/reports/...` let the instructor (or admin) read any
bank of their session. Reads are not audited (same as receipts and the journal).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from django.http import HttpResponse
from ninja import Query, Router, Schema

from apps.accounts.models import User
from apps.lab import services as lab
from apps.lab.models import Bank
from apps.rbac.context import require_bank_permission

from . import fin, ops, statement, teller
from .ctx import Ctx, branch_of
from .doc import Report, to_json
from .filters import (
    AsOfFilters,
    DailyFilters,
    GlLedgerFilters,
    JournalFilters,
    RangeFilters,
    StatementFilters,
    TellerCashFilters,
)
from .pdf import render_report
from .xlsx import render_xlsx

router = Router(tags=["reports-staff"])
student_router = Router(tags=["reports"])

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ColumnOut(Schema):
    key: str
    label: str
    kind: str  # text | money | int | date


class SectionOut(Schema):
    title: str
    currency: str
    columns: list[ColumnOut]
    # One dict per row keyed by column key; money as "1234.50", dates as ISO strings;
    # `style` is "", "header", "subtotal" or "total".
    rows: list[dict[str, Any]]


class SummaryOut(Schema):
    label: str
    value: str
    kind: str


class ReportOut(Schema):
    slug: str
    title: str
    bank_name: str
    branch: str
    period: str
    generated_at: datetime
    generated_by: str
    summary: list[SummaryOut]
    sections: list[SectionOut]


# (slug, operation name, permission, filter schema, builder)
REPORTS = [
    ("account-statement", "account_statement", "account.statement", StatementFilters,
     statement.account_statement),
    ("teller-cash", "teller_cash", "report.operational", TellerCashFilters, teller.teller_cash),
    ("branch-daily", "branch_daily", "report.operational", DailyFilters, ops.branch_daily),
    ("transaction-journal", "journal", "report.operational", JournalFilters, ops.journal),
    ("trial-balance", "trial_balance", "report.financial", AsOfFilters, fin.trial_balance),
    ("balance-sheet", "balance_sheet", "report.financial", AsOfFilters, fin.balance_sheet),
    ("income-statement", "income_statement", "report.financial", RangeFilters,
     fin.income_statement),
    ("gl-ledger", "gl_ledger", "gl.view", GlLedgerFilters, statement.gl_ledger),
]


def _emit(report: Report, fmt: str, bank):
    if fmt == "json":
        return to_json(report)
    if fmt == "pdf":
        resp = HttpResponse(render_report(report, branch_of(bank)), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{report.filename}.pdf"'
        return resp
    resp = HttpResponse(render_xlsx(report), content_type=XLSX_TYPE)
    resp["Content-Disposition"] = f'attachment; filename="{report.filename}.xlsx"'
    return resp


def _staff_bank(request, session_id: UUID, bank_id: UUID) -> Bank:
    user: User = request.user
    session = lab.get_session(user, session_id)
    bank = Bank.objects.filter(pk=bank_id, session=session).first()
    if bank is None:
        raise lab.NotFound("Bank not found in this session")
    return bank


def _student_view(perm, filt, build, fmt):
    @require_bank_permission(perm)
    def view(request, session_id: UUID, filters: Query[filt]):
        ctx = Ctx(
            bank=request.bank,
            user=request.user,
            member=request.session_member,
            scope=request.permission_scope,
        )
        return _emit(build(ctx, **filters.dict()), fmt, request.bank)

    return view


def _staff_view(filt, build, fmt):
    def view(request, session_id: UUID, bank_id: UUID, filters: Query[filt]):
        bank = _staff_bank(request, session_id, bank_id)
        return _emit(build(Ctx(bank=bank, user=request.user), **filters.dict()), fmt, bank)

    return view


def _register() -> None:
    for slug, name, perm, filt, build in REPORTS:
        for fmt in ("json", "pdf", "xlsx"):
            suffix = "" if fmt == "json" else f".{fmt}"
            op = f"report_{name}" + ("" if fmt == "json" else f"_{fmt}")
            kw = {"response": ReportOut} if fmt == "json" else {}
            student_router.get(
                f"/s/{{session_id}}/reports/{slug}{suffix}", operation_id=op, **kw
            )(_student_view(perm, filt, build, fmt))
            router.get(
                f"/sessions/{{session_id}}/banks/{{bank_id}}/reports/{slug}{suffix}",
                operation_id=f"report_staff_{name}" + ("" if fmt == "json" else f"_{fmt}"),
                **kw,
            )(_staff_view(filt, build, fmt))


_register()
