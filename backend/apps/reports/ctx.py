"""Request context and small helpers shared by the report builders."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.banking.models import Branch, BusinessDay, BusinessDayStatus
from apps.core.platform import enabled_currencies
from apps.ledger.models import JournalLine
from apps.ledger.services import CURRENCIES, LedgerError

from .doc import ZERO, Report


@dataclass
class Ctx:
    """Who reads which bank. `member` is None for instructor/admin (staff) reads, which
    see the whole bank; students carry `scope` = "own" when their reads are own-work only."""

    bank: object
    user: object
    member: object = None
    scope: str = "all"

    @property
    def own_only(self) -> bool:
        return self.member is not None and self.scope == "own"


def bad(message: str, code: str = "invalid_report_filter") -> LedgerError:
    return LedgerError(code, message)


def not_found(what: str) -> LedgerError:
    return LedgerError("not_found", f"{what} not found", status=404)


def check_currency(currency: str | None) -> str | None:
    if currency and currency not in CURRENCIES:
        raise bad("Currency must be USD or SOS")
    return currency or None


def current_date(bank) -> date:
    """The open business day, else the latest one, else today."""
    day = (
        BusinessDay.objects.filter(bank=bank, status=BusinessDayStatus.OPEN).first()
        or BusinessDay.objects.filter(bank=bank).order_by("-date").first()
    )
    return day.date if day else timezone.localdate()


def date_range(bank, date_from: date | None, date_to: date | None, *, days: int | None = None):
    """Resolve an optional range: end defaults to the current business date, start to the
    first day of that month (or `days` - 1 before the end)."""
    end = date_to or current_date(bank)
    start = date_from or (end - timedelta(days=days - 1) if days else end.replace(day=1))
    if start > end:
        raise bad("date_from must not be after date_to")
    return start, end


def branch_of(bank):
    return Branch.objects.filter(bank=bank).order_by("code").first()


def new_report(ctx: Ctx, slug: str, title: str, period: str = "", **kw) -> Report:
    branch = branch_of(ctx.bank)
    return Report(
        slug=slug,
        title=title,
        bank_name=ctx.bank.name,
        branch=f"{branch.name} ({branch.code})" if branch else "",
        period=period,
        generated_at=timezone.now(),
        generated_by=(ctx.user.full_name or ctx.user.username) if ctx.user else "",
        **kw,
    )


def person(member) -> str:
    return (member.user.full_name or member.user.username) if member else ""


def gl_nets(bank, *, date_from=None, date_to=None, currency=None) -> dict:
    """Net debit (Dr - Cr) per (gl_account_id, currency) over posted journal lines of the
    bank, optionally limited to a business-date range."""
    qs = JournalLine.objects.filter(entry__bank=bank)
    if date_from:
        qs = qs.filter(entry__business_date__gte=date_from)
    if date_to:
        qs = qs.filter(entry__business_date__lte=date_to)
    if currency:
        qs = qs.filter(currency=currency)
    out: dict = {}
    for row in qs.values("gl_account_id", "currency").annotate(d=Sum("debit"), c=Sum("credit")):
        out[(row["gl_account_id"], row["currency"])] = (row["d"] or ZERO) - (row["c"] or ZERO)
    return out


def side_amount(net: Decimal, debit_normal: bool) -> Decimal:
    """Balance in the account's normal side."""
    return net if debit_normal else -net


def report_currencies(bank, currency=None, date_to=None) -> list[str]:
    """Currencies a report lists. An explicit `currency` is always honoured. When SOS is off
    platform-wide, SOS is dropped unless the bank has SOS activity (any journal line other than the
    provisioned opening capital), so history stays readable."""
    if currency:
        return [check_currency(currency)]
    out = sorted(CURRENCIES)
    if "SOS" in out and "SOS" not in enabled_currencies():
        qs = JournalLine.objects.filter(entry__bank=bank, currency="SOS").exclude(
            entry__source_type="opening_capital"
        )
        if date_to:
            qs = qs.filter(entry__business_date__lte=date_to)
        if not qs.exists():
            out.remove("SOS")
    return out
