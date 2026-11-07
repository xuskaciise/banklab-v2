from ninja.errors import HttpError
from ninja.security import SessionAuth

from .models import PlatformRole


class ActiveSessionAuth(SessionAuth):
    """Session auth that also blocks staff who still must change their password.

    Students have no password, so the gate never applies to them.
    """

    def authenticate(self, request, key):
        user = super().authenticate(request, key)
        if (
            user is not None
            and user.must_change_password
            and user.platform_role != PlatformRole.STUDENT
        ):
            raise HttpError(403, "Password change required")
        return user
