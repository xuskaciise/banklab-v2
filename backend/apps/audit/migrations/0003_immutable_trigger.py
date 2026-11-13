from django.db import migrations

CREATE = """
CREATE FUNCTION audit_auditlog_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_auditlog rows are immutable';
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER audit_auditlog_no_change
BEFORE UPDATE OR DELETE ON audit_auditlog
FOR EACH ROW EXECUTE FUNCTION audit_auditlog_immutable();
"""

DROP = """
DROP TRIGGER audit_auditlog_no_change ON audit_auditlog;
DROP FUNCTION audit_auditlog_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0002_auditlog_institution")]

    operations = [migrations.RunSQL(CREATE, DROP)]
