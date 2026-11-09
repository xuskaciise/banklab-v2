"""End of day by the Manager (transactions.md E2). No journal entries are posted.

`eod_status` is a read (permission `eod.run`, allowed on archived sessions). `close_day`
re-runs every check under locks and, when all pass, closes the open business day and opens
the next calendar date. Lock order: lab session -> bank row -> business day.
"""

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from apps.audit import services as audit
from apps.ledger import services as ledger
from apps.ledger.models import JournalLine
from apps.rbac import services as rbac

from . import eod_summary as summary
from . import services as banking
from . import txn_core as core
from .models import (
    BusinessDay,
    BusinessDayStatus,
    CashTransfer,
    TellerSession,
    TellerSessionStatus,
    Transaction,
    TransferStatus,
    TxnStatus,
)

PERM = "eod.run"
ZERO = Decimal("0.00")
_DONE = (TellerSessionStatus.CLOSED, TellerSessionStatus.CANCELLED)


def _require(member) -> str:
    if member.bank_id is None:
        raise rbac.PermissionDenied("Not allowed")
    role = banking._role_of(member)
    if not rbac.role_has_permission(role, PERM, session=member.session):
        raise rbac.PermissionDenied("Not allowed")
    return role


def _check(code, label, ok, detail, items=None):
    items = items or []
    return {
        "code": code,
        "label": label,
        "ok": ok,
        "detail": detail,
        "count": len(items),
        "items": items,
    }


def _checks(bank, day) -> list[dict]:
    open_ts = (
        TellerSession.objects.filter(bank=bank)
        .exclude(status__in=_DONE)
        .select_related("teller_member__user", "till")
        .order_by("open_requested_at")
    )
    sessions = [
        {
            "id": str(ts.pk),
            "teller_name": ts.teller_member.user.full_name or ts.teller_member.user.username,
            "till_code": ts.till.code,
            "status": ts.status,
        }
        for ts in open_ts
    ]
    txns = Transaction.objects.filter(bank=bank, status=TxnStatus.PENDING_APPROVAL).count()
    transfers = CashTransfer.objects.filter(
        bank=bank, status__in=(TransferStatus.PENDING, TransferStatus.CUSTODIAN_APPROVED)
    ).count()
    pending = [
        {"kind": "transactions", "count": txns},
        {"kind": "cash_transfers", "count": transfers},
    ]
    recon = ledger.cash_reconciliation(bank)
    bad_recon = [r["currency"] for r in recon if not r["ok"]]
    totals = defaultdict(lambda: [ZERO, ZERO])
    for row in (
        JournalLine.objects.filter(entry__bank=bank)
        .values("currency")
        .annotate(d=Sum("debit"), c=Sum("credit"), n=Count("id"))
    ):
        totals[row["currency"]] = [row["d"] or ZERO, row["c"] or ZERO]
    unbalanced = sorted(cur for cur, (d, c) in totals.items() if d != c)
    return [
        _check(
            "teller_sessions_closed",
            "Every teller session of the day is closed",
            not sessions,
            f"{len(sessions)} teller session(s) still open" if sessions else "All closed",
            sessions,
        ),
        {
            **_check(
                "no_pending_approvals",
                "No pending transactions or cash transfers",
                txns + transfers == 0,
                f"{txns} transaction(s) and {transfers} cash transfer(s) pending"
                if txns + transfers
                else "Nothing pending",
                pending if txns + transfers else [],
            ),
            "count": txns + transfers,
        },
        _check(
            "cash_reconciliation",
            "Cash sub-ledger matches the general ledger",
            not bad_recon,
            f"Mismatch in {', '.join(bad_recon)}" if bad_recon else "Reconciled",
            [r for r in recon if not r["ok"]],
        ),
        _check(
            "trial_balance",
            "Trial balance balances per currency",
            not unbalanced,
            f"Out of balance in {', '.join(unbalanced)}" if unbalanced else "Balanced",
            [{"currency": c, "debit": totals[c][0], "credit": totals[c][1]} for c in unbalanced],
        ),
    ]


def _status(bank, day) -> dict:
    checks = _checks(bank, day)
    return {
        "business_date": day.date,
        "checks": checks,
        "can_close": all(c["ok"] for c in checks),
        "summary": summary.day_summary(bank, day),
        "recent_closings": summary.recent_closings(bank),
    }


def eod_status(member) -> dict:
    _require(member)
    day = core.open_day(member.bank_id)
    return _status(member.bank, day)


def close_day(member) -> dict:
    with transaction.atomic():
        session = banking._lock_session(member)  # archived / inactive guard
        role = _require(member)
        core.lock_bank(member.bank_id)  # serialise against postings
        day = (
            BusinessDay.objects.select_for_update()
            .filter(bank_id=member.bank_id, status=BusinessDayStatus.OPEN)
            .first()
        )
        if day is None:
            raise banking._conflict("day_closed", "The bank has no open business day")
        status = _status(member.bank, day)
        if not status["can_close"]:
            failed = [c["code"] for c in status["checks"] if not c["ok"]]
            raise banking._conflict(
                "eod_checks_failed", "End of day checks failed: " + ", ".join(failed)
            )
        day.status = BusinessDayStatus.CLOSED
        day.closed_by = member.user
        day.closed_at = timezone.now()
        day.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
        nxt = BusinessDay.objects.create(
            bank_id=member.bank_id, date=day.date + timedelta(days=1), status=BusinessDayStatus.OPEN
        )
        audit.record(
            "eod.closed",
            actor=member.user,
            actor_role=role,
            entity=("business_day", day.pk),
            before={"date": str(day.date), "status": "open"},
            after={"date": str(day.date), "status": "closed", "next_date": str(nxt.date)},
            session_id=session.pk,
            bank_id=member.bank_id,
            institution_id=session.lab_class.institution_id,
        )
        return {"closed_date": day.date, "business_date": nxt.date, "closed_at": day.closed_at}
