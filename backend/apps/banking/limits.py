"""Per-bank transaction limits (permissions.md section 5) and the approval test.

A missing rule means "no limit" for that role/type/currency.
"""

from decimal import Decimal

from .models import LimitRule

# (role, txn_type, USD, SOS) - permissions.md section 5
DEFAULT_LIMITS = [
    ("teller", "cash_withdrawal", "5000.00", "125000000.00"),
    ("teller", "cheque_withdrawal", "5000.00", "125000000.00"),
    ("teller", "cash_deposit", "20000.00", "500000000.00"),
    ("teller", "transfer", "10000.00", "250000000.00"),
    ("cso", "transfer", "10000.00", "250000000.00"),
]


def seed_limits(bank, model=LimitRule) -> None:
    """Create the default rules of a bank (idempotent). `model` lets a data migration pass
    its historical model."""
    for role, txn_type, usd, sos in DEFAULT_LIMITS:
        for currency, amount in (("USD", usd), ("SOS", sos)):
            model.objects.get_or_create(
                bank=bank,
                role=role,
                txn_type=txn_type,
                currency=currency,
                defaults={"max_amount": Decimal(amount)},
            )


def needs_approval(bank, role: str, txn_type: str, currency: str, amount: Decimal) -> bool:
    rule = LimitRule.objects.filter(
        bank=bank, role=role, txn_type=txn_type, currency=currency
    ).first()
    return rule is not None and amount > rule.max_amount
