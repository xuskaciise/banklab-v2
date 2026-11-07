from django.db import migrations


def create_default_institution(apps, schema_editor):
    Institution = apps.get_model("accounts", "Institution")
    Institution.objects.get_or_create(name="SIU")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [migrations.RunPython(create_default_institution, migrations.RunPython.noop)]
