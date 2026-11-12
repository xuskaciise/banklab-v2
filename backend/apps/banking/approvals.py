"""Approval queue (permissions.md section 7). Implemented reason so far: `limit`.

Approve re-validates everything (day, till, balances) and posts the transaction; reject marks
it `rejected` and posts nothing. Maker and checker must be different people.
"""

from django.db import transaction
from django.utils import timezone

from apps.customers import services as customers
from apps.exams.guard import check_write_allowed
from apps.rbac import services as rbac

from . import cheques
from . import txn_core as core
from .models import (
    Approval,
    ApprovalReason,
    ApprovalStatus,
    Transaction,
    TxnStatus,
    TxnType,
)


def _qs():
    return Approval.objects.select_related("requested_by__user", "decided_by__user")


def list_approvals(member, status: str | None = ApprovalStatus.PENDING):
    """Manager's queue (default: pending). Each row gets its `.transaction` attached."""
    customers._read_scope(member, core.PERM_DECIDE)
    qs = _qs().filter(bank_id=member.bank_id, subject_type="transaction")
    if status:
        if status not in ApprovalStatus.values:
            raise core.bad(
                "invalid_filter", f"Status must be one of: {', '.join(ApprovalStatus.values)}"
            )
        qs = qs.filter(status=status)
    rows = list(qs.order_by("created_at"))
    txns = {
        t.pk: t
        for t in Transaction.objects.select_related(
            "account__customer", "counter_account", "cheque"
        ).filter(bank_id=member.bank_id, pk__in=[a.subject_id for a in rows])
    }
    for a in rows:
        a.transaction = txns.get(a.subject_id)
    return rows


def _decide_ctx(member, approval_id):
    session, role = core.require_perm(member, core.PERM_DECIDE)
    approval = (
        Approval.objects.select_for_update(of=("self",))
        .select_related("requested_by")
        .filter(pk=approval_id, bank_id=member.bank_id, subject_type="transaction")
        .first()
    )
    if approval is None:
        raise core.not_found("Approval")
    if approval.status != ApprovalStatus.PENDING or approval.reason != ApprovalReason.LIMIT:
        raise core._conflict("already_decided", "This approval was already decided")
    rbac.assert_maker_checker(approval.requested_by.user_id, member.user_id)
    txn = (
        Transaction.objects.select_for_update(of=("self",))
        .select_related("account__product__gl_account", "counter_account__product__gl_account")
        .filter(pk=approval.subject_id, bank_id=member.bank_id)
        .first()
    )
    if txn is None or txn.status != TxnStatus.PENDING_APPROVAL:
        raise core._conflict("not_pending", "Transaction is no longer pending approval")
    return session, role, approval, txn


def _close(approval, member, status, note):
    approval.status = status
    approval.decided_by = member
    approval.decided_at = timezone.now()
    approval.note = note
    approval.save(update_fields=["status", "decided_by", "decided_at", "note", "updated_at"])


def approve(member, approval_id, note: str = "") -> Approval:
    with transaction.atomic():
        session, role, approval, txn = _decide_ctx(member, approval_id)
        # money posts on the maker's behalf: the maker's exam window must still be open
        check_write_allowed(session, approval.requested_by)
        note = customers._text(note, "Note", 300, required=False)
        day = core.open_day(member.bank_id)
        if txn.business_date != day.date:
            raise core._conflict("other_business_day", "The transaction belongs to a closed day")
        ts = None
        if txn.teller_session_id:
            ts = core.require_open_ts(core.lock_ts(member.bank_id, pk=txn.teller_session_id))
        bank = core.lock_bank(member.bank_id)
        ids = [i for i in (txn.account_id, txn.counter_account_id) if i is not None]
        accounts = core.lock_accounts(bank.pk, ids)
        acc = core.check_account(accounts.get(txn.account_id), txn.currency)
        counter = None
        if txn.counter_account_id:
            counter = core.check_account(
                accounts.get(txn.counter_account_id), txn.currency, "Destination account"
            )
        core.precheck(TxnType(txn.type), acc, counter, txn.amount, txn.currency, ts)
        core.post(txn, bank, acc, counter, ts, member)
        _close(approval, member, ApprovalStatus.APPROVED, note)
        core.audit_txn(
            member,
            role,
            "approval.approved",
            session,
            txn,
            before={"status": TxnStatus.PENDING_APPROVAL},
            after={**core.txn_snapshot(txn), "approval_id": str(approval.pk)},
        )
        return _qs().get(pk=approval.pk)


def reject(member, approval_id, note: str) -> Approval:
    with transaction.atomic():
        session, role, approval, txn = _decide_ctx(member, approval_id)
        note = customers._text(note, "Reason", 300)
        txn.status = TxnStatus.REJECTED
        txn.save(update_fields=["status", "updated_at"])
        cheques.release(txn)
        _close(approval, member, ApprovalStatus.REJECTED, note)
        core.audit_txn(
            member,
            role,
            "approval.rejected",
            session,
            txn,
            before={"status": TxnStatus.PENDING_APPROVAL},
            after={
                "ref_no": txn.ref_no,
                "status": txn.status,
                "note": note,
                "approval_id": str(approval.pk),
            },
        )
        return _qs().get(pk=approval.pk)
