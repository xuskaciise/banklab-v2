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


def permission_scope(role: str, code: str) -> str | None:
    """Return "all", "own" or None (not granted) for a bank role and permission code."""
    return _role_map().get(role, {}).get(code)


def role_has_permission(role: str, code: str, *, session=None) -> bool:
    """Whether `role` holds `code`.

    `session` is reserved for 1.3: per-session `permission_override` rows will be applied
    here (add/remove on top of the defaults, never touching the separation-of-duties
    rules). Today it is ignored.
    """
    return permission_scope(role, code) is not None


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
