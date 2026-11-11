import hashlib
from uuid import UUID

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.middleware.csrf import CsrfViewMiddleware, get_token
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

from apps.audit import services as audit

from . import services
from .models import PlatformRole, User

router = Router(tags=["auth"])

MAX_ATTEMPTS_PER_USER_IP = 5
# One class (100-200 students) logs in from a single NAT IP at lecture start.
# TODO(1.15): tune per-IP caps once the reverse proxy and trusted X-Forwarded-For are in place.
MAX_ATTEMPTS_PER_IP = 300
THROTTLE_SECONDS = 300
MAX_ATTEMPTS_PER_ID = 20
THROTTLE_ID_SECONDS = 900
INVALID_LOGIN = "Invalid credentials"
SESSION_BACKEND = "django.contrib.auth.backends.ModelBackend"


class StaffLoginIn(Schema):
    username: str
    password: str


class StudentLoginIn(Schema):
    student_id: str
    password: str


class ChangePasswordIn(Schema):
    current_password: str
    new_password: str


class MeOut(Schema):
    id: UUID
    username: str
    full_name: str
    platform_role: str
    must_change_password: bool
    institution_name: str
    logo_url: str | None = None

    @staticmethod
    def resolve_institution_name(obj):
        return obj.institution.name

    @staticmethod
    def resolve_logo_url(obj):
        return "/api/institution/logo" if obj.institution.logo else None


class LoginOut(Schema):
    user: MeOut


class CsrfOut(Schema):
    csrf_token: str


def _enforce_csrf(request) -> None:
    """Ninja only checks CSRF for cookie auth; unauthenticated POSTs need it too."""
    reason = CsrfViewMiddleware(lambda r: HttpResponse()).process_view(request, None, (), {})
    if reason is not None:
        raise HttpError(403, "CSRF check failed")


def _client_ip(request) -> str:
    # TODO(1.15): behind the reverse proxy, derive the client IP from a trusted
    # X-Forwarded-For hop instead of REMOTE_ADDR.
    return request.META.get("REMOTE_ADDR", "unknown")


def _hit(key: str, timeout: int = THROTTLE_SECONDS) -> int:
    cache.add(key, 0, timeout)
    return cache.incr(key)


def _throttle(request, prefix: str, ident: str) -> tuple[str, str]:
    """Count the attempt (before checking credentials); return the per-ID+IP key."""
    ip = _client_ip(request)
    digest = hashlib.sha256(ident.lower().encode()).hexdigest()[:32]
    user_key = f"{prefix}:{digest}:{ip}"
    id_key = f"{prefix}-id:{digest}"
    ip_key = f"login-ip:{ip}"  # one per-IP budget shared by both endpoints
    # Count every attempt before authenticating so concurrent guesses cannot race past the cap.
    user_hits = _hit(user_key)
    id_hits = _hit(id_key, THROTTLE_ID_SECONDS)
    ip_hits = _hit(ip_key)
    if (
        user_hits > MAX_ATTEMPTS_PER_USER_IP
        or ip_hits > MAX_ATTEMPTS_PER_IP
        or id_hits > MAX_ATTEMPTS_PER_ID
    ):
        raise HttpError(429, "Too many login attempts. Try again later.")
    return user_key, id_key


def _login_failed(request, known: User | None, method: str) -> None:
    # Never store the typed values: only a resolved user id, else a bare marker.
    audit.record(
        "auth.login_failed",
        entity=("user", known.pk) if known else ("unknown_username", ""),
        institution_id=known.institution_id if known else None,
        after={"method": method},
        request=request,
    )


def _login_ok(request, user: User, keys: tuple[str, str], method: str) -> None:
    cache.delete_many(keys)
    login(request, user, backend=SESSION_BACKEND)
    audit.record(
        "auth.login",
        actor=user,
        entity=("user", user.pk),
        after={"method": method},
        request=request,
    )


@router.get("/csrf", response=CsrfOut, auth=None, operation_id="auth_csrf")
def csrf(request):
    return {"csrf_token": get_token(request)}


@router.post("/staff-login", response=LoginOut, auth=None, operation_id="auth_staff_login")
def staff_login_view(request, payload: StaffLoginIn):
    _enforce_csrf(request)
    keys = _throttle(request, "login", payload.username)
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None or not user.is_active or user.platform_role == PlatformRole.STUDENT:
        known = User.objects.filter(username=payload.username).first()
        _login_failed(request, known, "staff")
        raise HttpError(401, INVALID_LOGIN)
    _login_ok(request, user, keys, "staff")
    return {"user": user}


@router.post("/student-login", response=LoginOut, auth=None, operation_id="auth_student_login")
def student_login_view(request, payload: StudentLoginIn):
    _enforce_csrf(request)
    keys = _throttle(request, "slogin", payload.student_id)
    # Always run the password check so unknown IDs cost the same as known ones.
    user = authenticate(request, username=payload.student_id, password=payload.password)
    if user is None or not user.is_active or user.platform_role != PlatformRole.STUDENT:
        known = User.objects.filter(username=payload.student_id).first()
        _login_failed(request, known, "student")
        raise HttpError(401, INVALID_LOGIN)
    _login_ok(request, user, keys, "student")
    return {"user": user}


@router.post("/logout", auth=django_auth, response={204: None}, operation_id="auth_logout")
def logout_view(request):
    audit.record(
        "auth.logout", actor=request.user, entity=("user", request.user.pk), request=request
    )
    logout(request)
    return 204, None


@router.get("/me", response=MeOut, auth=django_auth, operation_id="auth_me")
def me(request):
    return request.user


@router.post(
    "/change-password", response=MeOut, auth=django_auth, operation_id="auth_change_password"
)
def change_password_view(request, payload: ChangePasswordIn):
    with transaction.atomic():
        user = services.change_password(
            request.user, payload.current_password, payload.new_password
        )
        audit.record("auth.password_changed", actor=user, entity=("user", user.pk), request=request)
    # Keep the current session valid after the password hash changes.
    update_session_auth_hash(request, user)
    return user


@router.post(
    "/users/{user_id}/reset-password",
    response={204: None},
    operation_id="auth_reset_user_password",
)
def reset_password_view(request, user_id: UUID):
    target = get_object_or_404(User, pk=user_id, institution_id=request.user.institution_id)
    with transaction.atomic():
        services.reset_password(request.user, target)
        audit.record(
            "auth.password_reset",
            actor=request.user,
            entity=("user", target.pk),
            request=request,
        )
    return 204, None
