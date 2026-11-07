import re

from django.contrib.auth.hashers import make_password
from django.db import migrations


def students_without_password(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    # make_password(None) yields an unusable password hash.
    User.objects.filter(platform_role="student").update(
        password=make_password(None), must_change_password=False
    )


def restore_initial_passwords(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.filter(platform_role="student"):
        digits = re.sub(r"\D", "", user.phone or "")
        if len(digits) >= 4:
            user.password = make_password(digits[-4:])
            user.must_change_password = True
            user.save(update_fields=["password", "must_change_password"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_default_institution")]

    operations = [migrations.RunPython(students_without_password, restore_initial_passwords)]
