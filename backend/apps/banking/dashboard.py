"""Role dashboards (student) and the Dr/Cr learning panel data.

Read-only. A section is built only when the caller's active role holds the matching permission
(session overrides applied). Everything is scoped to the caller's bank; the teller section is
always the caller's own work. Money is summed on the server as `Decimal` per currency.
"""

from decimal import Decimal

from django.db.models import Count, Sum

from apps.ledger import services as ledger
from apps.rbac import services as rbac

from . import cash, tellers
from . import services as banking
from . import txn_core as core
from .models import (
    Approval,
    ApprovalStatus,
    BusinessDay,
    BusinessDayStatus,
    CashPosition,
    CashTransfer,
    HolderType,
    TellerSession,
    TellerSessionStatus,
    Transaction,
    TransferStatus,
    TxnStatus,
    TxnType,
)

ZERO = Decimal("0.00")
CURRENCIES = cash.CURRENCIES

P_VAULT_VIEW = "vault.view"
P_TRANSFER_CUSTODIAN = "cash.vault.approve_custodian"
P_TRANSFER_MANAGER = "cash.vault.approve_manager"

_IN_TYPES = (TxnType.CASH_DEPOSIT,)
_OUT_TYPES = (TxnType.CASH_WITHDRAWAL, TxnType.CHEQUE_WITHDRAWAL)


def _per_currency(values: dict) -> list[dict]:
    return [{"currency": c, "amount": values.get(c, ZERO)} for c in CURRENCIES]


def _current_day(bank) -> BusinessDay | None:
    """The open business day, else the latest one."""
    days = BusinessDay.objects.filter(bank=bank)
    return days.filter(status=BusinessDayStatus.OPEN).first() or days.order_by("-date").first()


def _teller_section(member, day) -> dict:
    ts = tellers.my_session(member)  # None without an open business day / session
    balances = (
        [{"currency": b["currency"], "amount": b["balance"]} for b in ts["balances"]]
        if ts
        else _per_currency({})
    )
    today = {
        "count": 0,
        "total_in": _per_currency({}),
        "total_out": _per_currency({}),
        "pending_count": 0,
    }
    if day is not None:
        mine = Transaction.objects.filter(
            bank_id=member.bank_id, created_by=member, business_date=day.date
        )
        posted = mine.filter(status=TxnStatus.POSTED)
        today["count"] = posted.count()
        today["pending_count"] = mine.filter(status=TxnStatus.PENDING_APPROVAL).count()
        for key, types in (("total_in", _IN_TYPES), ("total_out", _OUT_TYPES)):
            sums = dict(
                posted.filter(type__in=types)
                .values("currency")
                .annotate(total=Sum("amount"))
                .values_list("currency", "total")
            )
            today[key] = _per_currency(sums)
    return {
        "teller_session": (
            {
                "id": ts["id"],
                "till_code": ts["till_code"],
                "business_date": ts["business_date"],
                "opened_at": ts["opened_at"],
            }
            if ts
            else None
        ),
        "till_status": ts["status"] if ts else "none",
        "till_cash": balances,
        "today": today,
        "pending_approvals": Approval.objects.filter(
            bank_id=member.bank_id, requested_by=member, status=ApprovalStatus.PENDING
        ).count(),
    }


def _manager_section(bank, day, can) -> dict:
    out: dict = {
        "business_day": {"date": day.date, "status": day.status} if day else None,
        "cash": None,
        "open_tills": None,
        "closing_tills": None,
        "pending_approvals": [],
    }
    if can(P_VAULT_VIEW):
        vault = {c: ZERO for c in CURRENCIES}
        for branch in banking.vault_overview(bank)["branches"]:
            for p in branch["positions"]:
                vault[p["currency"]] += p["balance"]
        tills = dict(
            CashPosition.objects.filter(bank=bank, holder_type=HolderType.TELLER_SESSION)
            .values("currency")
            .annotate(total=Sum("balance"))
            .values_list("currency", "total")
        )
        out["cash"] = [
            {
                "currency": c,
                "vault": vault[c],
                "tills": tills.get(c, ZERO),
                "total": vault[c] + tills.get(c, ZERO),
            }
            for c in CURRENCIES
        ]
    if can(tellers.P_OPEN_APPROVE) or can(tellers.P_CLOSE_APPROVE):
        counts = dict(
            TellerSession.objects.filter(bank=bank)
            .exclude(status__in=(TellerSessionStatus.CLOSED, TellerSessionStatus.CANCELLED))
            .values("status")
            .annotate(n=Count("pk"))
            .values_list("status", "n")
        )
        out["open_tills"] = counts.get(TellerSessionStatus.OPEN, 0)
        out["closing_tills"] = counts.get(TellerSessionStatus.CLOSING, 0)
        if can(tellers.P_OPEN_APPROVE):
            out["pending_approvals"].append(
                {"type": "till_open", "count": counts.get(TellerSessionStatus.PENDING_OPEN, 0)}
            )
        if can(tellers.P_CLOSE_APPROVE):
            out["pending_approvals"].append(
                {"type": "till_close", "count": counts.get(TellerSessionStatus.CLOSING, 0)}
            )
    if can(core.PERM_DECIDE):
        out["pending_approvals"].append(
            {
                "type": "transaction_limit",
                "count": Approval.objects.filter(
                    bank=bank, subject_type="transaction", status=ApprovalStatus.PENDING
                ).count(),
            }
        )
    if can(P_TRANSFER_CUSTODIAN) or can(P_TRANSFER_MANAGER):
        wanted = []
        if can(P_TRANSFER_CUSTODIAN):
            wanted.append(TransferStatus.PENDING)
        if can(P_TRANSFER_MANAGER):
            wanted.append(TransferStatus.CUSTODIAN_APPROVED)
        out["pending_approvals"].append(
            {
                "type": "cash_transfer",
                "count": CashTransfer.objects.filter(bank=bank, status__in=wanted).count(),
            }
        )
    return out


