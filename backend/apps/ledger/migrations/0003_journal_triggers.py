from django.db import migrations

CREATE = """
CREATE FUNCTION ledger_journal_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ledger_journalentry_no_change
BEFORE UPDATE OR DELETE ON ledger_journalentry
FOR EACH ROW EXECUTE FUNCTION ledger_journal_immutable();

CREATE TRIGGER ledger_journalline_no_change
BEFORE UPDATE OR DELETE ON ledger_journalline
FOR EACH ROW EXECUTE FUNCTION ledger_journal_immutable();

CREATE FUNCTION ledger_check_entry_balanced() RETURNS trigger AS $$
DECLARE
    dr numeric;
    cr numeric;
    entry_currency text;
    entry_bank uuid;
BEGIN
    SELECT currency, bank_id INTO entry_currency, entry_bank
    FROM ledger_journalentry WHERE id = NEW.entry_id;
    SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0) INTO dr, cr
    FROM ledger_journalline WHERE entry_id = NEW.entry_id;
    IF dr <> cr THEN
        RAISE EXCEPTION 'journal entry % is not balanced (Dr % <> Cr %)', NEW.entry_id, dr, cr;
    END IF;
    IF EXISTS (SELECT 1 FROM ledger_journalline
               WHERE entry_id = NEW.entry_id AND currency <> entry_currency) THEN
        RAISE EXCEPTION 'journal entry % has lines in a different currency', NEW.entry_id;
    END IF;
    IF EXISTS (SELECT 1 FROM ledger_journalline l
               JOIN ledger_glaccount a ON a.id = l.gl_account_id
               WHERE l.entry_id = NEW.entry_id AND a.bank_id <> entry_bank) THEN
        RAISE EXCEPTION 'journal entry % uses a GL account of another bank', NEW.entry_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER ledger_journalline_balanced
AFTER INSERT ON ledger_journalline
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION ledger_check_entry_balanced();

CREATE FUNCTION ledger_check_entry_lines() RETURNS trigger AS $$
BEGIN
    IF (SELECT COUNT(*) FROM ledger_journalline WHERE entry_id = NEW.id) < 2 THEN
        RAISE EXCEPTION 'journal entry % needs at least two lines', NEW.id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER ledger_journalentry_has_lines
AFTER INSERT ON ledger_journalentry
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION ledger_check_entry_lines();
"""

DROP = """
DROP TRIGGER ledger_journalentry_has_lines ON ledger_journalentry;
DROP FUNCTION ledger_check_entry_lines();
DROP TRIGGER ledger_journalline_balanced ON ledger_journalline;
DROP FUNCTION ledger_check_entry_balanced();
DROP TRIGGER ledger_journalline_no_change ON ledger_journalline;
DROP TRIGGER ledger_journalentry_no_change ON ledger_journalentry;
DROP FUNCTION ledger_journal_immutable();
"""


class Migration(migrations.Migration):
    dependencies = [("ledger", "0002_seed_default_coa")]

    operations = [migrations.RunSQL(CREATE, DROP)]
