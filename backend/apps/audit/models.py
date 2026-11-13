import uuid

from django.conf import settings
from django.db import models


class ImmutableError(Exception):
    pass


class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ImmutableError("Audit log rows cannot be updated")

    def delete(self):
        raise ImmutableError("Audit log rows cannot be deleted")

    def bulk_update(self, *args, **kwargs):
        raise ImmutableError("Audit log rows cannot be updated")

    def _update(self, values):
        raise ImmutableError("Audit log rows cannot be updated")

    def _raw_delete(self, using):
        raise ImmutableError("Audit log rows cannot be deleted")


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    institution = models.ForeignKey(
        "accounts.Institution",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    actor_role = models.CharField(max_length=40, blank=True, default="")
    action = models.CharField(max_length=80)
    entity_type = models.CharField(max_length=80, blank=True, default="")
    entity_id = models.CharField(max_length=150, blank=True, default="")
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    ip = models.CharField(max_length=64, blank=True, default="")
    session = models.ForeignKey(
        "lab.Session", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    bank = models.ForeignKey(
        "lab.Bank", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    at = models.DateTimeField(auto_now_add=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ["-at"]
        indexes = [
            models.Index(fields=["at"], name="audit_at_idx"),
            models.Index(fields=["actor", "at"], name="audit_actor_at_idx"),
            models.Index(fields=["session", "at"], name="audit_session_at_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableError("Audit log rows cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError("Audit log rows cannot be deleted")

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M:%S} {self.action}"
