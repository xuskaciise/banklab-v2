"""Auto-check registry. Every check runs on the student's own rows only (created_by /
seed_owner / teller_member = the attempt's member, in the member's bank).

Add a check: write `validate(params) -> clean params` and `run(member, params, since) ->
(passed, details)` (`since` = attempt start: older rows never count), then register it with
`@register("name", "Label")`.
`details` is shown to the instructor, so it never contains other students' data.
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from apps.banking.models import (
    CashCount,
    CashCountKind,
    TellerSession,
    TellerSessionStatus,
    Transaction,
    TxnStatus,
    TxnType,
)
from apps.customers.models import Customer, CustomerType
from apps.ledger.models import JournalLine
from apps.products.models import Account

ZERO = Decimal("0.00")
SEED_SOURCE = "exam_seed"


class CheckConfigError(ValueError):
    """The task's check parameters are invalid (shown to the instructor as a 400)."""


@dataclass
class Check:
    name: str
    label: str
    validate: Callable[[dict], dict]
    run: Callable[[object, dict, object], tuple[bool, dict]]


CHECKS: dict[str, Check] = {}


def register(name: str, label: str):
    def deco(cls):
        CHECKS[name] = Check(name, label, cls.validate, cls.run)
        return cls

    return deco


def _amount(params: dict, key: str, *, required: bool = True, positive: bool = True):
    raw = params.get(key)
    if raw in (None, ""):
        if required:
            raise CheckConfigError(f"'{key}' is required")
        return None
    try:
        value = Decimal(str(raw)).quantize(ZERO)
    except (InvalidOperation, ValueError):
        raise CheckConfigError(f"'{key}' must be a number") from None
    if positive and value <= 0:
        raise CheckConfigError(f"'{key}' must be greater than zero")
    return value


def _currency(params: dict, *, required: bool):
    cur = params.get("currency")
    if cur in (None, ""):
        if required:
            raise CheckConfigError("'currency' is required")
        return None
    if cur not in ("USD", "SOS"):
        raise CheckConfigError("'currency' must be USD or SOS")
    return cur


def _count(params: dict) -> int:
    raw = params.get("min_count", 1)
    if not isinstance(raw, int) or isinstance(raw, bool) or not 1 <= raw <= 100:
        raise CheckConfigError("'min_count' must be a whole number between 1 and 100")
    return raw


def opening_amount(account: Account) -> Decimal:
    """What the exam seed credited to a seed account."""
    line = JournalLine.objects.filter(
        account_id=account.pk, entry__source_type=SEED_SOURCE, credit__gt=0
    ).first()
    return line.credit if line else ZERO


def _expected(acc: Account, params: dict) -> Decimal:
    if "delta" in params:
        return opening_amount(acc) + Decimal(params["delta"])
    return Decimal(params["amount"])


@register("account_balance_equals", "Account balance equals")
class AccountBalanceEquals:
    """`account`: "seed" (the student's seed account number `seed_index`, from 0) or "opened"
    (any account the student opened, optional `product_code`). Expected balance is `amount`
    (absolute) or `delta` (seed only: opening balance + delta)."""

    @staticmethod
    def validate(params):
        which = params.get("account")
        if which not in ("seed", "opened"):
            raise CheckConfigError("'account' must be 'seed' or 'opened'")
        clean = {"account": which}
        amount = _amount(params, "amount", required=False, positive=False)
        delta = _amount(params, "delta", required=False, positive=False)
        if (amount is None) == (delta is None):
            raise CheckConfigError("Give exactly one of 'amount' or 'delta'")
        if amount is not None:
            if amount < 0:
                raise CheckConfigError("'amount' must not be negative")
            clean["amount"] = str(amount)
        if delta is not None:
            if which != "seed":
                raise CheckConfigError("'delta' only applies to seed accounts")
            clean["delta"] = str(delta)
        if which == "seed":
            idx = params.get("seed_index", 0)
            if not isinstance(idx, int) or isinstance(idx, bool) or not 0 <= idx <= 20:
                raise CheckConfigError("'seed_index' must be a whole number from 0")
            clean["seed_index"] = idx
        elif params.get("product_code"):
            clean["product_code"] = str(params["product_code"])[:20]
        cur = _currency(params, required=False)
        if cur:
            clean["currency"] = cur
        return clean

    @staticmethod
    def run(member, params, since):
        accounts = Account.objects.filter(bank_id=member.bank_id)
        if params["account"] == "seed":
            rows = list(accounts.filter(seed_owner=member, is_seed=True).order_by("account_no"))
            idx = params.get("seed_index", 0)
            candidates = rows[idx : idx + 1]
        else:
            q = accounts.filter(created_by=member, is_seed=False, created_at__gte=since)
            if params.get("product_code"):
                q = q.filter(product__code=params["product_code"])
            candidates = list(q.order_by("account_no"))
        if params.get("currency"):
            candidates = [a for a in candidates if a.currency == params["currency"]]
        if not candidates:
            return False, {"reason": "account_not_found"}
        for acc in candidates:
            if acc.ledger_balance == _expected(acc, params):
                return True, _details(acc, params)
        return False, _details(candidates[0], params)


