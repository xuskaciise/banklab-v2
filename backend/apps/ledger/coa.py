"""Default chart of accounts, exactly per docs/design/coa.md.

Tuple: (code, name, type, parent_code, postable, system_tag, is_active)
Rows reserved for later phases (P3/P4/Later) are created inactive so codes stay stable.
"""

ASSET, LIABILITY, EQUITY, INCOME, EXPENSE = "asset", "liability", "equity", "income", "expense"

DEFAULT_COA_NAME = "Default CoA"

# Only RETAINED_EARNINGS may carry a negative balance (accumulated losses).
ALLOW_NEGATIVE_TAGS = frozenset({"RETAINED_EARNINGS"})

DEFAULT_COA = [
    ("1000", "Assets", ASSET, "", False, "", True),
    ("1100", "Cash", ASSET, "1000", False, "", True),
    ("1110", "Cash in Vault", ASSET, "1100", True, "CASH_VAULT", True),
    ("1120", "Cash at Tellers", ASSET, "1100", True, "CASH_TELLER", True),
    ("1300", "Financing & Loans", ASSET, "1000", False, "", False),
    ("1310", "Murabaha Receivables", ASSET, "1300", True, "FIN_MURABAHA", False),
    ("1320", "Musharakah Investments", ASSET, "1300", True, "FIN_MUSHARAKAH", False),
    ("1330", "Qard Hasan Receivables", ASSET, "1300", True, "FIN_QARD", False),
    ("1340", "Loans (conventional)", ASSET, "1300", True, "LOANS", False),
    ("2000", "Liabilities", LIABILITY, "", False, "", True),
    ("2100", "Customer Deposits - Conventional", LIABILITY, "2000", False, "", True),
    ("2110", "Savings Deposits", LIABILITY, "2100", True, "DEP_SAVINGS", True),
    ("2120", "Current Deposits", LIABILITY, "2100", True, "DEP_CURRENT", True),
    ("2130", "Fixed Deposits", LIABILITY, "2100", True, "DEP_FIXED", False),
    ("2200", "Customer Deposits - Islamic", LIABILITY, "2000", False, "", False),
    ("2210", "Mudarabah Savings", LIABILITY, "2200", True, "DEP_MUDARABAH_SAV", False),
    ("2220", "Mudarabah Term Investments", LIABILITY, "2200", True, "DEP_MUDARABAH_TERM", False),
    ("2230", "Wadiah Current", LIABILITY, "2200", True, "DEP_WADIAH", False),
    ("3000", "Equity", EQUITY, "", False, "", True),
    ("3100", "Paid-up Capital", EQUITY, "3000", True, "CAPITAL", True),
    ("3200", "Retained Earnings", EQUITY, "3000", True, "RETAINED_EARNINGS", True),
    ("4000", "Income", INCOME, "", False, "", True),
    ("4100", "Fee & Commission Income", INCOME, "4000", True, "INC_FEES", False),
    ("4200", "FX Income", INCOME, "4000", True, "INC_FX", False),
    ("4300", "Financing / Interest Income", INCOME, "4000", True, "INC_FINANCING", False),
    ("4900", "Cash Over", INCOME, "4000", True, "CASH_OVER", True),
    ("5000", "Expenses", EXPENSE, "", False, "", True),
    ("5100", "Interest / Profit Paid to Depositors", EXPENSE, "5000", True, "EXP_PROFIT_PAID",
     False),
    ("5900", "Cash Short", EXPENSE, "5000", True, "CASH_SHORT", True),
]
