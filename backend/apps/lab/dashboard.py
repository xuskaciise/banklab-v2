"""Instructor / admin dashboard (read-only, 1.13).

An instructor sees only the classes they teach; an admin sees every class of the institution.
"""

from collections import defaultdict

from django.db.models import Count

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.banking.models import (
    Approval,
    ApprovalStatus,
    BusinessDay,
    BusinessDayStatus,
    Transaction,
)

from . import services
from .models import Bank, Enrollment, Session, SessionMember, SessionStatus

RECENT_LIMIT = 20


def _name(user: User | None) -> str | None:
    return (user.full_name or user.username) if user else None


def staff_dashboard(actor: User) -> dict:
    classes = list(services.list_classes(actor))  # also enforces staff-only
    class_ids = [c.pk for c in classes]
    students = (
        Enrollment.objects.filter(lab_class_id__in=class_ids).values("user_id").distinct().count()
    )
    sessions = list(
        Session.objects.select_related("lab_class")
        .filter(lab_class_id__in=class_ids, status=SessionStatus.ACTIVE)
        .order_by("-opened_at", "-created_at")
    )
    ids = [s.pk for s in sessions]

    banks = dict(
        Bank.objects.filter(session_id__in=ids)
        .values("session_id")
        .annotate(n=Count("pk"))
        .values_list("session_id", "n")
    )
    members = dict(
        SessionMember.objects.filter(session_id__in=ids)
        .values("session_id")
        .annotate(n=Count("pk"))
        .values_list("session_id", "n")
    )
    pending = dict(
        Approval.objects.filter(bank__session_id__in=ids, status=ApprovalStatus.PENDING)
        .values("bank__session_id")
        .annotate(n=Count("pk"))
        .values_list("bank__session_id", "n")
    )
    # "Today" = the open business day of each bank.
    open_days = {
        (bank_id, d)
        for bank_id, d in BusinessDay.objects.filter(
            bank__session_id__in=ids, status=BusinessDayStatus.OPEN
        ).values_list("bank_id", "date")
    }
    bank_session = dict(Bank.objects.filter(session_id__in=ids).values_list("pk", "session_id"))
    today: dict = defaultdict(int)
    for bank_id, d, n in (
        Transaction.objects.filter(
            bank__session_id__in=ids, business_date__in={d for _, d in open_days}
        )
        .values("bank_id", "business_date")
        .annotate(n=Count("pk"))
        .values_list("bank_id", "business_date", "n")
    ):
        if (bank_id, d) in open_days:
            today[bank_session[bank_id]] += n

    events = (
        AuditLog.objects.filter(session_id__in=ids)
        .select_related("actor", "bank", "session")
        .order_by("-at")[:RECENT_LIMIT]
    )
    return {
        "counts": {
            "classes": len(classes),
            "active_sessions": len(sessions),
            "students": students,
        },
        "sessions": [
            {
                "id": s.pk,
                "name": s.name,
                "class_id": s.lab_class_id,
                "class_name": s.lab_class.name,
                "kind": s.kind,
                "learning_panel": s.learning_panel,
                "opened_at": s.opened_at,
                "banks_count": banks.get(s.pk, 0),
                "members_count": members.get(s.pk, 0),
                "today_transactions": today.get(s.pk, 0),
                "pending_approvals": pending.get(s.pk, 0),
            }
            for s in sessions
        ],
        "recent_activity": [
            {
                "id": e.pk,
                "at": e.at,
                "actor_name": _name(e.actor),
                "action": e.action,
                "bank_name": e.bank.name if e.bank_id else None,
                "session_id": e.session_id,
                "session_name": e.session.name if e.session_id else None,
            }
            for e in events
        ],
    }
