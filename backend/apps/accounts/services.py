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
    """The first password (staff and students) is the last 4 phone digits."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 4:
        raise ValidationFailed("Phone must contain at least 4 digits")
    return digits[-4:]


def normalize_phone(phone: str) -> str:
    """Reduce a phone number to a national number.

    Digits only; strip a leading "00"; strip "252" when more than 9 digits
    remain; strip leading zeros.
    """
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("252") and len(digits) > 9:
        digits = digits[3:]
    return digits.lstrip("0")


def validate_student_phone(phone: str) -> None:
    """The phone gives the initial password and contact: require a plausible national number."""
    if not 7 <= len(normalize_phone(phone or "")) <= 12:
        raise ValidationFailed("Enter a valid phone number")


@transaction.atomic
def create_user(username, full_name, phone, platform_role, institution=None) -> User:
    if platform_role not in PlatformRole.values:
        raise ValidationFailed("Invalid platform role")
    if User.objects.filter(username=username).exists():
        raise ValidationFailed("Username already exists")
    if platform_role == PlatformRole.STUDENT:
        validate_student_phone(phone)
    return User.objects.create_user(
        username=username,
        password=initial_password(phone),
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
    """Reset a user's password back to the initial one (last 4 phone digits).

    Admins may reset anyone in their institution; instructors only students of their own classes.
    """
    if actor.institution_id != target.institution_id:
        raise PermissionDenied("Not allowed to reset passwords")
    if actor.platform_role == PlatformRole.INSTRUCTOR:
        # Only students enrolled in one of the instructor's own classes.
        from apps.lab.models import Enrollment  # local import: lab depends on accounts

        own_student = (
            target.platform_role == PlatformRole.STUDENT
            and Enrollment.objects.filter(user=target, lab_class__instructor=actor).exists()
        )
        if not own_student:
            raise PermissionDenied("Not allowed to reset passwords")
    elif actor.platform_role != PlatformRole.ADMIN:
        raise PermissionDenied("Not allowed to reset passwords")
    target = User.objects.select_for_update().get(pk=target.pk)
    target.set_password(initial_password(target.phone))
    target.must_change_password = True
    target.save(update_fields=["password", "must_change_password"])
    return target
