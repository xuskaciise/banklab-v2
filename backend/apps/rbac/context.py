from dataclasses import dataclass
from functools import wraps

from ninja.errors import HttpError

from . import services

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ALWAYS_ALL_ROLES = {"manager", "vault_custodian", "accountant"}


@dataclass
class BankContext:
    session: object
    bank: object
    member: object
    role: str | None


def effective_visibility(session, member, role: str | None) -> str:
    """Row visibility for a member: "own" or "all".

    Exams force "own". Otherwise manager, vault custodian and accountant always see the
    whole bank; others use the member override, then the session default.
    """
    if session.kind == "exam":
        return "own"
    if role in ALWAYS_ALL_ROLES:
        return "all"
    return member.visibility_override or session.default_visibility


def resolve_bank_context(request, session_id, *, require_role: bool = True) -> BankContext:
    """Resolve the caller's membership, bank and active role in `session_id`.

    403 when not a member / not placed / no active role; 409 when the session is not
    active, except that archived sessions stay readable (GET/HEAD/OPTIONS).
    """
    from apps.lab.models import RoleAssignment, Session, SessionMember, SessionStatus

    user = getattr(request, "user", None)
    if session_id is None or user is None or not getattr(user, "is_authenticated", False):
        raise HttpError(403, "Not allowed")
    member = (
        SessionMember.objects.select_related("session", "bank")
        .filter(session_id=session_id, user=user, user__is_active=True)
        .first()
    )
    if member is None:
        raise HttpError(403, "Not allowed")
    session: Session = member.session
    if session.status == SessionStatus.DRAFT:
        raise HttpError(409, "Session is not open yet")
    if session.status == SessionStatus.ARCHIVED and request.method not in SAFE_METHODS:
        raise HttpError(409, "Session is archived (read-only)")
    assignment = RoleAssignment.objects.filter(
        session_member=member, active_to__isnull=True
    ).first()
    role = assignment.role if assignment else None
    if require_role and (role is None or member.bank_id is None):
        raise HttpError(403, "Not allowed")
    request.lab_session = session
    request.bank = member.bank
    request.session_member = member
    request.bank_role = role
    request.visibility = effective_visibility(session, member, role)
    return BankContext(session=session, bank=member.bank, member=member, role=role)


def get_active_bank_role(request) -> str | None:
    """Return the caller's active bank role in the session of this request, or None.

    The session comes from the view's `session_id` path kwarg (stored on the request by
    `require_bank_permission`). Sets request.lab_session / bank / session_member /
    bank_role as a side effect.
    """
    session_id = getattr(request, "_banklab_session_id", None)
    if session_id is None:
        match = getattr(request, "resolver_match", None)
        session_id = match.kwargs.get("session_id") if match else None
    return resolve_bank_context(request, session_id).role


def require_bank_permission(code: str):
    """Decorator for Ninja views under `/api/s/{session_id}/...`.

    403 unless the caller's active bank role holds `code` (session overrides applied).
    Sets `request.lab_session`, `request.bank`, `request.session_member`,
    `request.bank_role`, `request.visibility` and `request.permission_scope`
    ("all" | "own": "own" when either the permission or the visibility is own-only).
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            request._banklab_session_id = kwargs.get("session_id")
            role = get_active_bank_role(request)
            session = getattr(request, "lab_session", None)
            scope = services.permission_scope(role, code, session=session) if role else None
            if scope is None:
                raise HttpError(403, "Not allowed")
            request.bank_role = role
            visibility = getattr(request, "visibility", "all")
            request.permission_scope = "own" if "own" in (scope, visibility) else "all"
            return func(request, *args, **kwargs)

        return wrapper

    return decorator
