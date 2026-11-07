from django.db import migrations

# Frozen copy of the default CoA (docs/design/coa.md) as of 1.4; do not import app code.
# (code, name, type, parent_code, postable, system_tag, is_active)
FROZEN_COA = [('1000', 'Assets', 'asset', '', False, '', True),
 ('1100', 'Cash', 'asset', '1000', False, '', True),
 ('1110', 'Cash in Vault', 'asset', '1100', True, 'CASH_VAULT', True),
 ('1120', 'Cash at Tellers', 'asset', '1100', True, 'CASH_TELLER', True),
 ('1300', 'Financing & Loans', 'asset', '1000', False, '', False),
 ('1310', 'Murabaha Receivables', 'asset', '1300', True, 'FIN_MURABAHA', False),
 ('1320', 'Musharakah Investments', 'asset', '1300', True, 'FIN_MUSHARAKAH', False),
 ('1330', 'Qard Hasan Receivables', 'asset', '1300', True, 'FIN_QARD', False),
 ('1340', 'Loans (conventional)', 'asset', '1300', True, 'LOANS', False),
 ('2000', 'Liabilities', 'liability', '', False, '', True),
 ('2100', 'Customer Deposits - Conventional', 'liability', '2000', False, '', True),
 ('2110', 'Savings Deposits', 'liability', '2100', True, 'DEP_SAVINGS', True),
 ('2120', 'Current Deposits', 'liability', '2100', True, 'DEP_CURRENT', True),
 ('2130', 'Fixed Deposits', 'liability', '2100', True, 'DEP_FIXED', False),
 ('2200', 'Customer Deposits - Islamic', 'liability', '2000', False, '', False),
 ('2210', 'Mudarabah Savings', 'liability', '2200', True, 'DEP_MUDARABAH_SAV', False),
 ('2220', 'Mudarabah Term Investments', 'liability', '2200', True, 'DEP_MUDARABAH_TERM', False),
 ('2230', 'Wadiah Current', 'liability', '2200', True, 'DEP_WADIAH', False),
 ('3000', 'Equity', 'equity', '', False, '', True),
 ('3100', 'Paid-up Capital', 'equity', '3000', True, 'CAPITAL', True),
 ('3200', 'Retained Earnings', 'equity', '3000', True, 'RETAINED_EARNINGS', True),
 ('4000', 'Income', 'income', '', False, '', True),
 ('4100', 'Fee & Commission Income', 'income', '4000', True, 'INC_FEES', False),
 ('4200', 'FX Income', 'income', '4000', True, 'INC_FX', False),
 ('4300', 'Financing / Interest Income', 'income', '4000', True, 'INC_FINANCING', False),
 ('4900', 'Cash Over', 'income', '4000', True, 'CASH_OVER', True),
 ('5000', 'Expenses', 'expense', '', False, '', True),
 ('5100',
  'Interest / Profit Paid to Depositors',
  'expense',
  '5000',
  True,
  'EXP_PROFIT_PAID',
  False),
 ('5900', 'Cash Short', 'expense', '5000', True, 'CASH_SHORT', True)]
ALLOW_NEGATIVE_TAGS = {"RETAINED_EARNINGS"}
DEFAULT_COA_NAME = "Default CoA"


def backfill(apps, schema_editor):
    """Provision a CoA (and zero USD/SOS balances) for banks that have no GL accounts."""
    Bank = apps.get_model("lab", "Bank")
    Template = apps.get_model("ledger", "CoaTemplate")
    Line = apps.get_model("ledger", "CoaTemplateLine")
    GLAccount = apps.get_model("ledger", "GLAccount")
    GLBalance = apps.get_model("ledger", "GLBalance")
    banks = Bank.objects.filter(gl_accounts__isnull=True).select_related(
        "session__template", "session__lab_class"
    )
    for bank in banks:
        session = bank.session
        template = session.template.coa_template if session.template_id else None
        if template is None:
            template, created = Template.objects.get_or_create(
                institution_id=session.lab_class.institution_id, name=DEFAULT_COA_NAME
            )
            if created:
                Line.objects.bulk_create(
                    Line(
                        template=template, code=c, name=n, type=t, parent_code=p, postable=po,
                        system_tag=tag, is_active=act, allow_negative=tag in ALLOW_NEGATIVE_TAGS,
                    )
                    for c, n, t, p, po, tag, act in FROZEN_COA
                )
        lines = list(Line.objects.filter(template=template).order_by("code"))
        accounts = {}
        for ln in lines:
            accounts[ln.code] = GLAccount.objects.create(
                bank=bank, code=ln.code, name=ln.name, type=ln.type, postable=ln.postable,
                system_tag=ln.system_tag, is_active=ln.is_active, allow_negative=ln.allow_negative,
            )
        for ln in lines:
            if ln.parent_code and ln.parent_code in accounts:
                acc = accounts[ln.code]
                acc.parent = accounts[ln.parent_code]
                acc.save(update_fields=["parent"])
        GLBalance.objects.bulk_create(
            GLBalance(bank=bank, gl_account=acc, currency=cur)
            for acc in accounts.values()
            if acc.postable
            for cur in ("SOS", "USD")
        )


class Migration(migrations.Migration):
    dependencies = [("ledger", "0003_journal_triggers"), ("lab", "0002_sessiontemplate_coa_template")]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
