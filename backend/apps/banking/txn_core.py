"""Shared building blocks of the customer-transaction services (transactions.md C1, C2, C4, D1).

Everything here runs inside the caller's `transaction.atomic()`.

Lock order (extends ledger/services.py): lab session -> teller session -> bank row (ref_no
sequence) -> customer accounts by id -> [posting service: business day -> cash positions ->
GL balances]. Money moves only through `ledger.post_entry` / `ledger.reverse_entry`.
"""

from decimal import Decimal

from django.db.models import Max

from apps.audit import services as audit
from apps.ledger import services as ledger
from apps.ledger.models import GLAccount
from apps.ledger.services import LedgerError
from apps.products.models import Account, AccountStatus
from apps.rbac import services as rbac

from . import services as banking
from .models import (
    BusinessDayStatus,
    CashPosition,
    HolderType,
    TellerSession,
    TellerSessionStatus,
    Transaction,
    TxnStatus,
    TxnType,
)

CASH_TYPES = (TxnType.CASH_DEPOSIT, TxnType.CASH_WITHDRAWAL)
PERM = {
    TxnType.CASH_DEPOSIT: "txn.cash_deposit",
    TxnType.CASH_WITHDRAWAL: "txn.cash_withdrawal",
    TxnType.TRANSFER: "txn.transfer",
}
PERM_REVERSE = "txn.reverse"
PERM_READ = "report.operational"
PERM_DECIDE = "approval.decide"
LABEL = {
    TxnType.CASH_DEPOSIT: "Cash deposit",
    TxnType.CASH_WITHDRAWAL: "Cash withdrawal",
    TxnType.TRANSFER: "Transfer",
    TxnType.REVERSAL: "Reversal",
}
_conflict = banking._conflict


def bad(code: str, message: str) -> LedgerError:
    return LedgerError(code, message, status=400)


def not_found(what: str = "Transaction") -> LedgerError:
    return LedgerError("not_found", f"{what} not found", status=404)


def open_day(bank_id):
    from .models import BusinessDay

    day = BusinessDay.objects.filter(bank_id=bank_id, status=BusinessDayStatus.OPEN).first()
    if day is None:
        raise _conflict("day_closed", "The bank has no open business day")
    return day


def lock_bank(bank_id):
    from apps.lab.models import Bank

    return Bank.objects.select_for_update(no_key=True).get(pk=bank_id)


def lock_ts(bank_id, *, pk=None, member=None, business_date=None) -> TellerSession | None:
    qs = TellerSession.objects.select_for_update(of=("self",)).filter(bank_id=bank_id)
    qs = qs.filter(pk=pk) if pk else qs.filter(teller_member=member, business_date=business_date)
    return qs.exclude(status=TellerSessionStatus.CANCELLED).first()


def require_open_ts(ts: TellerSession | None) -> TellerSession:
    if ts is None or ts.status != TellerSessionStatus.OPEN:
        raise _conflict("no_open_till", "An open teller session is required for this transaction")
    return ts


def lock_accounts(bank_id, ids) -> dict:
    rows = (
        Account.objects.select_for_update(of=("self",))
        .select_related("product__gl_account", "customer")
        .filter(bank_id=bank_id, pk__in=ids)
        .order_by("pk")
    )
    return {a.pk: a for a in rows}


def check_account(acc: Account | None, currency: str, what: str = "Account") -> Account:
    if acc is None:
        raise not_found(what)
    if acc.status != AccountStatus.ACTIVE:
        raise _conflict("account_not_active", f"{what} {acc.account_no} is not active")
    if acc.currency != currency:
        raise bad("currency_mismatch", f"{what} {acc.account_no} is in {acc.currency}")
    return acc


def precheck(txn_type, acc, counter, amount: Decimal, currency: str, ts) -> None:
    """Friendly balance checks; the posting service enforces the same rules again."""
    if txn_type in (TxnType.CASH_WITHDRAWAL, TxnType.TRANSFER) and acc.ledger_balance < amount:
        raise _conflict("insufficient_balance", f"Insufficient balance on account {acc.account_no}")
    if txn_type == TxnType.CASH_WITHDRAWAL:
        till = CashPosition.objects.filter(
            bank_id=acc.bank_id,
            holder_type=HolderType.TELLER_SESSION,
            holder_id=ts.pk,
            currency=currency,
        ).first()
        if till is None or till.balance < amount:
            raise _conflict("insufficient_cash", "Insufficient cash in your till")


def _lines(txn_type, acc, counter, amount: Decimal, ts) -> list:
    dep = ledger.LineSpec(acc.product.gl_account, account_id=acc.pk)
    if txn_type == TxnType.TRANSFER:
        dep.debit = amount
        return [
            dep,
            ledger.LineSpec(counter.product.gl_account, credit=amount, account_id=counter.pk),
        ]
    till_gl = GLAccount.objects.get(bank_id=acc.bank_id, system_tag="CASH_TELLER")
    till = {"cash_holder_type": HolderType.TELLER_SESSION.value, "cash_holder_id": ts.pk}
    if txn_type == TxnType.CASH_DEPOSIT:
        dep.credit = amount
        return [ledger.LineSpec(till_gl, debit=amount, **till), dep]
    dep.debit = amount
    return [dep, ledger.LineSpec(till_gl, credit=amount, **till)]


def post(txn: Transaction, bank, acc, counter, ts, actor_member) -> None:
    """Post the C1/C2/C4 entry of `txn` and mark it posted. Accounts must be locked."""
    entry = ledger.post_entry(
        bank,
        _lines(txn.type, acc, counter, txn.amount, ts),
        currency=txn.currency,
        source_type="transaction",
        source_id=txn.pk,
        description=f"{LABEL[txn.type]} {txn.ref_no}",
        business_date=txn.business_date,
        actor_member=actor_member,
    )
    txn.journal_entry = entry
    txn.status = TxnStatus.POSTED
    txn.save(update_fields=["journal_entry", "status", "updated_at"])


def new_txn(bank, day, **fields) -> Transaction:
    """Insert a transaction with the next ref_no of the day. Needs the bank row lock."""
    last = (
        Transaction.objects.filter(bank=bank, business_date=day.date).aggregate(m=Max("seq"))["m"]
        or 0
    )
    seq = last + 1
    prefix = f"B{bank.group_no:02d}" if bank.group_no is not None else "B00"
    return Transaction.objects.create(
        bank=bank,
        seq=seq,
        ref_no=f"{prefix}-{day.date:%Y%m%d}-{seq:04d}",
        business_date=day.date,
        **fields,
    )


def audit_txn(member, role, action, session, txn, *, before=None, after=None) -> None:
    audit.record(
        action,
        actor=member.user,
        actor_role=role,
        entity=("transaction", txn.pk),
        before=before,
        after=after
        if after is not None
        else {"ref_no": txn.ref_no, "status": txn.status, "amount": str(txn.amount)},
        session_id=session.pk,
        bank_id=txn.bank_id,
        institution_id=session.lab_class.institution_id,
    )


def txn_snapshot(txn: Transaction) -> dict:
    return {
        "ref_no": txn.ref_no,
        "type": txn.type,
        "status": txn.status,
        "amount": str(txn.amount),
        "currency": txn.currency,
        "account_no": txn.account.account_no,
        "counter_account_no": txn.counter_account.account_no if txn.counter_account_id else None,
    }


def require_perm(member, code):
    """(locked session, role) after the server-side permission check."""
    session = banking._lock_session(member)
    role = banking._role_of(member)
    if not rbac.role_has_permission(role, code, session=session):
        raise rbac.PermissionDenied("Not allowed")
    return session, role
