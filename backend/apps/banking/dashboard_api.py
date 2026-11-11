"""Student dashboard + Dr/Cr learning panel routes.

`GET /s/{session_id}/dashboard` needs a bank role; sections are filtered by permission.
The learning panel needs `report.operational` (same visibility as `txn_get`), not `gl.view`.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from ninja import Router, Schema
from ninja.errors import HttpError

from apps.rbac import context as rbac_context
from apps.rbac.context import require_bank_permission

from . import dashboard, transactions

dashboard_router = Router(tags=["dashboard"])


class AmountOut(Schema):
    currency: str
    amount: Decimal


class TellerSessionBriefOut(Schema):
    id: UUID
    till_code: str
    business_date: date
    opened_at: datetime | None = None


class TellerTodayOut(Schema):
    count: int
    pending_count: int
    total_in: list[AmountOut]
    total_out: list[AmountOut]


class TellerDashboardOut(Schema):
    teller_session: TellerSessionBriefOut | None = None
    till_status: str  # none | pending_open | open | closing | closed
    till_cash: list[AmountOut]
    today: TellerTodayOut
    pending_approvals: int


class BranchCashOut(Schema):
    currency: str
    vault: Decimal
    tills: Decimal
    total: Decimal


class BusinessDayBriefOut(Schema):
    date: date
    status: str


class PendingApprovalCountOut(Schema):
    type: str  # transaction_limit | till_open | till_close | cash_transfer
    count: int


class ManagerDashboardOut(Schema):
    business_day: BusinessDayBriefOut | None = None
    cash: list[BranchCashOut] | None = None  # needs vault.view
    open_tills: int | None = None
    closing_tills: int | None = None
    pending_approvals: list[PendingApprovalCountOut]


class DashboardOut(Schema):
    role: str
    business_date: date | None = None
    teller: TellerDashboardOut | None = None
    manager: ManagerDashboardOut | None = None


class LearningLineOut(Schema):
    gl_code: str
    gl_name: str
    debit: Decimal
    credit: Decimal
    currency: str


class LearningOut(Schema):
    transaction_id: UUID
    ref_no: str
    type: str
    status: str
    currency: str
    journal_entry_no: int | None = None
    lines: list[LearningLineOut]
    total_debit: Decimal
    total_credit: Decimal
    explanation: str
    note: str | None = None


@dashboard_router.get(
    "/s/{session_id}/dashboard", response=DashboardOut, operation_id="dashboard_get"
)
def dashboard_get(request, session_id: UUID):
    ctx = rbac_context.resolve_bank_context(request, session_id)
    return dashboard.dashboard(ctx.member, ctx.session, ctx.role)


@dashboard_router.get(
    "/s/{session_id}/transactions/{txn_id}/learning",
    response=LearningOut,
    operation_id="txn_learning",
)
@require_bank_permission("report.operational")
def txn_learning(request, session_id: UUID, txn_id: UUID):
    session = request.lab_session
    if session.kind == "exam" or not session.learning_panel:
        raise HttpError(403, "The learning panel is not available in this session")
    txn = transactions.get_transaction(request.session_member, txn_id)
    return dashboard.learning_view(request.bank, txn)
