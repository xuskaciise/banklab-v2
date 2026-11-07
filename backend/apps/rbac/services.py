from threading import Lock
from uuid import UUID

from .models import RolePermission


class RbacError(Exception):
    """Domain error; `status` is the HTTP status the API maps it to."""

    status = 403

    def __init__(self, message: str = "Not allowed"):
        super().__init__(message)
        self.message = message


class PermissionDenied(RbacError):
    status = 403


_cache: dict[str, dict[str, str]] | None = None
_lock = Lock()


def _role_map() -> dict[str, dict[str, str]]:
    """role -> {permission code: scope}. Defaults only change via migrations (until 1.3)."""
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                data: dict[str, dict[str, str]] = {}
                for role, code, scope in RolePermission.objects.values_list(
                    "role", "permission_id", "scope"
                ):
                    data.setdefault(role, {})[code] = scope
                _cache = data
    return _cache


def clear_cache() -> None:
    global _cache
    with _lock:
        _cache = None


class ValidationFailed(RbacError):
    status = 400


# Catalog codes an instructor override may never grant to a role, derived from the
# separation-of-duties rules (permissions.md section 6). The person-level SoD rules
# (maker != checker, dual control) are hard checks below and are never affected by
# overrides; no catalog code is forbidden for a whole role today.
SOD_FORBIDDEN_GRANTS: dict[str, frozenset[str]] = {}


def load_overrides(session) -> dict[tuple[str, str], bool]:
    if session is None:
        return {}
    from apps.lab.models import PermissionOverride

    return {
        (role, code): allowed
        for role, code, allowed in PermissionOverride.objects.filter(session=session).values_list(
            "role", "permission_id", "allowed"
        )
    }


def default_scope(role: str, code: str) -> str | None:
    return _role_map().get(role, {}).get(code)


def permission_scope(
    role: str, code: str, *, session=None, overrides: dict | None = None
) -> str | None:
    """Return "all", "own" or None (not granted) for a bank role and permission code.

    Per-session overrides are applied on top of the defaults when `session` is given;
    pass a preloaded `overrides` map (from `load_overrides`) to avoid one query per call.
    """
    scope = default_scope(role, code)
    if overrides is None:
        overrides = load_overrides(session)
    override = overrides.get((role, code))
    if override is None:
        return scope
    if not override:
        return None
    return scope or "all"


def role_has_permission(role: str, code: str, *, session=None) -> bool:
    """Whether `role` holds `code` (defaults plus the session's overrides)."""
    return permission_scope(role, code, session=session) is not None


def assert_override_allowed(role: str, code: str, allowed: bool) -> None:
    if allowed and code in SOD_FORBIDDEN_GRANTS.get(role, frozenset()):
        raise ValidationFailed("Cannot grant this permission to this role (separation of duties)")


def _person_id(value) -> str:
    """Normalise an actor id; fail closed on missing ids or model instances."""
    if value is None:
        raise PermissionDenied("Actor id is required for separation-of-duties checks")
    if not isinstance(value, (str, int, UUID)) or isinstance(value, bool):
        raise TypeError("Pass actor ids (UUID/str/int), not model instances")
    normalised = str(value).strip().lower()
    if not normalised:
        raise PermissionDenied("Actor id is required for separation-of-duties checks")
    return normalised


# TODO(1.4+): person-level SoD checks (maker != checker, dual control, own open teller
# session) must stay hard checks that ignore PermissionOverride rows; never gate them on
# role_has_permission.
def assert_maker_checker(maker_id, checker_id) -> None:
    """Nobody approves their own request or transaction (permissions.md section 6.1)."""
    if _person_id(maker_id) == _person_id(checker_id):
        raise PermissionDenied("Maker and checker must be different people")


def assert_dual_control(maker_id, first_approver_id, second_approver_id) -> None:
    """Vault dual control: requester and both approvers are three different people
    (permissions.md section 6.1 + 6.2)."""
    ids = {_person_id(maker_id), _person_id(first_approver_id), _person_id(second_approver_id)}
    if len(ids) != 3:
        raise PermissionDenied("Dual control requires a requester and two different approvers")
