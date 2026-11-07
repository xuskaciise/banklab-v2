"""Ledger engine: chart of accounts per bank and the single posting service.

`post_entry` / `reverse_entry` are the only code paths that write journal rows and
`GLBalance`. Callers (transaction services in 1.5+) check role permissions, limits and
approvals before calling; this module re-checks everything that protects the books.

LOCK ORDER (every caller in 1.5+ that locks ledger-related rows must follow it):
    session (FOR NO KEY UPDATE) -> bank (FOR NO KEY UPDATE; serialises entry_no)
    -> open business day -> GL balances (by id).
Archiving takes a plain FOR UPDATE on the session, so it waits for in-flight postings and
blocks new ones; postings in different banks of one session do not block each other.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max, Sum

from apps.accounts.models import Institution
from apps.audit import services as audit
from apps.banking.models import BusinessDay, BusinessDayStatus
from apps.lab.models import Bank, RoleAssignment, Session, SessionMember, SessionStatus

from .coa import ALLOW_NEGATIVE_TAGS, DEFAULT_COA, DEFAULT_COA_NAME
from .models import (
    CoaTemplate,
    CoaTemplateLine,
    Currency,
    GLAccount,
    GLBalance,
    JournalEntry,
    JournalLine,
)

ZERO = Decimal("0.00")
CURRENCIES = {c.value for c in Currency}


class LedgerError(Exception):
    """Domain error; `code` is machine-readable, `status` the HTTP status the API maps to."""

    status = 400

    def __init__(self, code: str, message: str, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        if status is not None:
            self.status = status


def _conflict(code: str, message: str) -> LedgerError:
    return LedgerError(code, message, status=409)


@dataclass
class LineSpec:
    """One line of a posting. Exactly one of `debit` / `credit` is > 0."""

    gl_account: GLAccount
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    currency: str | None = None  # optional; must equal the entry currency when given
    account_id: object = None
    cash_holder_type: str = ""
    cash_holder_id: object = None


# --------------------------------------------------------------------------- CoA


def get_default_template(institution: Institution) -> CoaTemplate:
    """The institution's default CoA template; created from coa.md when missing."""
    template, created = CoaTemplate.objects.get_or_create(
        institution=institution, name=DEFAULT_COA_NAME
    )
    if created:
        CoaTemplateLine.objects.bulk_create(
            CoaTemplateLine(
                template=template,
                code=code,
                name=name,
                type=typ,
                parent_code=parent,
                postable=postable,
                system_tag=tag,
                is_active=active,
                allow_negative=tag in ALLOW_NEGATIVE_TAGS,
            )
            for code, name, typ, parent, postable, tag, active in DEFAULT_COA
        )
    return template


@transaction.atomic
def provision_bank_coa(bank: Bank) -> list[GLAccount]:
    """Copy the session template's CoA (or the institution default) into the new bank and
    create zero GL balances (USD and SOS) for every postable account."""
    if GLAccount.objects.filter(bank=bank).exists():
        raise LedgerError("coa_exists", "This bank already has a chart of accounts")
    session = Session.objects.select_related("template__coa_template", "lab_class").get(
        pk=bank.session_id
    )
    template = session.template.coa_template if session.template else None
    if template is None:
        template = get_default_template(session.lab_class.institution)
    lines = list(template.lines.all().order_by("code"))
    accounts: dict[str, GLAccount] = {}
    for line in lines:
        accounts[line.code] = GLAccount.objects.create(
            bank=bank,
            code=line.code,
            name=line.name,
            type=line.type,
            postable=line.postable,
            system_tag=line.system_tag,
            is_active=line.is_active,
            allow_negative=line.allow_negative,
        )
    for line in lines:
        parent = accounts.get(line.parent_code) if line.parent_code else None
        if parent is not None:
            acc = accounts[line.code]
            acc.parent = parent
            acc.save(update_fields=["parent", "updated_at"])
    GLBalance.objects.bulk_create(
        GLBalance(bank=bank, gl_account=acc, currency=cur)
        for acc in accounts.values()
        if acc.postable
        for cur in sorted(CURRENCIES)
    )
    return list(accounts.values())


# --------------------------------------------------------------------------- validation


