"""Customer transactions + approvals API (student routes).

Every route needs a bank role holding the matching permission (`txn.cash_deposit`,
`txn.cash_withdrawal`, `txn.transfer`, `txn.reverse`, `approval.decide`; reads use
`report.operational`); the services re-check role, limits, balances and the archived guard.
A posting above the actor's limit answers 200 with `status = pending_approval`.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.http import HttpResponse
from ninja import Query, Router, Schema
from ninja.pagination import PageNumberPagination, paginate

from apps.rbac.context import require_bank_permission

from . import approvals, receipts, transactions
from .models import Approval

txn_router = Router(tags=["transactions-student"])


class TxnPagination(PageNumberPagination):
    page_size = 25


def _name(member) -> str | None:
    return (member.user.full_name or member.user.username) if member else None


class PartyIn(Schema):
    party_name: str
    party_id_no: str
    party_phone: str


class DepositIn(PartyIn):
    account_id: UUID
    amount: Decimal
    currency: str
    narration: str = ""


class WithdrawalIn(DepositIn):
    pass


class TransferIn(Schema):
    from_account_id: UUID
    to_account_id: UUID
    amount: Decimal
    currency: str
    narration: str = ""


class ReverseIn(Schema):
    reason: str = ""


class DecisionIn(Schema):
    note: str = ""


class TxnFilters(Schema):
    status: str | None = None
    type: str | None = None
    account_id: UUID | None = None
    business_date: date | None = None


class TransactionOut(Schema):
    id: UUID
    ref_no: str
    type: str
    status: str
    amount: Decimal
    currency: str
    account_id: UUID
    account_no: int
    customer_name: str
    counter_account_id: UUID | None = None
    counter_account_no: int | None = None
    counter_customer_name: str | None = None
    teller_session_id: UUID | None = None
    party_name: str
    party_id_no: str
    party_phone: str
    narration: str
    business_date: date
    created_by_id: UUID
    created_by_name: str
    journal_entry_id: UUID | None = None
    journal_entry_no: int | None = None
    reversal_of_id: UUID | None = None
    reversal_of_ref_no: str | None = None
    approval_id: UUID | None = None
    approval_status: str | None = None
    approval_note: str | None = None
    created_at: datetime

    @staticmethod
    def resolve_account_no(obj):
        return obj.account.account_no

    @staticmethod
    def resolve_customer_name(obj):
        return obj.account.customer.display_name

    @staticmethod
    def resolve_counter_account_no(obj):
        return obj.counter_account.account_no if obj.counter_account_id else None

    @staticmethod
    def resolve_counter_customer_name(obj):
        return obj.counter_account.customer.display_name if obj.counter_account_id else None

    @staticmethod
    def resolve_created_by_name(obj):
        return _name(obj.created_by)

    @staticmethod
    def resolve_journal_entry_no(obj):
        return obj.journal_entry.entry_no if obj.journal_entry_id else None

    @staticmethod
    def resolve_reversal_of_ref_no(obj):
        return obj.reversal_of.ref_no if obj.reversal_of_id else None

    @staticmethod
    def _approval(obj):
        if not hasattr(obj, "_approval_row"):
            obj._approval_row = (
                Approval.objects.filter(
                    bank_id=obj.bank_id, subject_type="transaction", subject_id=obj.pk
                )
                .order_by("-created_at")
                .first()
            )
        return obj._approval_row

    @staticmethod
    def resolve_approval_id(obj):
        a = TransactionOut._approval(obj)
        return a.pk if a else None

    @staticmethod
    def resolve_approval_status(obj):
        a = TransactionOut._approval(obj)
        return a.status if a else None

    @staticmethod
    def resolve_approval_note(obj):
        a = TransactionOut._approval(obj)
        return (a.note or None) if a else None


class ApprovalTxnOut(Schema):
    id: UUID
    ref_no: str
    type: str
    status: str
    amount: Decimal
    currency: str
    account_no: int
    customer_name: str
    counter_account_no: int | None = None
    party_name: str
    narration: str
    business_date: date

    @staticmethod
    def resolve_account_no(obj):
        return obj.account.account_no

    @staticmethod
    def resolve_customer_name(obj):
        return obj.account.customer.display_name

    @staticmethod
    def resolve_counter_account_no(obj):
        return obj.counter_account.account_no if obj.counter_account_id else None


class ApprovalOut(Schema):
    id: UUID
    reason: str
    status: str
    subject_type: str
    subject_id: UUID
    requested_by_id: UUID
    requested_by_name: str
    decided_by_id: UUID | None = None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    note: str
    created_at: datetime
    transaction: ApprovalTxnOut | None = None

    @staticmethod
    def resolve_requested_by_name(obj):
        return _name(obj.requested_by)

    @staticmethod
    def resolve_decided_by_name(obj):
        return _name(obj.decided_by)

    @staticmethod
    def resolve_transaction(obj):
        return getattr(obj, "transaction", None)


_T = "/s/{session_id}/transactions"
_A = "/s/{session_id}/approvals"


@txn_router.post(_T + "/deposit", response=TransactionOut, operation_id="txn_deposit")
@require_bank_permission("txn.cash_deposit")
def txn_deposit(request, session_id: UUID, payload: DepositIn):
    return transactions.deposit(request.session_member, **payload.dict())


@txn_router.post(_T + "/withdrawal", response=TransactionOut, operation_id="txn_withdrawal")
@require_bank_permission("txn.cash_withdrawal")
def txn_withdrawal(request, session_id: UUID, payload: WithdrawalIn):
    return transactions.withdraw(request.session_member, **payload.dict())


@txn_router.post(_T + "/transfer", response=TransactionOut, operation_id="txn_transfer")
@require_bank_permission("txn.transfer")
def txn_transfer(request, session_id: UUID, payload: TransferIn):
    return transactions.transfer(request.session_member, **payload.dict())


@txn_router.get(_T, response=list[TransactionOut], operation_id="txn_list")
@require_bank_permission("report.operational")
@paginate(TxnPagination)
def txn_list(request, session_id: UUID, filters: Query[TxnFilters]):
    return transactions.list_transactions(request.session_member, **filters.dict())


@txn_router.get(_T + "/{txn_id}", response=TransactionOut, operation_id="txn_get")
@require_bank_permission("report.operational")
def txn_get(request, session_id: UUID, txn_id: UUID):
    return transactions.get_transaction(request.session_member, txn_id)


@txn_router.post(_T + "/{txn_id}/reverse", response=TransactionOut, operation_id="txn_reverse")
@require_bank_permission("txn.reverse")
def txn_reverse(request, session_id: UUID, txn_id: UUID, payload: ReverseIn):
    return transactions.reverse(request.session_member, txn_id, payload.reason)


@txn_router.get(_T + "/{txn_id}/receipt.pdf", operation_id="txn_receipt")
@require_bank_permission("report.operational")
def txn_receipt(request, session_id: UUID, txn_id: UUID):
    txn = transactions.get_transaction(request.session_member, txn_id)
    resp = HttpResponse(receipts.render_receipt(txn), content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="receipt-{txn.ref_no}.pdf"'
    return resp


@txn_router.get(_A, response=list[ApprovalOut], operation_id="approvals_list")
@require_bank_permission("approval.decide")
def approvals_list(request, session_id: UUID, status: str | None = "pending"):
    return approvals.list_approvals(request.session_member, status or None)


@txn_router.post(
    _A + "/{approval_id}/approve", response=ApprovalOut, operation_id="approvals_approve"
)
@require_bank_permission("approval.decide")
def approvals_approve(request, session_id: UUID, approval_id: UUID, payload: DecisionIn):
    return approvals.approve(request.session_member, approval_id, payload.note)


@txn_router.post(
    _A + "/{approval_id}/reject", response=ApprovalOut, operation_id="approvals_reject"
)
@require_bank_permission("approval.decide")
def approvals_reject(request, session_id: UUID, approval_id: UUID, payload: DecisionIn):
    return approvals.reject(request.session_member, approval_id, payload.note)
