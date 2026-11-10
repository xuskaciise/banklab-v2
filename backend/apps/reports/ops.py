"""Operational reports: branch daily report and the transaction journal."""

from collections import defaultdict
from datetime import date
from uuid import UUID

from django.db.models import Count, Sum

from apps.banking.models import (
    HolderType,
    TellerSession,
    TellerSessionStatus,
    Transaction,
    TxnStatus,
    TxnType,
    Vault,
)
from apps.ledger.models import JournalLine
from apps.ledger.services import CURRENCIES

from .ctx import Ctx, bad, check_currency, current_date, new_report, person
from .doc import ZERO, Column, Report, Section

TYPES = (
    TxnType.CASH_DEPOSIT,
    TxnType.CASH_WITHDRAWAL,
    TxnType.CHEQUE_WITHDRAWAL,
    TxnType.TRANSFER,
)
LABEL = dict(TxnType.choices)


def _txns(ctx: Ctx, day: date):
    qs = Transaction.objects.filter(bank=ctx.bank, business_date=day)
    return qs.filter(created_by=ctx.member) if ctx.own_only else qs


def _cash_as_of(bank, holder_type, holder_ids, day) -> dict:
    """Cash per (holder_id, currency) at the end of `day`, from the journal."""
    out: dict = defaultdict(lambda: ZERO)
    rows = (
        JournalLine.objects.filter(
            entry__bank=bank,
            cash_holder_type=holder_type,
            cash_holder_id__in=holder_ids,
            entry__business_date__lte=day,
        )
        .values("cash_holder_id", "currency")
        .annotate(d=Sum("debit"), c=Sum("credit"))
    )
    for r in rows:
        out[(r["cash_holder_id"], r["currency"])] = (r["d"] or ZERO) - (r["c"] or ZERO)
    return out


def _by_type_section(txns) -> tuple[Section, int]:
    posted = (
        txns.filter(status=TxnStatus.POSTED, type__in=TYPES)
        .values("type", "currency")
        .annotate(n=Count("id"), total=Sum("amount"))
        .order_by("currency", "type")
    )
    rows, totals = [], defaultdict(lambda: [0, ZERO])
    for r in posted:
        rows.append(
            {
                "item": LABEL[r["type"]],
                "currency": r["currency"],
                "count": r["n"],
                "amount": r["total"],
            }
        )
        totals[r["currency"]][0] += r["n"]
        totals[r["currency"]][1] += r["total"]
    for cur in sorted(totals):
        n, amount = totals[cur]
        rows.append(
            {"item": "Total posted", "currency": cur, "count": n, "amount": amount,
             "style": "total"}
        )
    reversed_ = (
        txns.filter(status=TxnStatus.REVERSED)
        .values("currency")
        .annotate(n=Count("id"), total=Sum("amount"))
        .order_by("currency")
    )
    for r in reversed_:
        rows.append(
            {
                "item": "Reversed (originals)",
                "currency": r["currency"],
                "count": r["n"],
                "amount": r["total"],
                "style": "subtotal",
            }
        )
    cols = [
        Column("item", "Type", weight=4),
        Column("currency", "Currency", weight=1.5),
        Column("count", "Count", "int", 1),
        Column("amount", "Amount", "money", 2.5),
    ]
    return Section("Transactions by type", cols, rows), sum(v[0] for v in totals.values())


