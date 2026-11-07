from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.utils import timezone
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate

from apps.accounts.models import PlatformRole
from apps.lab.models import RoleAssignment
from apps.rbac import services as rbac

from .models import AuditLog

router = Router(tags=["audit"])
FILTERS = Query(...)


class AuditFilters(Schema):
    action: str | None = None
    actor: str | None = None  # actor username
    session_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None  # inclusive


class AuditOut(Schema):
    id: UUID
    actor_username: str | None = None
    actor_role: str
    action: str
    entity_type: str
    entity_id: str
    before: dict | list | None = None
    after: dict | list | None = None
    ip: str
    session_id: UUID | None = None
    bank_id: UUID | None = None
    at: datetime

    @staticmethod
    def resolve_actor_username(obj):
        return obj.actor.username if obj.actor_id else None


def _scoped(request, qs):
    """Rows the caller may see: admin all, instructor own classes' sessions, manager own bank."""
    user = request.user
    qs = qs.filter(institution_id=user.institution_id)
    if user.platform_role == PlatformRole.ADMIN:
        return qs
    if user.platform_role == PlatformRole.INSTRUCTOR:
        return qs.filter(session__lab_class__instructor=user)
    if user.platform_role == PlatformRole.STUDENT:
        bank_ids = []
        assignments = RoleAssignment.objects.select_related(
            "session_member__session"
        ).filter(
            session_member__user=user,
            session_member__bank__isnull=False,
            active_to__isnull=True,
            role="manager",
            session_member__session__status__in=["active", "archived"],
        )
        for a in assignments:
            member = a.session_member
            if rbac.role_has_permission("manager", "audit.view", session=member.session):
                bank_ids.append(member.bank_id)
        if bank_ids:
            return qs.filter(bank_id__in=bank_ids)
    raise HttpError(403, "Not allowed")


class AuditPagination(PageNumberPagination):
    page_size = 50


@router.get("", response=list[AuditOut], operation_id="audit_list")
@paginate(AuditPagination, page_size=50)
def audit_list(request, filters: AuditFilters = FILTERS):
    qs = _scoped(request, AuditLog.objects.select_related("actor")).order_by("-at", "-id")
    if filters.session_id:
        qs = qs.filter(session_id=filters.session_id)
    if filters.action:
        qs = qs.filter(action=filters.action)
    if filters.actor:
        qs = qs.filter(actor__username=filters.actor)
    tz = timezone.get_current_timezone()
    if filters.date_from:
        start = datetime.combine(filters.date_from, time.min)
        qs = qs.filter(at__gte=timezone.make_aware(start, tz))
    if filters.date_to:
        end = datetime.combine(filters.date_to + timedelta(days=1), time.min)
        qs = qs.filter(at__lt=timezone.make_aware(end, tz))
    return qs
