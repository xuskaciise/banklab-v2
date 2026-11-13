"""Read-only ledger API: chart of accounts with balances and the journal.

Student routes need `gl.view` in the caller's own bank; staff routes let the instructor
(or admin) of the class read any bank of their session.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from ninja import Query, Router, Schema
from ninja.pagination import PageNumberPagination, paginate

from apps.accounts.models import User
from apps.lab import services as lab
from apps.lab.models import Bank
from apps.rbac.context import require_bank_permission

from . import services

router = Router(tags=["ledger"])
student_router = Router(tags=["ledger-student"])


class BalanceOut(Schema):
    currency: str
    balance: Decimal


class GLAccountOut(Schema):
    id: UUID
    code: str
    name: str
    type: str
    parent_id: UUID | None
    postable: bool
    system_tag: str
    is_active: bool
    balances: list[BalanceOut]


class JournalLineOut(Schema):
    id: int
    gl_code: str
    gl_name: str
    currency: str
    debit: Decimal
    credit: Decimal

    @staticmethod
    def resolve_gl_code(obj):
        return obj.gl_account.code

    @staticmethod
    def resolve_gl_name(obj):
        return obj.gl_account.name


class JournalEntryOut(Schema):
    id: UUID
    entry_no: int
    business_date: date
    currency: str
    source_type: str
    source_id: UUID | None
    description: str
    reversal_of_id: UUID | None
    posted_by_id: UUID | None
    posted_at: datetime


class JournalEntryDetailOut(JournalEntryOut):
    lines: list[JournalLineOut]


class JournalFilters(Schema):
    currency: str | None = None
    date_from: date | None = None
    date_to: date | None = None


FILTERS = Query(...)


class JournalPagination(PageNumberPagination):
    page_size = 50


def _staff_bank(request, session_id: UUID, bank_id: UUID) -> Bank:
    user: User = request.user
    session = lab.get_session(user, session_id)
    bank = Bank.objects.filter(pk=bank_id, session=session).first()
    if bank is None:
        raise lab.NotFound("Bank not found in this session")
    return bank


# ------------------------------------------------------------------ student (bank role)


def _own(request):
    """The acting member when the viewer may only see their own work, else None."""
    return request.session_member if request.permission_scope == "own" else None


@student_router.get(
    "/s/{session_id}/gl/accounts", response=list[GLAccountOut], operation_id="ledger_gl_accounts"
)
@require_bank_permission("gl.view")
def gl_accounts(request, session_id: UUID):
    return services.gl_tree(request.bank, with_balances=request.permission_scope != "own")


@student_router.get(
    "/s/{session_id}/journal", response=list[JournalEntryOut], operation_id="ledger_journal_list"
)
@require_bank_permission("gl.view")
@paginate(JournalPagination, page_size=50)
def journal_list(request, session_id: UUID, filters: JournalFilters = FILTERS):
    return services.list_entries(
        request.bank,
        own_member=_own(request),
        currency=filters.currency,
        date_from=filters.date_from,
        date_to=filters.date_to,
    )


@student_router.get(
    "/s/{session_id}/journal/{entry_id}",
    response=JournalEntryDetailOut,
    operation_id="ledger_journal_get",
)
@require_bank_permission("gl.view")
def journal_get(request, session_id: UUID, entry_id: UUID):
    return services.get_entry(request.bank, entry_id, own_member=_own(request))


# ------------------------------------------------------------------ staff (instructor/admin)


@router.get(
    "/sessions/{session_id}/banks/{bank_id}/gl/accounts",
    response=list[GLAccountOut],
    operation_id="ledger_staff_gl_accounts",
)
def staff_gl_accounts(request, session_id: UUID, bank_id: UUID):
    return services.gl_tree(_staff_bank(request, session_id, bank_id))


@router.get(
    "/sessions/{session_id}/banks/{bank_id}/journal",
    response=list[JournalEntryOut],
    operation_id="ledger_staff_journal_list",
)
@paginate(JournalPagination, page_size=50)
def staff_journal_list(request, session_id: UUID, bank_id: UUID, filters: JournalFilters = FILTERS):
    return services.list_entries(
        _staff_bank(request, session_id, bank_id),
        currency=filters.currency,
        date_from=filters.date_from,
        date_to=filters.date_to,
    )


@router.get(
    "/sessions/{session_id}/banks/{bank_id}/journal/{entry_id}",
    response=JournalEntryDetailOut,
    operation_id="ledger_staff_journal_get",
)
def staff_journal_get(request, session_id: UUID, bank_id: UUID, entry_id: UUID):
    return services.get_entry(_staff_bank(request, session_id, bank_id), entry_id)
