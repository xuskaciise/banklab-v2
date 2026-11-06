# Roles, Permissions, Limits & Approvals — BankLab V2 (Phase 0.4)

Defaults seeded into `role_permission` and `limit_rule`. The instructor can
override permissions per session (`permission_override`) and edit limits per
bank. The server enforces everything; the UI only hides what is not allowed.

## 1. Platform roles (`user.platform_role`)
| Role | Can do |
|------|--------|
| `admin` | Manage instructors, institution settings, CoA/session templates; everything an instructor can |
| `instructor` | Own classes: students (manual/CSV, reset password), sessions (open/archive/re-open), banks/groups, assign bank roles, visibility (session or per student), Dr/Cr panel, permission overrides, limits, exams (tasks, timing, grading), read everything in their sessions (all banks, audit log, reports). Never posts banking transactions |
| `student` | Works only inside sessions they are a member of, through their active bank role |

## 2. Bank roles (`role_assignment.role`)
A member has **one active bank role at a time**; the instructor rotates it.

| Code | Name | Purpose |
|------|------|---------|
| `teller` | Teller | Cash counter: deposits, withdrawals, cheques, own till |
| `cso` | Customer Service Officer | Customers, accounts, chequebooks, transfers |
| `manager` | Supervisor / Manager | Approvals, till open/close sign-off, vault dual control, EOD |
| `vault_custodian` | Vault Custodian | Vault cash in/out (first approver) |
| `accountant` | Accountant | GL, financial reports, reconciliation (read-only on postings) |

## 3. Visibility
- `own` mode applies to **teller** and **cso**: they see rows they created plus shared seed data (and their own exam seed data).
- **manager, vault_custodian, accountant always see the whole bank** — their duties (approvals, vault, GL) need it.
- Exams force `own` for everyone.

## 4. Permission matrix (defaults)
✓ = allowed · A = allowed, may need approval (see §5) · – = not allowed

| Permission code | Teller | CSO | Manager | Vault Cust. | Accountant |
|-----------------|:-:|:-:|:-:|:-:|:-:|
| `customer.view` | ✓ | ✓ | ✓ | – | ✓ |
| `customer.create` / `customer.update` | – | ✓ | ✓ | – | – |
| `account.view` (incl. balance) | ✓ | ✓ | ✓ | – | ✓ |
| `account.open` / `account.close` | – | ✓ | ✓ | – | – |
| `account.statement` | ✓ | ✓ | ✓ | – | ✓ |
| `chequebook.issue` | – | ✓ | ✓ | – | – |
| `cheque.stop` | – | ✓ | ✓ | – | – |
| `till.open.request` / `till.close` | ✓ | – | – | – | – |
| `till.open.approve` / `till.close.approve` | – | – | ✓ | – | – |
| `cash.vault_to_teller.request` | ✓ | – | ✓ | – | – |
| `cash.teller_to_vault.request` | ✓ | – | – | – | – |
| `cash.teller_to_teller.request` | ✓ | – | – | – | – |
| `cash.vault.approve` (1st, custodian) | – | – | – | ✓ | – |
| `cash.vault.approve` (2nd, manager) | – | – | ✓ | – | – |
| `txn.cash_deposit` | A | – | – | – | – |
| `txn.cash_withdrawal` | A | – | – | – | – |
| `txn.cheque_withdrawal` | A | – | – | – | – |
| `txn.transfer` | A | A | – | – | – |
| `txn.reverse` (own, same day) | ✓ | ✓ | – | – | – |
| `approval.decide` (limits, teller-to-teller) | – | – | ✓ | – | – |
| `vault.view` | – | – | ✓ | ✓ | ✓ |
| `gl.view` / `report.financial` (TB, BS, IS, GL) | – | – | ✓ | – | ✓ |
| `report.operational` (teller, branch, journal) | own | own | ✓ | – | ✓ |
| `eod.run` | – | – | ✓ | – | – |
| `audit.view` | – | – | ✓ (own bank) | – | – |

Instructor overrides can add or remove any of these per role and session,
except the separation rules in §6.

## 5. Default limits (`limit_rule`, per bank, editable)
Above the limit the transaction goes to the approval queue (`manager`).

| Role | Transaction | USD | SOS |
|------|-------------|----:|----:|
| teller | cash_withdrawal / cheque_withdrawal | 5,000.00 | 125,000,000.00 |
| teller | cash_deposit | 20,000.00 | 500,000,000.00 |
| teller / cso | transfer | 10,000.00 | 250,000,000.00 |

Cash transfers involving the vault **always** need both approvals, whatever the amount.

## 6. Separation-of-duties rules (cannot be overridden)
1. **Maker ≠ checker:** nobody approves their own request or transaction.
2. Vault dual control: the two approvals come from two different people
   (custodian then manager).
3. A teller posts only through their own `open` teller session.
4. Instructors never post banking transactions (they observe and grade).
5. Archived sessions: read-only for everyone.

## 7. Approval types (`approval.reason`)
| Reason | Raised by | Decided by | On approve | On reject |
|--------|-----------|------------|------------|-----------|
| `limit` | Teller / CSO transaction over limit | Manager | Post the transaction | Status `rejected`, nothing posted |
| `till_open` | Teller opening a session | Manager | Session `open` | Stays `pending_open` |
| `till_close` | Teller closing with a count | Manager | Post over/short, return cash (B2), session `closed` | Teller recounts |
| `dual_control` | Vault cash transfer | Custodian, then Manager | Post B1/B2 | Status `rejected` |
| `teller_to_teller` | Sending teller | Manager | Post B3 | Status `rejected` |
