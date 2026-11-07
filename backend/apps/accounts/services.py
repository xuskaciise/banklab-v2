import re

from django.db import transaction

from .models import PlatformRole, User, get_default_institution

MIN_PASSWORD_LENGTH = 6


class AccountsError(Exception):
    """Domain error; `status` is the HTTP status the API maps it to."""

    status = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationFailed(AccountsError):
    status = 400


class PermissionDenied(AccountsError):
    status = 403


def initial_password(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 4:
        raise ValidationFailed("Phone must contain at least 4 digits")
    return digits[-4:]


@transaction.atomic
def create_user(username, full_name, phone, platform_role, institution=None) -> User:
    if platform_role not in PlatformRole.values:
        raise ValidationFailed("Invalid platform role")
    if User.objects.filter(username=username).exists():
        raise ValidationFailed("Username already exists")
    password = initial_password(phone)
    return User.objects.create_user(
        username=username,
        password=password,
        full_name=full_name,
        phone=phone,
        platform_role=platform_role,
        institution=institution or get_default_institution(),
        must_change_password=True,
    )


@transaction.atomic
def change_password(user: User, current: str, new: str) -> User:
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.check_password(current):
        raise ValidationFailed("Current password is incorrect")
    if len(new) < MIN_PASSWORD_LENGTH:
        raise ValidationFailed(f"New password must be at least {MIN_PASSWORD_LENGTH} characters")
    if new == current:
        raise ValidationFailed("New password must differ from the current password")
    if new == initial_password(user.phone):
        raise ValidationFailed("New password must not be the initial password")
    user.set_password(new)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password"])
    return user


@transaction.atomic
def reset_password(actor: User, target: User) -> User:
    if actor.platform_role == PlatformRole.ADMIN:
        pass
    elif actor.platform_role == PlatformRole.INSTRUCTOR:
        # TODO(1.3): scope to students in the instructor's own classes.
        if target.platform_role != PlatformRole.STUDENT:
            raise PermissionDenied("Instructors can only reset student passwords")
    else:
        raise PermissionDenied("Not allowed to reset passwords")
    if actor.institution_id != target.institution_id:
        raise PermissionDenied("Not allowed to reset passwords")
    target = User.objects.select_for_update().get(pk=target.pk)
    target.set_password(initial_password(target.phone))
    target.must_change_password = True
    target.save(update_fields=["password", "must_change_password"])
    return target
