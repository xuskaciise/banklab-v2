"""Platform-wide settings and the single currency gate used by every write service."""

from .models import PLATFORM_SETTINGS_ID, PlatformSettings


def get_platform_settings(*, lock: bool = False) -> PlatformSettings:
    obj, _ = PlatformSettings.objects.get_or_create(pk=PLATFORM_SETTINGS_ID)
    if lock:
        obj = PlatformSettings.objects.select_for_update().get(pk=PLATFORM_SETTINGS_ID)
    return obj


def enabled_currencies() -> list[str]:
    return ["USD", "SOS"] if get_platform_settings().sos_enabled else ["USD"]


def require_currency_enabled(currency: str) -> None:
    """Reject NEW business in a switched-off currency. Reads and reversals never call this."""
    from apps.ledger.services import LedgerError

    if currency not in enabled_currencies():
        raise LedgerError(
            "currency_disabled",
            f"{currency} currency is disabled",
            status=400,
        )