def _details(acc: Account, params: dict) -> dict:
    return {
        "account_no": acc.account_no,
        "expected": str(_expected(acc, params)),
        "actual": str(acc.ledger_balance),
        "currency": acc.currency,
    }


@register("txn_exists", "Transaction posted")
class TxnExists:
    """The student posted `min_count` (default 1) transactions of `type`, `amount`, `currency`."""

    @staticmethod
    def validate(params):
        kind = params.get("type")
        allowed = [v for v in TxnType.values if v != TxnType.REVERSAL]
        if kind not in allowed:
            raise CheckConfigError(f"'type' must be one of: {', '.join(allowed)}")
        return {
            "type": kind,
            "amount": str(_amount(params, "amount")),
            "currency": _currency(params, required=True),
            "min_count": _count(params),
        }

    @staticmethod
    def run(member, params, since):
        found = Transaction.objects.filter(
            bank_id=member.bank_id,
            created_by=member,
            status=TxnStatus.POSTED,
            created_at__gte=since,
            type=params["type"],
            amount=Decimal(params["amount"]),
            currency=params["currency"],
        ).count()
        need = params.get("min_count", 1)
        return found >= need, {"found": found, "required": need}


@register("till_closed_balanced", "Till closed with no over/short")
class TillClosedBalanced:
    """The student has a closed teller session whose final closing counts all show zero
    difference (optionally only for `currency`)."""

    @staticmethod
    def validate(params):
        cur = _currency(params, required=False)
        return {"currency": cur} if cur else {}

    @staticmethod
    def run(member, params, since):
        sessions = TellerSession.objects.filter(
            bank_id=member.bank_id, teller_member=member, status=TellerSessionStatus.CLOSED
        )
        if not sessions.exists():
            return False, {"reason": "till_not_closed"}
        worst = None
        for ts in sessions:
            latest: dict[str, CashCount] = {}
            for c in CashCount.objects.filter(teller_session=ts, kind=CashCountKind.CLOSE):
                if params.get("currency") and c.currency != params["currency"]:
                    continue
                if c.currency not in latest or c.attempt > latest[c.currency].attempt:
                    latest[c.currency] = c
            if not latest:
                continue
            diffs = {cur: str(c.difference) for cur, c in latest.items()}
            if all(c.difference == 0 for c in latest.values()):
                return True, {"over_short": diffs}
            worst = diffs
        if worst is None:
            return False, {"reason": "no_closing_count"}
        return False, {"over_short": worst}


@register("customer_created", "Customer created")
class CustomerCreated:
    """The student created `min_count` (default 1) customers, optionally of one `type`."""

    @staticmethod
    def validate(params):
        clean = {"min_count": _count(params)}
        ctype = params.get("type")
        if ctype not in (None, ""):
            if ctype not in CustomerType.values:
                raise CheckConfigError(f"'type' must be one of: {', '.join(CustomerType.values)}")
            clean["type"] = ctype
        return clean

    @staticmethod
    def run(member, params, since):
        q = Customer.objects.filter(
            bank_id=member.bank_id, created_by=member, is_seed=False, created_at__gte=since
        )
        if params.get("type"):
            q = q.filter(type=params["type"])
        found = q.count()
        need = params.get("min_count", 1)
        return found >= need, {"found": found, "required": need}


def validate_params(check_type: str, params) -> dict:
    check = CHECKS.get(check_type)
    if check is None:
        raise CheckConfigError(f"Unknown check type. Use one of: {', '.join(sorted(CHECKS))}")
    if not isinstance(params, dict):
        raise CheckConfigError("check_params must be an object")
    return check.validate(params)
