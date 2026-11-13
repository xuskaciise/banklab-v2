import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

DEFAULT_INSTITUTION_NAME = "SIU"


def get_default_institution() -> "Institution":
    institution, _ = Institution.objects.get_or_create(name=DEFAULT_INSTITUTION_NAME)
    return institution


class Institution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    logo = models.FileField(upload_to="institution_logos/", blank=True, default="")

    def __str__(self) -> str:
        return self.name


class PlatformRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    INSTRUCTOR = "instructor", "Instructor"
    STUDENT = "student", "Student"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, username, password=None, **extra):
        if not username:
            raise ValueError("username is required")
        extra.setdefault("platform_role", PlatformRole.STUDENT)
        extra.setdefault("is_staff", extra["platform_role"] == PlatformRole.ADMIN)
        if extra.get("institution") is None:
            extra.pop("institution", None)
            extra["institution"] = get_default_institution()
        user = self.model(username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra):
        extra.update(
            platform_role=PlatformRole.ADMIN,
            is_staff=True,
            is_superuser=True,
            must_change_password=False,
        )
        return self.create_user(username, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="users")
    username = models.CharField(max_length=150, unique=True)
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    platform_role = models.CharField(
        max_length=20, choices=PlatformRole.choices, default=PlatformRole.STUDENT
    )
    must_change_password = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        constraints = [
            # "S5101" and "s5101" are the same person: usernames are unique ignoring case.
            models.UniqueConstraint(Lower("username"), name="accounts_user_username_ci_uniq"),
        ]

    def __str__(self) -> str:
        return self.username
