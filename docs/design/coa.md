# Chart of Accounts — BankLab V2 (Phase 0.2)

The default CoA template every new bank is created from (`coa_template`).
The instructor may add accounts or rename them; accounts with a
`system_tag` cannot be deleted, re-typed or untagged (the posting service
finds them by tag).

## Currency model
- **One CoA, balances per currency.** A GL account is not tied to a currency;
  every `journal_line` carries `currency` and `gl_balance` is kept per
  (`gl_account`, `currency`). Trial Balance and statements are shown per currency.
- Every journal entry balances **per currency** (Σ Dr = Σ Cr in USD and in SOS
  separately). No FX in MVP, so an entry never mixes currencies.
- Amounts: `NUMERIC(18,2)`. SOS is also kept at 2 decimals for one rule everywhere.

## Template

`P` = postable (journal lines allowed), `H` = header (totals only).
`MVP` = used in Phase 1; `Px` = reserved for a later phase (created now so codes stay stable, but inactive).

| Code | Name | Type | P/H | system_tag | Phase |
|------|------|------|-----|------------|-------|
| **1000** | **Assets** | asset | H | | MVP |
| 1100 | Cash | asset | H | | MVP |
| 1110 | Cash in Vault | asset | P | `CASH_VAULT` | MVP |
| 1120 | Cash at Tellers | asset | P | `CASH_TELLER` | MVP |
| 1300 | Financing & Loans | asset | H | | P3 |
| 1310 | Murabaha Receivables | asset | P | `FIN_MURABAHA` | P3 |
| 1320 | Musharakah Investments | asset | P | `FIN_MUSHARAKAH` | P3 |
| 1330 | Qard Hasan Receivables | asset | P | `FIN_QARD` | P3 |
| 1340 | Loans (conventional) | asset | P | `LOANS` | P3 |
| **2000** | **Liabilities** | liability | H | | MVP |
| 2100 | Customer Deposits — Conventional | liability | H | | MVP |
| 2110 | Savings Deposits | liability | P | `DEP_SAVINGS` | MVP |
| 2120 | Current Deposits | liability | P | `DEP_CURRENT` | MVP |
| 2130 | Fixed Deposits | liability | P | `DEP_FIXED` | P4 |
| 2200 | Customer Deposits — Islamic | liability | H | | P4 |
| 2210 | Mudarabah Savings | liability | P | `DEP_MUDARABAH_SAV` | P4 |
| 2220 | Mudarabah Term Investments | liability | P | `DEP_MUDARABAH_TERM` | P4 |
| 2230 | Wadiah Current | liability | P | `DEP_WADIAH` | Later |
| **3000** | **Equity** | equity | H | | MVP |
| 3100 | Paid-up Capital | equity | P | `CAPITAL` | MVP |
| 3200 | Retained Earnings | equity | P | `RETAINED_EARNINGS` | MVP (EOD year-end later) |
| **4000** | **Income** | income | H | | MVP |
| 4100 | Fee & Commission Income | income | P | `INC_FEES` | P4 |
| 4200 | FX Income | income | P | `INC_FX` | P4 |
| 4300 | Financing / Interest Income | income | P | `INC_FINANCING` | P3 |
| 4900 | Cash Over | income | P | `CASH_OVER` | MVP |
| **5000** | **Expenses** | expense | H | | MVP |
| 5100 | Interest / Profit Paid to Depositors | expense | P | `EXP_PROFIT_PAID` | P4 |
| 5900 | Cash Short | expense | P | `CASH_SHORT` | MVP |

## Sub-ledgers (how detail ties to the GL)
| Control account | Detail lives in | Link on `journal_line` | Reconciliation rule |
|-----------------|-----------------|------------------------|---------------------|
| 1110 Cash in Vault | `cash_position` (holder = vault) | `cash_holder_type/id` | Σ vault positions = GL 1110, per currency |
| 1120 Cash at Tellers | `cash_position` (holder = teller_session) | `cash_holder_type/id` | Σ teller positions = GL 1120, per currency |
| 2110 / 2120 | `account.ledger_balance` | `account_id` | Σ account balances of that product kind = GL, per currency |

Every line on a control account **must** carry its sub-ledger link (service
check). EOD fails if any reconciliation rule is off.

## Product → GL mapping (MVP)
| Product kind | banking_model | Deposit GL |
|--------------|---------------|------------|
| savings | conventional | 2110 `DEP_SAVINGS` |
| current | conventional | 2120 `DEP_CURRENT` |

## Bank opening entry (when a bank is created)
The bank starts with capital held as cash in the vault, per currency:

```
Dr 1110 Cash in Vault   (vault of main branch)   USD 1,000,000.00
    Cr 3100 Paid-up Capital                       USD 1,000,000.00
Dr 1110 Cash in Vault                             SOS 5,000,000,000.00
    Cr 3100 Paid-up Capital                       SOS 5,000,000,000.00
```
Amounts are template parameters (`opening_capital_usd`, `opening_capital_sos`);
the values above are defaults. Seed customers' opening balances are posted the
same way (Dr Cash in Vault / Cr deposit GL) so the books always balance.

## Statement layout
- **Trial Balance:** every postable account with Dr/Cr balance, per currency; totals equal.
- **Balance Sheet:** Assets = Liabilities + Equity + (Income − Expenses for the open period).
- **Income Statement:** 4xxx − 5xxx for a date range.