def _check_amount(value, what: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, str)):
        raise LedgerError("invalid_amount", f"{what} must be a Decimal amount")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        raise LedgerError("invalid_amount", f"{what} is not a valid amount") from None
    if not amount.is_finite():
        raise LedgerError("invalid_amount", f"{what} is not a valid amount")
    if amount.as_tuple().exponent < -2:
        raise LedgerError("invalid_amount", f"{what} has more than 2 decimal places")
    if amount < 0:
        raise LedgerError("invalid_amount", f"{what} cannot be negative")
    if amount >= Decimal("10") ** 16:
        raise LedgerError("invalid_amount", f"{what} is too large")
    return amount.quantize(ZERO)


def _normalise(lines, currency: str, bank: Bank) -> list[LineSpec]:
    if currency not in CURRENCIES:
        raise LedgerError("invalid_currency", "Currency must be USD or SOS")
    lines = list(lines)
    if len(lines) < 2:
        raise LedgerError("too_few_lines", "An entry needs at least two lines")
    out: list[LineSpec] = []
    total_dr = total_cr = ZERO
    for i, spec in enumerate(lines, start=1):
        if spec.currency is not None and spec.currency != currency:
            raise LedgerError("mixed_currency", f"Line {i} currency differs from the entry")
        debit = _check_amount(spec.debit, f"Line {i} debit")
        credit = _check_amount(spec.credit, f"Line {i} credit")
        if (debit > 0) == (credit > 0):
            raise LedgerError(
                "invalid_line", f"Line {i} must have exactly one of debit or credit above zero"
            )
        acc = spec.gl_account
        if acc.bank_id != bank.pk:
            raise LedgerError("foreign_account", f"Line {i}: GL account is not in this bank")
        out.append(
            LineSpec(
                acc,
                debit,
                credit,
                currency,
                spec.account_id,
                spec.cash_holder_type,
                spec.cash_holder_id,
            )
        )
        total_dr += debit
        total_cr += credit
    if total_dr != total_cr:
        raise LedgerError("unbalanced", f"Entry is not balanced (Dr {total_dr} <> Cr {total_cr})")
    return out


def _check_text(value, max_len: int, what: str) -> None:
    if not isinstance(value, str) or (what == "source_type" and not value):
        raise LedgerError("invalid_text", f"{what} is required")
    if len(value) > max_len:
        raise LedgerError("text_too_long", f"{what} is longer than {max_len} characters")


def _check_actor(bank: Bank, actor_member: SessionMember | None) -> None:
    if actor_member is None:
        return
    if actor_member.bank_id != bank.pk or actor_member.session_id != bank.session_id:
        raise LedgerError("actor_not_in_bank", "Actor does not belong to this bank", status=403)
    if not RoleAssignment.objects.filter(
        session_member=actor_member, active_to__isnull=True
    ).exists():
        raise LedgerError("actor_no_role", "Actor has no active role", status=403)


def _lock_context(bank: Bank) -> tuple[Bank, BusinessDay]:
    """Lock session (archive guard), bank (entry_no + serialisation) and the open day,
    in the documented order."""
    session = Session.objects.select_for_update(no_key=True).get(pk=bank.session_id)
    if session.status == SessionStatus.ARCHIVED:
        raise _conflict("session_archived", "Session is archived (read-only)")
    if session.status != SessionStatus.ACTIVE:
        raise _conflict("session_not_active", "Session is not active")
    locked = Bank.objects.select_for_update(no_key=True).get(pk=bank.pk)
    day = (
        BusinessDay.objects.select_for_update()
        .filter(bank=locked, status=BusinessDayStatus.OPEN)
        .first()
    )
    if day is None:
        raise _conflict("day_closed", "The bank has no open business day")
    return locked, day


# --------------------------------------------------------------------------- posting


def _apply(bank: Bank, specs: list[LineSpec], currency: str) -> None:
    """Lock the affected GL balances in id order, apply deltas, reject negatives."""
    deltas: dict[object, Decimal] = defaultdict(lambda: ZERO)
    accounts = {}
    for s in specs:
        acc = s.gl_account
        accounts[acc.pk] = acc
        delta = (s.debit - s.credit) if acc.debit_normal else (s.credit - s.debit)
        deltas[acc.pk] += delta
    existing = set(
        GLBalance.objects.filter(gl_account_id__in=deltas, currency=currency).values_list(
            "gl_account_id", flat=True
        )
    )
    missing = [pk for pk in deltas if pk not in existing]
    if missing:
        GLBalance.objects.bulk_create(
            [GLBalance(bank=bank, gl_account_id=pk, currency=currency) for pk in missing],
            ignore_conflicts=True,
        )
    rows = list(
        GLBalance.objects.select_for_update()
        .filter(gl_account_id__in=deltas, currency=currency)
        .order_by("id")
    )
    for row in rows:
        acc = accounts[row.gl_account_id]
        new = row.balance + deltas[row.gl_account_id]
        if new < 0 and not acc.allow_negative:
            raise _conflict(
                "insufficient_balance",
                f"Insufficient balance on {acc.code} {acc.name} ({currency})",
            )
        row.balance = new
    for row in rows:
        row.save(update_fields=["balance", "updated_at"])


