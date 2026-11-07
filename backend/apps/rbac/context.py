from functools import wraps

from ninja.errors import HttpError

from . import services


def get_active_bank_role(request) -> str | None:
    """Return the caller's active bank role in the current bank, or None.

    TODO(1.3): resolve from the user's active role_assignment in the current session/bank.
    """
    return None


def require_bank_permission(code: str):
    """Decorator for Ninja views: 403 unless the caller's active bank role holds `code`.

    Sets `request.bank_role` and `request.permission_scope` ("all" | "own") for the view.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            role = get_active_bank_role(request)
            scope = services.permission_scope(role, code) if role else None
            if scope is None:
                raise HttpError(403, "Not allowed")
            request.bank_role = role
            request.permission_scope = scope
            return func(request, *args, **kwargs)

        return wrapper

    return decorator
