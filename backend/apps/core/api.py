"""Platform settings API: any signed-in user reads, only an Admin writes."""

from django.db import transaction
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.accounts.models import PlatformRole
from apps.audit import services as audit

from . import platform

router = Router(tags=["platform"])


class PlatformSettingsOut(Schema):
    sos_enabled: bool
    currencies: list[str]


class PlatformSettingsIn(Schema):
    sos_enabled: bool


def _out(obj) -> dict:
    return {"sos_enabled": obj.sos_enabled, "currencies": platform.enabled_currencies()}


@router.get(
    "/platform/settings", response=PlatformSettingsOut, operation_id="platform_settings_get"
)
def get_settings(request):
    return _out(platform.get_platform_settings())


@router.put(
    "/platform/settings", response=PlatformSettingsOut, operation_id="platform_settings_put"
)
def put_settings(request, payload: PlatformSettingsIn):
    user = request.user
    if user.platform_role != PlatformRole.ADMIN:
        raise HttpError(403, "Not allowed")
    with transaction.atomic():
        obj = platform.get_platform_settings(lock=True)
        before = {"sos_enabled": obj.sos_enabled}
        obj.sos_enabled = payload.sos_enabled
        obj.save(update_fields=["sos_enabled", "updated_at"])
        audit.record(
            "platform.settings_updated",
            actor=user,
            actor_role=user.platform_role,
            entity=("platform_settings", obj.pk),
            before=before,
            after={"sos_enabled": obj.sos_enabled},
            request=request,
        )
    return _out(obj)
