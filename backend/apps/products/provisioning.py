"""Default deposit products of a bank (idempotent). Used when a bank is created."""

from django.db import transaction

from apps.ledger.models import GLAccount

from .models import Product

# (code, name, kind, currency, GL system_tag, allows_cheques)
DEFAULT_PRODUCTS = [
    ("SAV-USD", "Savings USD", "savings", "USD", "DEP_SAVINGS", False),
    ("SAV-SOS", "Savings SOS", "savings", "SOS", "DEP_SAVINGS", False),
    ("CUR-USD", "Current USD", "current", "USD", "DEP_CURRENT", True),
    ("CUR-SOS", "Current SOS", "current", "SOS", "DEP_CURRENT", True),
]


@transaction.atomic
def provision_bank_products(bank) -> list[Product]:
    """Create the 4 default products; needs the bank's CoA. Safe to call again."""
    gl = {
        a.system_tag: a for a in GLAccount.objects.filter(bank=bank, system_tag__startswith="DEP_")
    }
    out = []
    for code, name, kind, currency, tag, cheques in DEFAULT_PRODUCTS:
        if tag not in gl:  # a custom CoA template may omit the deposit accounts
            continue
        product, _ = Product.objects.get_or_create(
            bank=bank,
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "currency": currency,
                "allows_cheques": cheques,
                "gl_account": gl[tag],
            },
        )
        out.append(product)
    return out
