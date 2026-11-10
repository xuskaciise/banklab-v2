"""Running-balance reports: customer account statement and GL ledger."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from django.db.models import Sum

from apps.banking.models import Transaction
from apps.ledger.models import GLAccount, JournalLine
from apps.products import services as products
from apps.products.models import Account

from .ctx import Ctx, bad, check_currency, date_range, new_report, not_found
from .doc import ZERO, Column, Report, Section


def _refs(bank, entry_ids) -> dict:
    """Transaction reference per journal entry id (reversals included)."""
    return dict(
        Transaction.objects.filter(bank=bank, journal_entry_id__in=entry_ids).values_list(
            "journal_entry_id", "ref_no"
        )
    )


def _opening(lines, start: date, credit_normal: bool) -> Decimal:
    agg = lines.filter(entry__business_date__lt=start).aggregate(d=Sum("debit"), c=Sum("credit"))
    d, c = agg["d"] or ZERO, agg["c"] or ZERO
    return (c - d) if credit_normal else (d - c)


def _running(bank, lines, start, end, opening, credit_normal, cur, title, summary_head, report):
    rows = [
        {"date": start, "description": "Opening balance", "balance": opening, "style": "subtotal"}
    ]
    found = list(
        lines.filter(entry__business_date__gte=start, entry__business_date__lte=end)
        .select_related("entry")
        .order_by("entry__business_date", "entry__entry_no", "id")
    )
    refs = _refs(bank, {ln.entry_id for ln in found})
    balance, total_dr, total_cr = opening, ZERO, ZERO
    for ln in found:
        balance += (ln.credit - ln.debit) if credit_normal else (ln.debit - ln.credit)
        total_dr += ln.debit
        total_cr += ln.credit
        rows.append(
            {
                "date": ln.entry.business_date,
                "ref": refs.get(ln.entry_id, f"JE-{ln.entry.entry_no}"),
                "description": ln.entry.description,
                "debit": ln.debit or None,
                "credit": ln.credit or None,
                "balance": balance,
            }
        )
    rows.append(
        {"description": "Closing balance", "debit": total_dr, "credit": total_cr,
         "balance": balance, "style": "total"}
    )
    cols = [
        Column("date", "Date", "date", 1.1),
        Column("ref", "Reference", weight=2),
        Column("description", "Description", weight=4),
        Column("debit", "Debit", "money", 1.5),
        Column("credit", "Credit", "money", 1.5),
        Column("balance", "Balance", "money", 1.6),
    ]
    report.sections.append(Section(title, cols, rows, currency=cur))
    report.summary += [
        *summary_head,
        ("Opening balance", opening, "money"),
        ("Total debit", total_dr, "money"),
        ("Total credit", total_cr, "money"),
        ("Closing balance", balance, "money"),
    ]
    return report


def account_statement(
    ctx: Ctx, account_id: UUID, date_from: date | None = None, date_to: date | None = None
) -> Report:
    """Customer account: balance moves with credits (deposits) up and debits down."""
    if ctx.member is not None:
        qs = products.visible_accounts(ctx.member, ctx.scope)
    else:
        qs = Account.objects.filter(bank=ctx.bank)
    account = qs.select_related("customer", "product").filter(pk=account_id).first()
    if account is None:
        raise not_found("Account")
    start, end = date_range(ctx.bank, date_from, date_to)
    lines = JournalLine.objects.filter(
        entry__bank=ctx.bank, account_id=account.pk, currency=account.currency
    )
    no = str(account.account_no).zfill(8)
    report = new_report(
        ctx, "account-statement", "Account Statement", f"{start:%d %b %Y} to {end:%d %b %Y}",
        landscape=False,
    )
    head = [
        ("Account", no, "text"),
        ("Customer", account.customer.display_name, "text"),
        ("Product", account.product.name, "text"),
        ("Currency", account.currency, "text"),
    ]
    return _running(
        ctx.bank, lines, start, end, _opening(lines, start, True), True, account.currency,
        f"Statement of account {no}", head, report,
    )


def gl_ledger(
    ctx: Ctx,
    gl_account_id: UUID,
    currency: str,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Report:
    """One GL account (and its children for a header account) in one currency."""
    if not check_currency(currency):
        raise bad("currency is required (USD or SOS)")
    account = GLAccount.objects.filter(bank=ctx.bank, pk=gl_account_id).first()
    if account is None:
        raise not_found("GL account")
    ids, frontier = {account.pk}, [account.pk]
    while frontier:
        frontier = list(
            GLAccount.objects.filter(bank=ctx.bank, parent_id__in=frontier)
            .exclude(pk__in=ids)
            .values_list("pk", flat=True)
        )
        ids.update(frontier)
    start, end = date_range(ctx.bank, date_from, date_to)
    lines = JournalLine.objects.filter(
        entry__bank=ctx.bank, gl_account_id__in=ids, currency=currency
    )
    report = new_report(
        ctx, "gl-ledger", "General Ledger", f"{start:%d %b %Y} to {end:%d %b %Y}"
    )
    head = [
        ("GL account", f"{account.code} {account.name}", "text"),
        ("Currency", currency, "text"),
    ]
    return _running(
        ctx.bank, lines, start, end, _opening(lines, start, not account.debit_normal),
        not account.debit_normal, currency, f"Ledger {account.code} {account.name} - {currency}",
        head, report,
    )
