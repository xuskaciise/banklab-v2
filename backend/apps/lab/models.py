from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.rbac.models import BankRole, Permission


class SessionKind(models.TextChoices):
    PRACTICE = "practice", "Practice"
    EXAM = "exam", "Exam"


class SessionStructure(models.TextChoices):
    SINGLE_BANK = "single_bank", "Single bank"
    PER_GROUP = "per_group", "One bank per group"


class SessionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class Visibility(models.TextChoices):
    OWN = "own", "Own work only"
    ALL = "all", "Whole bank"


class Class(TimeStampedModel):
    institution = models.ForeignKey(
        "accounts.Institution", on_delete=models.PROTECT, related_name="classes"
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="taught_classes"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=40)

    class Meta:
        verbose_name_plural = "classes"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "code"], name="uniq_class_code")
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class Enrollment(TimeStampedModel):
    lab_class = models.ForeignKey(Class, on_delete=models.PROTECT, related_name="enrollments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrollments"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lab_class", "user"], name="uniq_enrollment")
        ]


class SessionTemplate(TimeStampedModel):
    """Saved session settings. `lab_class` null = institution-wide (admin-managed).

    `coa_template` / `product_set` arrive with the ledger (1.4+).
    """

    institution = models.ForeignKey(
        "accounts.Institution", on_delete=models.PROTECT, related_name="session_templates"
    )
    lab_class = models.ForeignKey(
        Class, null=True, blank=True, on_delete=models.PROTECT, related_name="templates"
    )
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=SessionKind.choices)
    structure = models.CharField(max_length=12, choices=SessionStructure.choices)
    allowed_roles = models.JSONField(default=list)
    default_visibility = models.CharField(max_length=3, choices=Visibility.choices)
    learning_panel = models.BooleanField(default=True)
    seed_profile = models.CharField(max_length=80, blank=True, default="")
    opening_capital_usd = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("1000000.00")
    )
    opening_capital_sos = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("5000000000.00")
    )
    coa_template = models.ForeignKey(
        "ledger.CoaTemplate",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="session_templates",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["name"]


class Session(TimeStampedModel):
    lab_class = models.ForeignKey(Class, on_delete=models.PROTECT, related_name="sessions")
    template = models.ForeignKey(
        SessionTemplate, null=True, blank=True, on_delete=models.PROTECT, related_name="sessions"
    )
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=SessionKind.choices)
    structure = models.CharField(max_length=12, choices=SessionStructure.choices)
    status = models.CharField(
        max_length=10, choices=SessionStatus.choices, default=SessionStatus.DRAFT
    )
    allowed_roles = models.JSONField(default=list)
    default_visibility = models.CharField(max_length=3, choices=Visibility.choices)
    learning_panel = models.BooleanField(default=True)
    seed_profile = models.CharField(max_length=80, blank=True, default="")
    opening_capital_usd = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("1000000.00")
    )
    opening_capital_sos = models.DecimalField(
        max_digits=18, decimal_places=2, default=Decimal("5000000000.00")
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class Bank(TimeStampedModel):
    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name="banks")
    name = models.CharField(max_length=200)
    group_no = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["group_no", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "group_no"],
                condition=models.Q(group_no__isnull=False),
                name="uniq_bank_group_no",
            )
        ]

    def __str__(self) -> str:
        return self.name


class SessionMember(TimeStampedModel):
    """A student in a session. `bank` is null until the student is placed in a bank."""

    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name="members")
    bank = models.ForeignKey(
        Bank, null=True, blank=True, on_delete=models.PROTECT, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="session_memberships"
    )
    visibility_override = models.CharField(
        max_length=3, choices=Visibility.choices, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="uniq_session_member")
        ]


class RoleAssignment(TimeStampedModel):
    session_member = models.ForeignKey(
        SessionMember, on_delete=models.PROTECT, related_name="assignments"
    )
    role = models.CharField(max_length=20, choices=BankRole.choices)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    active_from = models.DateTimeField()
    active_to = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-active_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["session_member"],
                condition=models.Q(active_to__isnull=True),
                name="uniq_active_role_per_member",
            )
        ]


class PermissionOverride(TimeStampedModel):
    session = models.ForeignKey(
        Session, on_delete=models.PROTECT, related_name="permission_overrides"
    )
    role = models.CharField(max_length=20, choices=BankRole.choices)
    permission = models.ForeignKey(Permission, on_delete=models.PROTECT, related_name="+")
    allowed = models.BooleanField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "role", "permission"], name="uniq_permission_override"
            )
        ]
