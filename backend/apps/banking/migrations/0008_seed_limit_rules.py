from django.db import migrations

# Source: docs/design/permissions.md section 5 (kept inline: migrations must not import app code).
DEFAULT_LIMITS = [
    ("teller", "cash_withdrawal", "5000.00", "125000000.00"),
    ("teller", "cheque_withdrawal", "5000.00", "125000000.00"),
    ("teller", "cash_deposit", "20000.00", "500000000.00"),
    ("teller", "transfer", "10000.00", "250000000.00"),
    ("cso", "transfer", "10000.00", "250000000.00"),
]


def seed(apps, schema_editor):
    Bank = apps.get_model("lab", "Bank")
    LimitRule = apps.get_model("banking", "LimitRule")
    for bank in Bank.objects.all():
        for role, txn_type, usd, sos in DEFAULT_LIMITS:
            for currency, amount in (("USD", usd), ("SOS", sos)):
                LimitRule.objects.get_or_create(
                    bank=bank,
                    role=role,
                    txn_type=txn_type,
                    currency=currency,
                    defaults={"max_amount": amount},
                )


class Migration(migrations.Migration):
    dependencies = [("banking", "0007_transactions"), ("lab", "0003_session_opening_capital_sos_and_more")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
