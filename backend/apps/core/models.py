import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Base for every table: UUID primary key plus created/updated timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


PLATFORM_SETTINGS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class PlatformSettings(TimeStampedModel):
    """Platform-wide singleton (fixed primary key) controlled by an Admin."""

    sos_enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "platform settings"
