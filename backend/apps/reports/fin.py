"""Financial statements from the journal: Trial Balance, Balance Sheet, Income Statement."""

from datetime import date
from decimal import Decimal

from apps.ledger.models import AccountType, GLAccount

from .ctx import (
    Ctx,
    check_currency,
    current_date,
    date_range,
    gl_nets,
    new_report,
    report_currencies,
    side_amount,
)
from .doc import ZERO, Column, Report, Section

ACCOUNT_COLS = [Column("code", "Code", weight=1), Column("name", "Account", weight=4)]


def _currencies(ctx, currency, date_to=None) -> list[str]:
    return report_currencies(ctx.bank, currency, date_to)


def _postable(ctx: Ctx):
    return list(GLAccount.objects.filter(bank=ctx.bank, postable=True).order_by("code"))


def trial_balance(ctx: Ctx, as_of: date | None = None, currency: str | None = None) -> Report:
    as_of = as_of or current_date(ctx.bank)
    nets = gl_nets(ctx.bank, date_to=as_of, currency=check_currency(currency))
    accounts = _postable(ctx)
    report = new_report(ctx, "trial-balance", "Trial Balance", f"As of {as_of:%d %b %Y}")
    for cur in _currencies(ctx, currency, as_of):
        rows, total_dr, total_cr = [], ZERO, ZERO
        for acc in accounts:
            net = nets.get((acc.pk, cur), ZERO)
            dr, cr = (net, ZERO) if net > 0 else (ZERO, -net)
            total_dr += dr
            total_cr += cr
            rows.append({"code": acc.code, "name": acc.name, "debit": dr, "credit": cr})
        rows.append({"name": "Total", "debit": total_dr, "credit": total_cr, "style": "total"})
        money_cols = [Column("debit", "Debit", "money"), Column("credit", "Credit", "money")]
        cols = [*ACCOUNT_COLS, *money_cols]
        report.sections.append(Section(f"Trial Balance - {cur}", cols, rows, currency=cur))
        report.summary.append((f"{cur} total debit", total_dr, "money"))
        report.summary.append((f"{cur} total credit", total_cr, "money"))
        report.summary.append((f"{cur} difference", total_dr - total_cr, "money"))
    return report


def _group(rows, title, accounts, nets, cur, total_label) -> Decimal:
    rows.append({"name": title, "style": "header"})
    total = ZERO
    for acc in accounts:
        amount = side_amount(nets.get((acc.pk, cur), ZERO), acc.debit_normal)
        if amount:
            rows.append({"code": acc.code, "name": acc.name, "amount": amount})
        total += amount
    rows.append({"name": total_label, "amount": total, "style": "subtotal"})
    return total


def balance_sheet(ctx: Ctx, as_of: date | None = None, currency: str | None = None) -> Report:
    """Assets = Liabilities + Equity + (Income - Expenses). The system has no year-end close,
    so the result line is the cumulative Income - Expenses up to `as_of`."""
    as_of = as_of or current_date(ctx.bank)
    nets = gl_nets(ctx.bank, date_to=as_of, currency=check_currency(currency))
    accounts = _postable(ctx)
    by_type = {t: [a for a in accounts if a.type == t] for t in AccountType.values}
    report = new_report(ctx, "balance-sheet", "Balance Sheet", f"As of {as_of:%d %b %Y}")
    cols = [*ACCOUNT_COLS, Column("amount", "Amount", "money")]
    for cur in _currencies(ctx, currency, as_of):
        rows: list[dict] = []
        assets = _group(rows, "ASSETS", by_type["asset"], nets, cur, "Total assets")
        liabilities = _group(
            rows, "LIABILITIES", by_type["liability"], nets, cur, "Total liabilities"
        )
        equity = _group(rows, "EQUITY", by_type["equity"], nets, cur, "Total equity")
        income = sum(
            (side_amount(nets.get((a.pk, cur), ZERO), False) for a in by_type["income"]), ZERO
        )
        expense = sum(
            (side_amount(nets.get((a.pk, cur), ZERO), True) for a in by_type["expense"]), ZERO
        )
        result = income - expense
        rows.append({"name": "Current period result (Income - Expenses)", "amount": result})
        right = liabilities + equity + result
        label = "Total liabilities + equity + result"
        rows.append({"name": label, "amount": right, "style": "total"})
        report.sections.append(Section(f"Balance Sheet - {cur}", cols, rows, currency=cur))
        report.summary.append((f"{cur} total assets", assets, "money"))
        report.summary.append((f"{cur} liabilities + equity + result", right, "money"))
        report.summary.append((f"{cur} difference", assets - right, "money"))
    return report


def income_statement(
    ctx: Ctx,
    date_from: date | None = None,
    date_to: date | None = None,
    currency: str | None = None,
) -> Report:
    start, end = date_range(ctx.bank, date_from, date_to)
    nets = gl_nets(ctx.bank, date_from=start, date_to=end, currency=check_currency(currency))
    accounts = _postable(ctx)
    report = new_report(
        ctx, "income-statement", "Income Statement", f"{start:%d %b %Y} to {end:%d %b %Y}"
    )
    cols = [*ACCOUNT_COLS, Column("amount", "Amount", "money")]
    for cur in _currencies(ctx, currency, end):
        rows: list[dict] = []
        income = _group(
            rows, "INCOME", [a for a in accounts if a.type == AccountType.INCOME], nets, cur,
            "Total income",
        )
        expense = _group(
            rows, "EXPENSES", [a for a in accounts if a.type == AccountType.EXPENSE], nets, cur,
            "Total expenses",
        )
        rows.append({"name": "Net income", "amount": income - expense, "style": "total"})
        report.sections.append(Section(f"Income Statement - {cur}", cols, rows, currency=cur))
        report.summary.append((f"{cur} total income", income, "money"))
        report.summary.append((f"{cur} total expenses", expense, "money"))
        report.summary.append((f"{cur} net income", income - expense, "money"))
    return report
