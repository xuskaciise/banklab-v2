from django.db import migrations


class Migration(migrations.Migration):
    """Superseded: students do have passwords again (see 0004).

    Kept as a no-op so the migration graph stays stable; it was never on main.
    """

    dependencies = [("accounts", "0002_default_institution")]

    operations = [migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop)]
