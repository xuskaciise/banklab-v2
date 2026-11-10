"""Teller cash report: one teller session, per currency."""

from collections import defaultdict
from uuid import UUID

from apps.banking.models import (
    CashCount,
    CashCountKind,
    CashPosition,
    CashTransfer,
    HolderType,
    TellerSession,
    Transaction,
    TxnType,
)
from apps.ledger.models import JournalLine

from .ctx import Ctx, new_report, not_found, person
from .doc import ZERO, Column, Report, Section

CLOSE_REASON = "Till close"  # reason text of the cash transfer that returns the till to the vault


def _session(ctx: Ctx, session_id: UUID) -> TellerSession:
    ts = (
        TellerSession.objects.select_related("till__branch", "teller_member__user")
        .filter(bank=ctx.bank, pk=session_id)
        .first()
    )
    # own-only readers get 404 for other tellers' sessions (same as "does not exist")
    if ts is None or (ctx.own_only and ts.teller_member_id != ctx.member.pk):
        raise not_found("Teller session")
    return ts


def _currency_block(ts, cur, lines, txn_type, transfer_reason, transfers) -> tuple[list, list]:
    def is_float(entry_id) -> bool:
        """Vault float requested with the till-open request, i.e. before the till opened."""
        t = transfers.get(entry_id)
        return bool(
            t
            and t.from_type == HolderType.VAULT
            and t.requested_by_id == ts.teller_member_id
            and (ts.opened_at is None or t.created_at < ts.opened_at)
        )

    opening = over_short = closing_return = tin = tout = ZERO
    by_type: dict[str, list] = defaultdict(lambda: [0, ZERO, ZERO])  # count, in, out
    for ln in lines:
        entry = ln.entry
        if entry.source_type == "cash_transfer":
            net = ln.debit - ln.credit
            if transfer_reason.get(entry.pk) == CLOSE_REASON:
                closing_return += net
            elif is_float(entry.pk):
                opening += net  # float received before the till opened
            else:
                tin += ln.debit
                tout += ln.credit
        elif entry.source_type == "till_close":
            over_short += ln.debit - ln.credit
        else:
            row = by_type[txn_type.get(entry.pk, entry.source_type)]
            row[0] += 1
            row[1] += ln.debit
            row[2] += ln.credit
    labels = dict(TxnType.choices)
    moves = [
        {"item": labels.get(t, t), "count": n, "cash_in": i, "cash_out": o}
        for t, (n, i, o) in sorted(by_type.items())
    ]
    moves.append({"item": "Transfers received (vault / teller)", "cash_in": tin})
    moves.append({"item": "Transfers sent (vault / teller)", "cash_out": tout})
    cash_in = sum((r[1] for r in by_type.values()), ZERO)
    cash_out = sum((r[2] for r in by_type.values()), ZERO)
    moves.append({"item": "Total", "cash_in": cash_in + tin, "cash_out": cash_out + tout,
                  "style": "total"})
    expected = opening + cash_in - cash_out + tin - tout
    count = (
        CashCount.objects.filter(teller_session=ts, kind=CashCountKind.CLOSE, currency=cur)
        .order_by("-attempt")
        .first()
    )
    on_hand = (
        CashPosition.objects.filter(
            bank=ts.bank, holder_type=HolderType.TELLER_SESSION, holder_id=ts.pk, currency=cur
        )
        .values_list("balance", flat=True)
        .first()
    ) or ZERO
    pos = [
        {"item": "Opening cash (float from vault)", "amount": opening},
        {"item": "Expected closing cash", "amount": expected, "style": "subtotal"},
    ]
    if count:
        pos += [
            {"item": "Counted cash at close", "amount": count.counted_total},
            {"item": "Difference (counted - expected)", "amount": count.counted_total - expected},
        ]
    pos.append({"item": "Over / short posted at close", "amount": over_short})
    pos.append({"item": "Returned to vault at close", "amount": -closing_return})
    pos.append({"item": "Cash on hand now", "amount": on_hand, "style": "total"})
    return moves, pos


def teller_cash(ctx: Ctx, teller_session_id: UUID) -> Report:
    ts = _session(ctx, teller_session_id)
    lines = list(
        JournalLine.objects.filter(
            entry__bank=ctx.bank,
            cash_holder_type=HolderType.TELLER_SESSION,
            cash_holder_id=ts.pk,
        )
        .select_related("entry")
        .order_by("entry__entry_no", "id")
    )
    entry_ids = {ln.entry_id for ln in lines}
    txn_type = dict(
        Transaction.objects.filter(bank=ctx.bank, journal_entry_id__in=entry_ids).values_list(
            "journal_entry_id", "type"
        )
    )
    transfers = {
        t.journal_entry_id: t
        for t in CashTransfer.objects.filter(bank=ctx.bank, journal_entry_id__in=entry_ids)
    }
    transfer_reason = {k: t.reason for k, t in transfers.items()}
    report = new_report(
        ctx, "teller-cash", "Teller Cash Report", f"Business date {ts.business_date:%d %b %Y}"
    )
    report.summary += [
        ("Teller", person(ts.teller_member), "text"),
        ("Till", f"{ts.till.code} ({ts.till.branch.name})", "text"),
        ("Session status", ts.get_status_display(), "text"),
    ]
    move_cols = [
        Column("item", "Item", weight=5),
        Column("count", "Count", "int", 1),
        Column("cash_in", "Cash in", "money", 2),
        Column("cash_out", "Cash out", "money", 2),
    ]
    pos_cols = [Column("item", "Item", weight=5), Column("amount", "Amount", "money", 3)]
    for cur in sorted({ln.currency for ln in lines}):
        moves, pos = _currency_block(
            ts,
            cur,
            [ln for ln in lines if ln.currency == cur],
            txn_type,
            transfer_reason,
            transfers,
        )
        report.sections.append(Section(f"Cash movements - {cur}", move_cols, moves, currency=cur))
        report.sections.append(Section(f"Cash position - {cur}", pos_cols, pos, currency=cur))
    return report


