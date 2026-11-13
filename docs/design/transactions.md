# Transaction Catalog — BankLab V2 (Phase 0.3)

Every MVP operation that moves money, with its journal lines (GL codes from
[coa.md](coa.md)), who may do it, approvals, checks and side effects. The
posting service implements exactly these templates; anything not listed here
cannot post.

Notation: `Dr 1120 [teller]` = debit GL 1120 with sub-ledger link to the
teller session; `[acct]` = link to a customer `account`; `[vault]` = vault.
`DEP(acct)` = deposit GL of the account's product (2110 savings / 2120 current).
All lines in one entry share one currency; amount `A` > 0.

## Common rules (every posting)
1. Business day of the bank is `open`; session is not archived.
2. Actor has the permission for the type (see permissions.md) and an active
   role assignment in this bank.
3. Amount > 0, max 2 decimals, currency matches the account / cash holder.
4. Above the actor's `limit_rule` ⇒ create `approval` (status `pending_approval`);
   post only when approved. Below ⇒ post immediately.
5. One `transaction.atomic()`: lock rows (`select_for_update`) on affected
   accounts / cash positions in a fixed order (accounts by id, then cash
   holders by id) → validate balances → insert `journal_entry` + lines →
   update `account.ledger_balance`, `cash_position.balance`, `gl_balance` →
   write `audit_log`.
6. Balances may never go below zero (accounts, tills, vault).
7. Every posted transaction gets a `ref_no` (`{bank}-{yyyymmdd}-{seq}`) and a
   printable PDF receipt.

---

## A. Setup postings (system)

### A1. Bank opening capital — when a bank is created
| Dr/Cr | GL | Link |
|---|---|---|
| Dr | 1110 Cash in Vault | [vault] |
| Cr | 3100 Paid-up Capital | – |
One entry per currency. Actor: system. *Learning:* cash (asset) ↑, owners' equity ↑.

### A2. Seed account opening balance — when seed data is created
| Dr | 1110 Cash in Vault [vault] |
|---|---|
| **Cr** | **DEP(acct) [acct]** |
Actor: system. Marks rows `is_seed`.

## B. Cash management

### B1. Vault → Teller (issue cash, incl. opening float)
| Dr | 1120 Cash at Tellers [teller] |
|---|---|
| **Cr** | **1110 Cash in Vault [vault]** |
- Requested by: Teller or Supervisor. Approved by: **Vault Custodian + Manager** (dual control, two different people).
- Opening float also needs the **Supervisor's till-open approval** (`teller_session` → `open`).
- Check: vault balance ≥ A. *Learning:* cash moves inside the bank; total cash unchanged.

### B2. Teller → Vault (return cash)
| Dr | 1110 Cash in Vault [vault] |
|---|---|
| **Cr** | **1120 Cash at Tellers [teller]** |
- Requested by Teller; received/approved by **Vault Custodian + Manager**.
- Check: till balance ≥ A.

### B3. Teller → Teller
| Dr | 1120 [teller: receiver] |
|---|---|
| **Cr** | **1120 [teller: sender]** |
- Sender requests, Supervisor approves. Both teller sessions `open`.

## C. Customer transactions

### C1. Cash deposit
| Dr | 1120 Cash at Tellers [teller] |
|---|---|
| **Cr** | **DEP(acct) [acct]** |
- Actor: Teller with an `open` teller session. Account `active`.
- Record depositor name, ID no., phone (may differ from the owner).
- *Learning:* bank cash (asset) ↑, bank owes the customer more (liability ↑).

### C2. Cash withdrawal
| Dr | DEP(acct) [acct] |
|---|---|
| **Cr** | **1120 Cash at Tellers [teller]** |
- Actor: Teller (`open` session). Checks: account `active`, account balance ≥ A, till balance ≥ A.
- Joint/company accounts: mandate satisfied (signatories recorded on the transaction).
- Record withdrawer name, ID no., phone.

### C3. Cheque withdrawal (cash at counter)
Same lines as **C2**, plus:
- Cheque belongs to this account's chequebook and has status `issued`
  (not `paid`, not `stopped`) ⇒ set `paid` and link the transaction.
- A cheque can be paid only once (unique `cheque.transaction_id`).

### C4. Transfer between accounts (same currency, no cash)
| Dr | DEP(from) [acct: from] |
|---|---|
| **Cr** | **DEP(to) [acct: to]** |
- Actor: Teller or CSO. Both accounts `active`, same bank, same currency, different accounts. From-balance ≥ A.
- No till involved. *Learning:* liabilities move between customers; bank totals unchanged.

## D. Corrections

### D1. Reversal
- New entry with every line of the original swapped (Dr ↔ Cr), same amounts,
  `reversal_of_id` = original; original `transaction.status` → `reversed`.
- Actor: the Teller who posted it (decision: teller reverses directly), **same
  business day only**; otherwise not allowed in MVP.
- Checks: original is `posted` and not already reversed; reversal must not make
  any balance negative (e.g. a deposit already withdrawn ⇒ rejected).
- C3 reversal sets the cheque back to `issued`.

## E. Teller close & End of Day

### E1. Teller close — over / short
At close the teller enters a denomination count; `difference = counted − system`.
| Case | Dr | Cr |
|---|---|---|
| Over (difference > 0) | 1120 [teller] | 4900 Cash Over |
| Short (difference < 0) | 5900 Cash Short | 1120 [teller] |
- Posted per currency when the **Supervisor approves the close**.
- Then all remaining till cash goes back with **B2**; a closed till holds 0.

### E2. End of Day (Manager)
No journal entries in MVP (no interest/fees). Pre-checks, all must pass:
1. Every teller session of the day is `closed`.
2. No `pending_approval` transactions or cash transfers.
3. Sub-ledger reconciliation (coa.md) holds for every currency.
4. Trial balance balances per currency.
Then `business_day` → `closed` and the next date is opened.

## F. Non-posting operations (no journal entry)
| Operation | Rule |
|---|---|
| Open account | Product currency; status `active`; balance 0 |
| Close account | Balance must be exactly 0 and no pending items |
| Issue chequebook | Account product `allows_cheques`; new number series, no overlap |
| Stop payment | Cheque status `issued` → `stopped`; reason required |
