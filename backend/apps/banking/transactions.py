"""Customer transactions: cash deposit (C1), cash withdrawal (C2), transfer (C4), reversal (D1).

Student functions take the acting `SessionMember` and re-check role permission, the open
business day, the teller session, limits and balances on the server. Above the actor's
`LimitRule` a transaction is stored as `pending_approval` with an `Approval(limit)` and posts
only when a manager approves it (see approvals.py). Every write is audited.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core import platform
from apps.customers import services as customers
from apps.ledger import services as ledger
from apps.ledger.services import LedgerError
from apps.rbac import services as rbac

from . import cheques, limits
from . import txn_core as core
from .models import (
    Approval,
    ApprovalReason,
    Transaction,
    TxnStatus,
    TxnType,
)

REVERSIBLE = (
    TxnType.CASH_DEPOSIT,
    TxnType.CASH_WITHDRAWAL,
    TxnType.CHEQUE_WITHDRAWAL,
    TxnType.TRANSFER,
)


def _amount(value) -> Decimal:
    amount = ledger._check_amount(value, "Amount")
    if amount <= 0:
        raise core.bad("invalid_amount", "Amount must be greater than zero")
    return amount


def _party(name, id_no, phone) -> dict:
    return {
        "party_name": customers._text(name, "Name", 200),
        "party_id_no": customers._text(id_no, "ID number", 60),
        "party_phone": customers._phone(customers._text(phone, "Phone", 30)),
    }


def _create(
    member,
    txn_type,
    *,
    account_id,
    counter_id=None,
    amount,
    currency,
    narration,
    party,
    cheque_no=None,
):
    """Common path of C1/C2/C4: validate, then post now or park for approval."""
    with transaction.atomic():
        session, role = core.require_perm(member, core.PERM[txn_type])
        amount = _amount(amount)
        narration = customers._text(narration, "Narration", 300, required=False)
        if currency not in ledger.CURRENCIES:
            raise core.bad("invalid_currency", "Currency must be USD or SOS")
        platform.require_currency_enabled(currency)
        if counter_id is not None and counter_id == account_id:
            raise core.bad("same_account", "Choose two different accounts")
        day = core.open_day(member.bank_id)
        ts = None
        if txn_type in core.CASH_TYPES or role == "teller":
            ts = core.require_open_ts(
                core.lock_ts(member.bank_id, member=member, business_date=day.date)
            )
        bank = core.lock_bank(member.bank_id)
        ids = [i for i in (account_id, counter_id) if i is not None]
        accounts = core.lock_accounts(bank.pk, ids)
        acc = core.check_account(accounts.get(account_id), currency, "Account")
        counter = None
        if counter_id is not None:
            counter = core.check_account(accounts.get(counter_id), currency, "Destination account")
        for found, what in ((acc, "Account"), (counter, "Destination account")):
            # another student's exam seed account behaves as if it does not exist
            if found is not None and found.seed_owner_id not in (None, member.pk):
                raise core.not_found(what)
        core.precheck(txn_type, acc, counter, amount, currency, ts)
        cheque = None
        if txn_type == TxnType.CHEQUE_WITHDRAWAL:
            cheque = cheques.reserve(bank.pk, acc, cheque_no)
        pending = limits.needs_approval(bank, role, txn_type, currency, amount)
        txn = core.new_txn(
            bank,
            day,
            type=txn_type,
            status=TxnStatus.PENDING_APPROVAL if pending else TxnStatus.POSTED,
            amount=amount,
            currency=currency,
            account=acc,
            counter_account=counter,
            teller_session=ts,
            narration=narration,
            created_by=member,
            cheque=cheque,
            **party,
        )
        if pending:
            if cheque:
                cheques.attach(cheque, txn)
            Approval.objects.create(
                bank=bank,
                subject_type="transaction",
                subject_id=txn.pk,
                reason=ApprovalReason.LIMIT,
                requested_by=member,
            )
            core.audit_txn(member, role, "txn.submitted_for_approval", session, txn)
        else:
            core.post(txn, bank, acc, counter, ts, member)
            core.audit_txn(member, role, "txn.posted", session, txn)
        return detail_qs().get(pk=txn.pk)


def deposit(
    member, *, account_id, amount, currency, party_name, party_id_no, party_phone, narration=""
):
    return _create(
        member,
        TxnType.CASH_DEPOSIT,
        account_id=account_id,
        amount=amount,
        currency=currency,
        narration=narration,
        party=_party(party_name, party_id_no, party_phone),
    )


def withdraw(
    member, *, account_id, amount, currency, party_name, party_id_no, party_phone, narration=""
):
    return _create(
        member,
        TxnType.CASH_WITHDRAWAL,
        account_id=account_id,
        amount=amount,
        currency=currency,
        narration=narration,
        party=_party(party_name, party_id_no, party_phone),
    )


def cheque_withdraw(
    member,
    *,
    account_id,
    cheque_no,
    amount,
    currency,
    party_name,
    party_id_no,
    party_phone,
    narration="",
):
    return _create(
        member,
        TxnType.CHEQUE_WITHDRAWAL,
        account_id=account_id,
        amount=amount,
        currency=currency,
        narration=narration,
        party=_party(party_name, party_id_no, party_phone),
        cheque_no=cheque_no,
    )


def transfer(member, *, from_account_id, to_account_id, amount, currency, narration=""):
    return _create(
        member,
        TxnType.TRANSFER,
        account_id=from_account_id,
        counter_id=to_account_id,
        amount=amount,
        currency=currency,
        narration=narration,
        party={},
    )


# --------------------------------------------------------------------------- reversal (D1)


def reverse(member, txn_id, reason: str = "") -> Transaction:
    """The creator reverses their own posted transaction of the open business day."""
    with transaction.atomic():
        session, role = core.require_perm(member, core.PERM_REVERSE)
        reason = customers._text(reason, "Reason", 200, required=False)
        day = core.open_day(member.bank_id)
        txn = (
            Transaction.objects.select_for_update(of=("self",))
            .filter(pk=txn_id, bank_id=member.bank_id)
            .first()
        )
        if txn is None:
            raise core.not_found()
        if txn.created_by_id != member.pk:
            raise rbac.PermissionDenied("Only the person who posted a transaction can reverse it")
        if txn.status == TxnStatus.REVERSED:
            raise core._conflict("already_reversed", "Transaction is already reversed")
        if txn.status != TxnStatus.POSTED or txn.type not in REVERSIBLE:
            raise core._conflict("not_reversible", "Only a posted transaction can be reversed")
        if txn.business_date != day.date:
            raise core._conflict(
                "other_business_day", "Only transactions of the open business day can be reversed"
            )
        ts = None
        if txn.teller_session_id:
            ts = core.require_open_ts(core.lock_ts(member.bank_id, pk=txn.teller_session_id))
        bank = core.lock_bank(member.bank_id)
        ids = [i for i in (txn.account_id, txn.counter_account_id) if i is not None]
        core.lock_accounts(bank.pk, ids)
        try:
            entry = ledger.reverse_entry(
                bank,
                txn.journal_entry,
                actor_member=member,
                description=f"Reversal of {txn.ref_no}",
            )
        except LedgerError as exc:
            if exc.code in ("insufficient_balance", "insufficient_cash"):
                raise core._conflict(
                    "reversal_negative_balance",
                    "Reversal rejected: it would make a balance negative",
                ) from exc
            raise
        rev = core.new_txn(
            bank,
            day,
            type=TxnType.REVERSAL,
            status=TxnStatus.POSTED,
            amount=txn.amount,
            currency=txn.currency,
            account_id=txn.account_id,
            counter_account_id=txn.counter_account_id,
            teller_session=ts,
            party_name=txn.party_name,
            party_id_no=txn.party_id_no,
            party_phone=txn.party_phone,
            narration=(f"Reversal of {txn.ref_no}" + (f": {reason}" if reason else ""))[:300],
            created_by=member,
            journal_entry=entry,
            reversal_of=txn,
        )
        txn.status = TxnStatus.REVERSED
        txn.save(update_fields=["status", "updated_at"])
        cheques.release(txn)
        core.audit_txn(
            member,
            role,
            "txn.reversed",
            session,
            txn,
            before={"status": TxnStatus.POSTED},
            after={
                "status": TxnStatus.REVERSED,
                "reversal_ref_no": rev.ref_no,
                "reason": reason,
                "reversed_at": timezone.now().isoformat(),
            },
        )
        return detail_qs().get(pk=txn.pk)


# --------------------------------------------------------------------------- reads


def detail_qs():
    return Transaction.objects.select_related(
        "account__customer",
        "account__product",
        "counter_account__customer",
        "created_by__user",
        "journal_entry",
        "reversal_of",
        "cheque",
        "teller_session__teller_member__user",
        "bank",
    )


def _visible(member, scope):
    qs = detail_qs().filter(bank_id=member.bank_id)
    return qs.filter(created_by=member) if scope == "own" else qs


def list_transactions(member, *, status=None, type=None, account_id=None, business_date=None):
    _, _, scope = customers._read_scope(member, core.PERM_READ)
    qs = _visible(member, scope)
    if status:
        if status not in TxnStatus.values:
            raise core.bad(
                "invalid_filter", f"Status must be one of: {', '.join(TxnStatus.values)}"
            )
        qs = qs.filter(status=status)
    if type:
        if type not in TxnType.values:
            raise core.bad("invalid_filter", f"Type must be one of: {', '.join(TxnType.values)}")
        qs = qs.filter(type=type)
    if account_id:
        qs = qs.filter(account_id=account_id)
    if business_date:
        qs = qs.filter(business_date=business_date)
    return qs.order_by("-created_at")


def get_transaction(member, txn_id) -> Transaction:
    _, _, scope = customers._read_scope(member, core.PERM_READ)
    txn = _visible(member, scope).filter(pk=txn_id).first()
    if txn is None:
        raise core.not_found()
    return txn
