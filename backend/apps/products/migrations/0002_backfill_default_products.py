from django.db import migrations

# Frozen copy of the 1.7 default products; do not import app code.
# (code, name, kind, currency, GL system_tag, allows_cheques)
PRODUCTS = [
    ("SAV-USD", "Savings USD", "savings", "USD", "DEP_SAVINGS", False),
    ("SAV-SOS", "Savings SOS", "savings", "SOS", "DEP_SAVINGS", False),
    ("CUR-USD", "Current USD", "current", "USD", "DEP_CURRENT", True),
    ("CUR-SOS", "Current SOS", "current", "SOS", "DEP_CURRENT", True),
]


def backfill(apps, schema_editor):
    Bank = apps.get_model("lab", "Bank")
    GLAccount = apps.get_model("ledger", "GLAccount")
    Product = apps.get_model("products", "Product")
    for bank in Bank.objects.all():
        gl = {
            a.system_tag: a
            for a in GLAccount.objects.filter(bank=bank, system_tag__in=["DEP_SAVINGS", "DEP_CURRENT"])
        }
        if len(gl) < 2:
            continue
        for code, name, kind, currency, tag, cheques in PRODUCTS:
            Product.objects.get_or_create(
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


class Migration(migrations.Migration):
    dependencies = [("products", "0001_initial")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
