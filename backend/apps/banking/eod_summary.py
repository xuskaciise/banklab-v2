"""Read-only summary of the open business day for the End-of-Day screen (no postings)."""

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Sum

from . import services as banking
from .models import (
    BusinessDay,
    BusinessDayStatus,
    TellerSession,
    TellerSessionStatus,
    Transaction,
    TxnStatus,
    TxnType,
)

ZERO = Decimal("0.00")
_TYPES = (
    TxnType.CASH_DEPOSIT,
    TxnType.CASH_WITHDRAWAL,
    TxnType.CHEQUE_WITHDRAWAL,
    TxnType.TRANSFER,
)


def day_summary(bank, day) -> dict:
    """Counts and totals of the bank's transactions on `day`; posted ones only (reversal
    entries themselves are excluded, originals later reversed are counted separately)."""
    txns = Transaction.objects.filter(bank=bank, business_date=day.date)
    rows = (
        txns.filter(status=TxnStatus.POSTED, type__in=_TYPES)
        .values("type", "currency")
        .annotate(n=Count("id"), total=Sum("amount"))
        .order_by("type", "currency")
    )
    by_type = [
        {
            "type": r["type"],
            "currency": r["currency"],
            "count": r["n"],
            "amount": r["total"] or ZERO,
        }
        for r in rows
    ]
    sessions = TellerSession.objects.filter(bank=bank, business_date=day.date).exclude(
        status=TellerSessionStatus.CANCELLED
    )
    vault = defaultdict(lambda: ZERO)
    for branch in banking.vault_overview(bank)["branches"]:
        for pos in branch["positions"]:
            vault[pos["currency"]] += pos["balance"]
    return {
        "transactions_total": sum(r["count"] for r in by_type),
        "reversed_count": txns.filter(status=TxnStatus.REVERSED).count(),
        "by_type": by_type,
        "teller_sessions": {
            "closed": sessions.filter(status=TellerSessionStatus.CLOSED).count(),
            "total": sessions.count(),
        },
        "vault_balances": [{"currency": c, "amount": a} for c, a in sorted(vault.items())],
    }


def recent_closings(bank, limit: int = 5) -> list[dict]:
    days = (
        BusinessDay.objects.filter(bank=bank, status=BusinessDayStatus.CLOSED)
        .select_related("closed_by")
        .order_by("-closed_at", "-date")[:limit]
    )
    return [
        {
            "date": d.date,
            "closed_at": d.closed_at,
            "closed_by_name": (d.closed_by.full_name or d.closed_by.username)
            if d.closed_by
            else "",
        }
        for d in days
    ]
