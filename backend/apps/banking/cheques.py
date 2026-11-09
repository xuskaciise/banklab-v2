"""Chequebooks and cheques (transactions.md C3, F): issue a series, stop payment, reads.

Issue and stop are non-posting operations (no journal entry) but are permission-checked,
audited and run in one transaction. The cheque withdrawal itself is created through
`transactions.cheque_withdraw`; the helpers `reserve`, `release` and `mark_paid` keep the cheque
in step with that transaction. Lock order: session -> bank row -> account -> cheque.
"""

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit import services as audit
from apps.customers import services as customers
from apps.products import services as products
from apps.products.models import Account, AccountStatus

from . import txn_core as core
from .models import Cheque, Chequebook, ChequeStatus

PERM_ISSUE = "chequebook.issue"
PERM_STOP = "cheque.stop"
LEAVES = (10, 25, 50)
FIRST_NUMBER = 100001


def _audit(member, role, action, session, entity, *, before=None, after=None):
    audit.record(
        action,
        actor=member.user,
        actor_role=role,
        entity=entity,
        before=before,
        after=after,
        session_id=session.pk,
        bank_id=member.bank_id,
        institution_id=session.lab_class.institution_id,
    )


def issue_chequebook(member, account_id, leaves) -> Chequebook:
    with transaction.atomic():
        session, role = core.require_perm(member, PERM_ISSUE)
        if leaves not in LEAVES:
            raise core.bad(
                "invalid_leaves", f"Leaves must be one of: {', '.join(map(str, LEAVES))}"
            )
        bank = core.lock_bank(member.bank_id)  # serialises number allocation
        _, _, scope = customers._read_scope(member, PERM_ISSUE)
        visible = products._visible(member, scope).filter(pk=account_id)
        acc = (
            Account.objects.select_for_update(of=("self",))
            .select_related("product", "customer")
            .filter(pk__in=visible.values("pk"))
            .first()
        )
        if acc is None:
            raise core.not_found("Account")
        if acc.status != AccountStatus.ACTIVE:
            raise core._conflict("account_not_active", f"Account {acc.account_no} is not active")
        if not acc.product.allows_cheques:
            raise core.bad("cheques_not_allowed", "This account's product does not allow cheques")
        last = Cheque.objects.filter(bank=bank).aggregate(m=Max("number"))["m"]
        first = (last + 1) if last else FIRST_NUMBER
        book = Chequebook.objects.create(
            bank=bank,
            account=acc,
            first_no=first,
            last_no=first + leaves - 1,
            leaves=leaves,
            issued_by=member,
            issued_at=timezone.now(),
        )
        Cheque.objects.bulk_create(
            Cheque(bank=bank, chequebook=book, number=n) for n in range(first, first + leaves)
        )
        _audit(
            member,
            role,
            "chequebook.issued",
            session,
            ("chequebook", book.pk),
            after={
                "account_no": acc.account_no,
                "first_no": first,
                "last_no": book.last_no,
                "leaves": leaves,
            },
        )
        return book


def stop_cheque(member, cheque_id, reason: str) -> Cheque:
    with transaction.atomic():
        session, role = core.require_perm(member, PERM_STOP)
        reason = customers._text(reason, "Reason", 200)
        cheque = (
            Cheque.objects.select_for_update(of=("self",))
            .select_related("chequebook__account")
            .filter(pk=cheque_id, bank_id=member.bank_id)
            .first()
        )
        if cheque is None:
            raise core.not_found("Cheque")
        _, _, scope = customers._read_scope(member, PERM_STOP)
        if not products._visible(member, scope).filter(pk=cheque.chequebook.account_id).exists():
            raise core.not_found("Cheque")
        if cheque.status != ChequeStatus.ISSUED:
            raise core._conflict("cheque_not_issued", f"Cheque is already {cheque.status}")
        if cheque.transaction_id:
            raise core._conflict("cheque_in_use", "Cheque has a withdrawal waiting for approval")
        cheque.status = ChequeStatus.STOPPED
        cheque.stopped_by = member
        cheque.stopped_at = timezone.now()
        cheque.stop_reason = reason
        cheque.save(
            update_fields=["status", "stopped_by", "stopped_at", "stop_reason", "updated_at"]
        )
        _audit(
            member,
            role,
            "cheque.stopped",
            session,
            ("cheque", cheque.pk),
            before={"status": ChequeStatus.ISSUED},
            after={"number": cheque.number, "status": cheque.status, "reason": reason},
        )
        return cheque


# --------------------------------------------------------------------------- withdrawal hooks


def reserve(bank_id, account, cheque_no) -> Cheque:
    """Lock and validate the cheque of a withdrawal on `account` (must be locked already)."""
    if cheque_no is None:
        raise core.bad("cheque_required", "Cheque number is required")
    cheque = (
        Cheque.objects.select_for_update(of=("self",))
        .select_related("chequebook")
        .filter(bank_id=bank_id, number=cheque_no)
        .first()
    )
    if cheque is None:
        raise core.not_found("Cheque")
    if cheque.chequebook.account_id != account.pk:
        raise core.bad("cheque_wrong_account", "Cheque does not belong to this account")
    if cheque.status == ChequeStatus.PAID or cheque.transaction_id:
        raise core._conflict("cheque_already_paid", "Cheque was already presented")
    if cheque.status == ChequeStatus.STOPPED:
        raise core._conflict("cheque_stopped", "Payment on this cheque was stopped")
    return cheque


def attach(cheque: Cheque, txn) -> None:
    cheque.transaction = txn
    cheque.save(update_fields=["transaction", "updated_at"])


def mark_paid(txn) -> None:
    """Called when a cheque withdrawal posts (directly or on approval)."""
    if txn.cheque_id:
        Cheque.objects.filter(pk=txn.cheque_id).update(
            status=ChequeStatus.PAID, transaction=txn, updated_at=timezone.now()
        )


def release(txn) -> None:
    """Rejected or reversed withdrawal: the cheque can be presented again."""
    if txn.cheque_id:
        Cheque.objects.select_for_update(of=("self",)).filter(pk=txn.cheque_id).update(
            status=ChequeStatus.ISSUED, transaction=None, updated_at=timezone.now()
        )


# --------------------------------------------------------------------------- reads


def list_chequebooks(member, account_id):
    products.get_account(member, account_id)  # visibility + account.view
    return (
        Chequebook.objects.filter(bank_id=member.bank_id, account_id=account_id)
        .select_related("issued_by__user")
        .order_by("-issued_at")
    )


def list_cheques(member, account_id, status=None):
    products.get_account(member, account_id)
    qs = Cheque.objects.filter(bank_id=member.bank_id, chequebook__account_id=account_id)
    if status:
        if status not in ChequeStatus.values:
            raise core.bad(
                "invalid_filter", f"Status must be one of: {', '.join(ChequeStatus.values)}"
            )
        qs = qs.filter(status=status)
    return qs.select_related("chequebook").order_by("number")