def _write(
    bank: Bank,
    day: BusinessDay,
    specs: list[LineSpec],
    currency: str,
    *,
    source_type,
    source_id,
    description,
    reversal_of,
    actor_member,
    actor_user,
    audit_action,
) -> JournalEntry:
    _apply(bank, specs, currency)
    last = JournalEntry.objects.filter(bank=bank).aggregate(m=Max("entry_no"))["m"] or 0
    user = actor_member.user if actor_member is not None else actor_user
    entry = JournalEntry.objects.create(
        bank=bank,
        entry_no=last + 1,
        business_date=day.date,
        currency=currency,
        source_type=source_type,
        source_id=source_id,
        description=description,
        reversal_of=reversal_of,
        posted_by=actor_member,
        posted_by_user=user,
    )
    JournalLine.objects.bulk_create(
        JournalLine(
            entry=entry,
            gl_account=s.gl_account,
            currency=currency,
            debit=s.debit,
            credit=s.credit,
            account_id=s.account_id,
            cash_holder_type=s.cash_holder_type,
            cash_holder_id=s.cash_holder_id,
        )
        for s in specs
    )
    role = ""
    if actor_member is not None:
        assignment = RoleAssignment.objects.filter(
            session_member=actor_member, active_to__isnull=True
        ).first()
        role = assignment.role if assignment else ""
    institution_id = (
        Session.objects.filter(pk=bank.session_id)
        .values_list("lab_class__institution_id", flat=True)
        .first()
    )
    audit.record(
        audit_action,
        actor=user,
        actor_role=role,
        entity=("journal_entry", entry.pk),
        after={
            "entry_no": entry.entry_no,
            "currency": currency,
            "business_date": str(day.date),
            "source_type": source_type,
            "reversal_of": str(reversal_of.pk) if reversal_of else None,
            "total": str(sum((s.debit for s in specs), ZERO)),
            "lines": [
                {"gl": s.gl_account.code, "dr": str(s.debit), "cr": str(s.credit)} for s in specs
            ],
        },
        session_id=bank.session_id,
        bank_id=bank.pk,
        institution_id=institution_id,
    )
    return entry


def post_entry(
    bank: Bank,
    lines,
    *,
    currency: str,
    source_type: str,
    description: str,
    source_id=None,
    business_date=None,
    actor_member: SessionMember | None = None,
    actor_user=None,
) -> JournalEntry:
    """Post one balanced, single-currency journal entry to the bank's open business day.

    Internal API: permission/limit/approval checks belong to the calling transaction service.
    Lock order: session -> bank -> business day -> GL balances by id (see module docstring);
    callers that lock their own rows (accounts, cash positions) must do so after these.
    """
    _check_text(source_type, 40, "source_type")
    _check_text(description, 300, "description")
    specs = _normalise(lines, currency, bank)
    with transaction.atomic():
        locked, day = _lock_context(bank)
        _check_actor(locked, actor_member)
        if business_date is not None and business_date != day.date:
            raise _conflict("wrong_business_date", "Entry date is not the open business day")
        accounts = {
            a.pk: a
            for a in GLAccount.objects.filter(
                pk__in={s.gl_account.pk for s in specs}, bank=locked
            )
        }
        for s in specs:
            acc = accounts.get(s.gl_account.pk)
            if acc is None:
                raise LedgerError("foreign_account", "GL account is not in this bank")
            if not acc.postable or not acc.is_active:
                raise LedgerError(
                    "account_not_postable", f"GL account {acc.code} is not open for posting"
                )
            s.gl_account = acc
        return _write(
            locked,
            day,
            specs,
            currency,
            source_type=source_type,
            source_id=source_id,
            description=description,
            reversal_of=None,
            actor_member=actor_member,
            actor_user=actor_user,
            audit_action="ledger.entry_posted",
        )


