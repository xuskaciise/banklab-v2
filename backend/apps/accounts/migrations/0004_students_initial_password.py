import re

from django.contrib.auth.hashers import is_password_usable, make_password
from django.db import migrations


def give_students_initial_password(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.filter(platform_role="student"):
        if is_password_usable(user.password):
            continue
        digits = re.sub(r"\D", "", user.phone or "")
        if len(digits) < 4:
            continue  # no usable phone: an admin must fix the record, then reset
        user.password = make_password(digits[-4:])
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_students_passwordless")]

    operations = [
        migrations.RunPython(give_students_initial_password, migrations.RunPython.noop)
    ]