def branch_daily(ctx: Ctx, business_date: date | None = None) -> Report:
    """Own-only readers (teller, CSO) get the report limited to their own transactions and
    tills, without the vault; manager, accountant and instructor see the whole bank."""
    day = business_date or current_date(ctx.bank)
    report = new_report(ctx, "branch-daily", "Branch Daily Report", f"Business date {day:%d %b %Y}")
    section, count = _by_type_section(_txns(ctx, day))
    report.sections.append(section)
    report.summary.append(("Posted transactions", count, "int"))
    sessions = TellerSession.objects.filter(bank=ctx.bank, business_date=day).exclude(
        status=TellerSessionStatus.CANCELLED
    )
    if ctx.own_only:
        sessions = sessions.filter(teller_member=ctx.member)
    sessions = list(sessions.select_related("till", "teller_member__user").order_by("till__code"))
    cash = _cash_as_of(ctx.bank, HolderType.TELLER_SESSION, [s.pk for s in sessions], day)
    rows = [
        {
            "teller": person(s.teller_member),
            "till": s.till.code,
            "status": s.get_status_display(),
            "currency": cur,
            "cash": cash[(s.pk, cur)],
        }
        for s in sessions
        for cur in sorted(CURRENCIES)
    ]
    cols = [
        Column("teller", "Teller", weight=3),
        Column("till", "Till", weight=1),
        Column("status", "Status", weight=2),
        Column("currency", "Currency", weight=1.5),
        Column("cash", "Cash", "money", 2.5),
    ]
    report.sections.append(Section("Teller positions (cash at end of day)", cols, rows))
    if not ctx.own_only:
        vaults = list(Vault.objects.filter(bank=ctx.bank).select_related("branch"))
        cash = _cash_as_of(ctx.bank, HolderType.VAULT, [v.pk for v in vaults], day)
        rows = [
            {
                "branch": f"{v.branch.name} ({v.branch.code})",
                "currency": cur,
                "cash": cash[(v.pk, cur)],
            }
            for v in vaults
            for cur in sorted(CURRENCIES)
        ]
        cols = [
            Column("branch", "Branch", weight=4),
            Column("currency", "Currency", weight=1.5),
            Column("cash", "Cash", "money", 2.5),
        ]
        report.sections.append(Section("Vault position (cash at end of day)", cols, rows))
    return report


def _filtered(ctx, day, type, status, currency, teller_id):
    qs = _txns(ctx, day)
    if type:
        if type not in TxnType.values:
            raise bad(f"Type must be one of: {', '.join(TxnType.values)}")
        qs = qs.filter(type=type)
    if status:
        if status not in TxnStatus.values:
            raise bad(f"Status must be one of: {', '.join(TxnStatus.values)}")
        qs = qs.filter(status=status)
    if check_currency(currency):
        qs = qs.filter(currency=currency)
    if teller_id:
        qs = qs.filter(created_by_id=teller_id)
    return qs.select_related("account__customer", "counter_account", "created_by__user")


def journal(
    ctx: Ctx,
    business_date: date | None = None,
    type: str | None = None,
    status: str | None = None,
    currency: str | None = None,
    teller_id: UUID | None = None,
) -> Report:
    """All transactions of one business date; own-only readers see only their own."""
    day = business_date or current_date(ctx.bank)
    txns = list(_filtered(ctx, day, type, status, currency, teller_id).order_by("created_at"))
    status_label = dict(TxnStatus.choices)
    rows, totals = [], defaultdict(lambda: ZERO)
    for t in txns:
        counter = t.counter_account
        rows.append(
            {
                "time": f"{t.created_at:%H:%M}",
                "ref": t.ref_no,
                "type": LABEL.get(t.type, t.type),
                "status": status_label.get(t.status, t.status),
                "account": str(t.account.account_no).zfill(8),
                "customer": t.account.customer.display_name,
                "counter": str(counter.account_no).zfill(8) if counter else "",
                "currency": t.currency,
                "amount": t.amount,
                "by": person(t.created_by),
            }
        )
        if t.status == TxnStatus.POSTED and t.type != TxnType.REVERSAL:
            totals[t.currency] += t.amount
    for cur in sorted(totals):
        rows.append(
            {"ref": f"Total posted {cur}", "currency": cur, "amount": totals[cur],
             "style": "total"}
        )
    report = new_report(
        ctx,
        "transaction-journal",
        "Transaction Journal",
        f"Business date {day:%d %b %Y}",
        landscape=True,
    )
    cols = [
        Column("time", "Time", weight=0.9),
        Column("ref", "Reference", weight=2.4),
        Column("type", "Type", weight=1.8),
        Column("status", "Status", weight=1.5),
        Column("account", "Account", weight=1.2),
        Column("customer", "Customer", weight=2.5),
        Column("counter", "To account", weight=1.2),
        Column("currency", "Cur.", weight=0.8),
        Column("amount", "Amount", "money", 1.6),
        Column("by", "Served by", weight=2),
    ]
    report.sections.append(Section("Transactions", cols, rows))
    report.summary.append(("Transactions listed", len(txns), "int"))
    return report
