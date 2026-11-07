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
from .models import User

router = Router(tags=["auth"])

MAX_ATTEMPTS_PER_USER_IP = 5
MAX_ATTEMPTS_PER_IP = 30
THROTTLE_SECONDS = 300


class LoginIn(Schema):
    username: str
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


def _hit(key: str) -> int:
    cache.add(key, 0, THROTTLE_SECONDS)
    return cache.incr(key)


@router.get("/csrf", response=CsrfOut, auth=None, operation_id="auth_csrf")
def csrf(request):
    return {"csrf_token": get_token(request)}


@router.post("/login", response=LoginOut, auth=None, operation_id="auth_login")
def login_view(request, payload: LoginIn):
    _enforce_csrf(request)
    ip = _client_ip(request)
    user_key = f"login:{payload.username.lower()}:{ip}"
    ip_key = f"login-ip:{ip}"
    # Count every attempt before authenticating so concurrent guesses cannot race past the cap.
    user_hits = _hit(user_key)
    ip_hits = _hit(ip_key)
    if user_hits > MAX_ATTEMPTS_PER_USER_IP or ip_hits > MAX_ATTEMPTS_PER_IP:
        raise HttpError(429, "Too many login attempts. Try again later.")
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None or not user.is_active:
        # Never store the typed string: only a resolved user id, else a bare marker.
        known = User.objects.filter(username=payload.username).first()
        audit.record(
            "auth.login_failed",
            entity=("user", known.pk) if known else ("unknown_username", ""),
            institution_id=known.institution_id if known else None,
            request=request,
        )
        raise HttpError(401, "Invalid username or password")
    cache.delete(user_key)
    login(request, user)
    audit.record("auth.login", actor=user, entity=("user", user.pk), request=request)
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