def reverse_entry(
    bank: Bank,
    entry: JournalEntry,
    *,
    actor_member: SessionMember | None = None,
    actor_user=None,
    description: str | None = None,
) -> JournalEntry:
    """Post the mirror of `entry` (Dr and Cr swapped) on the same, still open, business day."""
    if description is not None:
        _check_text(description, 300, "description")
    if entry.bank_id != bank.pk:
        raise LedgerError("foreign_entry", "Entry is not in this bank")
    with transaction.atomic():
        locked, day = _lock_context(bank)
        _check_actor(locked, actor_member)
        # Re-read under the bank lock; never trust the caller's (possibly stale) object.
        original = JournalEntry.objects.filter(pk=entry.pk, bank=locked).first()
        if original is None:
            raise LedgerError("foreign_entry", "Entry is not in this bank")
        if original.reversal_of_id is not None:
            raise _conflict("is_reversal", "A reversal entry cannot be reversed")
        if JournalEntry.objects.filter(reversal_of=original).exists():
            raise _conflict("already_reversed", "Entry is already reversed")
        if original.business_date != day.date:
            raise _conflict(
                "other_business_day", "Only entries of the open business day can be reversed"
            )
        specs = []
        for line in original.lines.select_related("gl_account").order_by("id"):
            specs.append(
                LineSpec(
                    line.gl_account,
                    debit=line.credit,
                    credit=line.debit,
                    currency=line.currency,
                    account_id=line.account_id,
                    cash_holder_type=line.cash_holder_type,
                    cash_holder_id=line.cash_holder_id,
                )
            )
        return _write(
            locked,
            day,
            specs,
            original.currency,
            source_type="reversal",
            source_id=original.pk,
            description=description or f"Reversal of entry #{original.entry_no}",
            reversal_of=original,
            actor_member=actor_member,
            actor_user=actor_user,
            audit_action="ledger.entry_reversed",
        )


# --------------------------------------------------------------------------- reads


def balances_for_bank(bank: Bank) -> dict[tuple[str, str], Decimal]:
    """{(gl code, currency): balance} for the bank."""
    return {
        (code, cur): bal
        for code, cur, bal in GLBalance.objects.filter(bank=bank).values_list(
            "gl_account__code", "currency", "balance"
        )
    }


def recompute_balances(bank: Bank) -> dict[tuple[str, str], Decimal]:
    """Balances recomputed from journal lines (reconciliation check)."""
    result: dict[tuple[str, str], Decimal] = {}
    for acc in GLAccount.objects.filter(bank=bank, postable=True):
        for cur in CURRENCIES:
            sums = JournalLine.objects.filter(
                entry__bank=bank, gl_account=acc, currency=cur
            ).aggregate(dr=Sum("debit"), cr=Sum("credit"))
            dr, cr = sums["dr"] or ZERO, sums["cr"] or ZERO
            result[(acc.code, cur)] = (dr - cr) if acc.debit_normal else (cr - dr)
    return result


def balances_match_lines(bank: Bank) -> bool:
    stored = balances_for_bank(bank)
    return all(stored.get(key, ZERO) == value for key, value in recompute_balances(bank).items())


def gl_tree(bank: Bank) -> list[dict]:
    """Every GL account of the bank with its balance per currency."""
    balances: dict[object, dict[str, Decimal]] = defaultdict(dict)
    for acc_id, cur, bal in GLBalance.objects.filter(bank=bank).values_list(
        "gl_account_id", "currency", "balance"
    ):
        balances[acc_id][cur] = bal
    rows = []
    for acc in GLAccount.objects.filter(bank=bank).order_by("code"):
        rows.append(
            {
                "id": acc.pk,
                "code": acc.code,
                "name": acc.name,
                "type": acc.type,
                "parent_id": acc.parent_id,
                "postable": acc.postable,
                "system_tag": acc.system_tag,
                "is_active": acc.is_active,
                "balances": [
                    {"currency": cur, "balance": balances[acc.pk].get(cur, ZERO)}
                    for cur in sorted(CURRENCIES)
                ]
                if acc.postable
                else [],
            }
        )
    return rows


def list_entries(bank: Bank, *, currency=None, date_from=None, date_to=None):
    qs = JournalEntry.objects.filter(bank=bank).prefetch_related("lines__gl_account")
    if currency:
        qs = qs.filter(currency=currency)
    if date_from:
        qs = qs.filter(business_date__gte=date_from)
    if date_to:
        qs = qs.filter(business_date__lte=date_to)
    return qs.order_by("-entry_no")


def get_entry(bank: Bank, entry_id) -> JournalEntry:
    entry = (
        JournalEntry.objects.filter(bank=bank, pk=entry_id)
        .prefetch_related("lines__gl_account")
        .first()
    )
    if entry is None:
        raise LedgerError("not_found", "Journal entry not found", status=404)
    return entry
