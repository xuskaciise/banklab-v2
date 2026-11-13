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


def seed(apps, schema_editor):
    Institution = apps.get_model("accounts", "Institution")
    Template = apps.get_model("ledger", "CoaTemplate")
    Line = apps.get_model("ledger", "CoaTemplateLine")
    for inst in Institution.objects.all():
        template, created = Template.objects.get_or_create(institution=inst, name=DEFAULT_COA_NAME)
        if not created:
            continue
        Line.objects.bulk_create(
            Line(
                template=template,
                code=code,
                name=name,
                type=typ,
                parent_code=parent,
                postable=postable,
                system_tag=tag,
                is_active=active,
                allow_negative=tag in ALLOW_NEGATIVE_TAGS,
            )
            for code, name, typ, parent, postable, tag, active in FROZEN_COA
        )


class Migration(migrations.Migration):
    dependencies = [("ledger", "0001_initial"), ("accounts", "0004_students_initial_password")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
