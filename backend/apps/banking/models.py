from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class BusinessDayStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class BusinessDay(TimeStampedModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="business_days")
    date = models.DateField()
    status = models.CharField(
        max_length=6, choices=BusinessDayStatus.choices, default=BusinessDayStatus.OPEN
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["bank", "date"], name="uniq_business_day"),
            models.UniqueConstraint(
                fields=["bank"],
                condition=models.Q(status="open"),
                name="uniq_open_business_day_per_bank",
            ),
        ]
