from datetime import date, datetime, time, timedelta
from uuid import UUID

from django.utils import timezone
from ninja import Query, Router, Schema
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate

from apps.accounts.models import PlatformRole

from .models import AuditLog

router = Router(tags=["audit"])
FILTERS = Query(...)


class AuditFilters(Schema):
    action: str | None = None
    actor: str | None = None  # actor username
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


class AuditPagination(PageNumberPagination):
    page_size = 50


@router.get("", response=list[AuditOut], operation_id="audit_list")
@paginate(AuditPagination, page_size=50)
def audit_list(request, filters: AuditFilters = FILTERS):
    # TODO(1.3): instructors see their sessions, managers their own bank.
    if request.user.platform_role != PlatformRole.ADMIN:
        raise HttpError(403, "Not allowed")
    qs = (
        AuditLog.objects.select_related("actor")
        .filter(institution_id=request.user.institution_id)
        .order_by("-at", "-id")
    )
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
