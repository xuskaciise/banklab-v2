from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.banking.models import NoDeleteModel
from apps.core.models import TimeStampedModel


class ExamStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"


class Exam(TimeStampedModel):
    """Exam set-up of one exam session (1:1). Editable only while `draft`.

    `seed` is a list of per-student seed accounts, e.g.
    `[{"product_code": "SAV-USD", "amount": "500.00", "vary": false}]`.
    """

    session = models.OneToOneField("lab.Session", on_delete=models.PROTECT, related_name="exam")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    instructions = models.TextField(blank=True, default="")
    seed = models.JSONField(default=list)
    status = models.CharField(max_length=10, choices=ExamStatus.choices, default=ExamStatus.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    results_published = models.BooleanField(default=False)
    results_published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")), name="exam_window_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(duration_minutes__gt=0), name="exam_duration_gt_0"
            ),
        ]


class ExamTask(TimeStampedModel):
    """One task. Config only (draft exams); results never reference a deleted task."""

    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="tasks")
    position = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    instructions = models.TextField(blank=True, default="")
    check_type = models.CharField(max_length=40)
    check_params = models.JSONField(default=dict)
    points = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("1.00"))

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(points__gt=0), name="exam_task_points_gt_0")
        ]


class ExamAttempt(NoDeleteModel):
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="attempts")
    session_member = models.ForeignKey(
        "lab.SessionMember", on_delete=models.PROTECT, related_name="exam_attempts"
    )
    started_at = models.DateTimeField()
    deadline_at = models.DateTimeField()  # min(ends_at, started_at + duration), fixed at start
    submitted_at = models.DateTimeField(null=True, blank=True)
    auto_submitted = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["exam", "session_member"], name="uniq_exam_attempt")
        ]


class ExamTaskResult(NoDeleteModel):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.PROTECT, related_name="results")
    task = models.ForeignKey(ExamTask, on_delete=models.PROTECT, related_name="results")
    passed = models.BooleanField()
    points = models.DecimalField(max_digits=18, decimal_places=2)  # auto-check points
    details = models.JSONField(default=dict)
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    adjusted_points = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    adjusted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["task__position", "created_at"]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "task"], name="uniq_exam_task_result")
        ]

    @property
    def final_points(self) -> Decimal:
        return self.adjusted_points if self.adjusted_points is not None else self.points
