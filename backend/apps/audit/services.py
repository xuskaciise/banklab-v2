from apps.core.net import client_ip

from .models import AuditLog

_SENSITIVE_PARTS = (
    "password",
    "passwd",
    "pin",
    "token",
    "secret",
    "key",
    "session",
    "hash",
    "csrf",
)


def _scrub(value):
    """Drop password/token keys so they can never be persisted."""
    if isinstance(value, dict):
        return {
            k: _scrub(v)
            for k, v in value.items()
            if not any(part in str(k).lower() for part in _SENSITIVE_PARTS)
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


def record(
    action: str,
    *,
    actor=None,
    actor_role: str = "",
    entity=None,
    before=None,
    after=None,
    request=None,
    session_id=None,
    bank_id=None,
    institution_id=None,
) -> AuditLog:
    """Append one audit row. `entity` is None or an (entity_type, entity_id) tuple."""
    entity_type, entity_id = ("", "")
    if entity is not None:
        entity_type, entity_id = entity[0], str(entity[1])
    if institution_id is None and actor is not None:
        institution_id = actor.institution_id
    return AuditLog.objects.create(
        institution_id=institution_id,
        actor=actor,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=_scrub(before),
        after=_scrub(after),
        ip=client_ip(request),
        session_id=session_id,
        bank_id=bank_id,
    )
