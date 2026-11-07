from ninja.errors import HttpError
from ninja.security import SessionAuth


class ActiveSessionAuth(SessionAuth):
    """Session auth that also blocks users who still must change their password."""

    def authenticate(self, request, key):
        user = super().authenticate(request, key)
        if user is not None and user.must_change_password:
            raise HttpError(403, "Password change required")
        return user
