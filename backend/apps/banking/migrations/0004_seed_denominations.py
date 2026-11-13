from decimal import Decimal

from django.db import migrations

# (currency, kind, values) - frozen lookup, see docs/design/erd.md section 2.
DENOMINATIONS = [
    ("USD", "note", ["100", "50", "20", "10", "5", "2", "1"]),
    ("SOS", "note", ["1000", "500", "100", "50"]),
]


def seed(apps, schema_editor):
    Denomination = apps.get_model("banking", "Denomination")
    for currency, kind, values in DENOMINATIONS:
        for value in values:
            Denomination.objects.get_or_create(
                currency=currency, value=Decimal(value), defaults={"kind": kind}
            )


class Migration(migrations.Migration):
    dependencies = [("banking", "0003_branch_cashposition_cashtransfer_denomination_till_and_more")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
