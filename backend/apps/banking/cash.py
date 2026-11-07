"""Cash holders (vault, teller session) and the bank's cash set-up.

Low-level module: imported by the ledger posting service, so it must not import
`apps.ledger.services` at module level.
"""

import uuid
from collections.abc import Callable
from decimal import Decimal

from .models import Branch, CashPosition, HolderType, Vault

# GL system tag of the control account that mirrors each holder type.
HOLDER_GL_TAG = {
    HolderType.VAULT.value: "CASH_VAULT",
    HolderType.TELLER_SESSION.value: "CASH_TELLER",
}
GL_TAG_HOLDER = {tag: holder for holder, tag in HOLDER_GL_TAG.items()}
CURRENCIES = ("SOS", "USD")

# holder_type -> callable(bank, holder_id) -> bool ("does this holder exist in this bank?").
# 1.8 registers `teller_session`; until then nothing can hold teller cash.
# TODO(1.8): teller-originated requests (teller -> vault) must use the acting member's own
# teller_session as the source; do not trust a client-supplied teller holder id.
_HOLDER_EXISTS: dict[str, Callable[[object, uuid.UUID], bool]] = {}


def register_holder_type(holder_type: str, exists: Callable[[object, uuid.UUID], bool]) -> None:
    _HOLDER_EXISTS[holder_type] = exists


def holder_exists(bank, holder_type: str, holder_id) -> bool:
    check = _HOLDER_EXISTS.get(holder_type)
    if check is None:
        return False
    try:
        holder_uuid = holder_id if isinstance(holder_id, uuid.UUID) else uuid.UUID(str(holder_id))
    except (ValueError, AttributeError, TypeError):
        return False
    return bool(check(bank, holder_uuid))


register_holder_type(
    HolderType.VAULT.value, lambda bank, pk: Vault.objects.filter(bank=bank, pk=pk).exists()
)


def create_position_rows(bank, holder_type: str, holder_id) -> None:
    CashPosition.objects.bulk_create(
        [
            CashPosition(
                bank=bank,
                holder_type=holder_type,
                holder_id=holder_id,
                currency=cur,
                balance=Decimal("0.00"),
            )
            for cur in CURRENCIES
        ],
        ignore_conflicts=True,
    )


def create_branch(bank, code: str, name: str, address: str = "") -> Branch:
    """Branch + its vault + zero cash positions (USD, SOS). Caller owns the transaction."""
    branch = Branch.objects.create(bank=bank, code=code, name=name, address=address)
    vault = Vault.objects.create(bank=bank, branch=branch)
    create_position_rows(bank, HolderType.VAULT.value, vault.pk)
    return branch