def dashboard(member, session, role: str) -> dict:
    """Dashboard of `member` (active role `role`) for the member's bank."""
    overrides = rbac.load_overrides(session)

    def can(code: str) -> bool:
        return rbac.permission_scope(role, code, session=session, overrides=overrides) is not None

    day = _current_day(member.bank)
    open_day = day if day and day.status == BusinessDayStatus.OPEN else None
    out = {
        "role": role,
        "business_date": open_day.date if open_day else None,
        "teller": None,
        "manager": None,
    }
    if can(tellers.P_OPEN_REQUEST) or can(tellers.P_CLOSE):
        out["teller"] = _teller_section(member, open_day)
    manager_codes = (
        P_VAULT_VIEW,
        core.PERM_DECIDE,
        tellers.P_OPEN_APPROVE,
        tellers.P_CLOSE_APPROVE,
        P_TRANSFER_CUSTODIAN,
        P_TRANSFER_MANAGER,
    )
    if any(can(c) for c in manager_codes):
        out["manager"] = _manager_section(member.bank, day, can)
    return out


# --------------------------------------------------------------------------- learning panel

EXPLANATION = {
    TxnType.CASH_DEPOSIT: (
        "The customer hands cash to the bank. Bank cash (an asset) goes up, so the till is "
        "debited. The bank now owes the customer more (a liability), so the customer account "
        "is credited."
    ),
    TxnType.CASH_WITHDRAWAL: (
        "The customer takes cash out. The bank owes the customer less, so the customer "
        "account is debited. Bank cash goes down, so the till is credited."
    ),
    TxnType.CHEQUE_WITHDRAWAL: (
        "A cheque is paid in cash. The account that wrote the cheque is debited because the "
        "bank owes them less, and the till is credited because bank cash goes down."
    ),
    TxnType.TRANSFER: (
        "Money moves between two customer accounts inside the bank. The sending account is "
        "debited and the receiving account is credited. No cash moves, so bank totals "
        "stay the same."
    ),
    TxnType.REVERSAL: (
        "A reversal undoes an earlier transaction by posting the opposite entry: every debit "
        "of the original becomes a credit and every credit becomes a debit. The original is "
        "never edited or deleted."
    ),
}


def learning_view(bank, txn: Transaction) -> dict:
    """Journal lines of a visible transaction with a short explanation."""
    lines, entry_no, note = [], None, None
    if txn.journal_entry_id:
        entry = ledger.get_entry(bank, txn.journal_entry_id)
        entry_no = entry.entry_no
        lines = [
            {
                "gl_code": ln.gl_account.code,
                "gl_name": ln.gl_account.name,
                "debit": ln.debit,
                "credit": ln.credit,
                "currency": ln.currency,
            }
            for ln in entry.lines.all()
        ]
    else:
        note = "Nothing is posted yet: the journal entry appears once the transaction is posted."
    return {
        "transaction_id": txn.pk,
        "ref_no": txn.ref_no,
        "type": txn.type,
        "status": txn.status,
        "currency": txn.currency,
        "journal_entry_no": entry_no,
        "lines": lines,
        "total_debit": sum((ln["debit"] for ln in lines), ZERO),
        "total_credit": sum((ln["credit"] for ln in lines), ZERO),
        "explanation": EXPLANATION.get(txn.type, ""),
        "note": note,
    }
