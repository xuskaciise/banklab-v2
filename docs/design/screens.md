# Screens & Navigation — BankLab V2 (Phase 0.5)

Every MVP screen, its route (Next.js App Router), who uses it and what it
does. Permissions come from [permissions.md](permissions.md); colours and
badges from [theme.md](theme.md). `R#` = ROADMAP item that builds it.

## Layout
- **Sidebar** (`bank-navy`): menu items filtered by the user's role/permissions.
- **Top bar (student, inside a session):** class › session › bank name ·
  **business date** · **active role** badge · pending-approvals bell (manager)
  · exam countdown (exam sessions) · user menu (change password, logout).
- **Top bar (instructor):** class/session switcher (dropdown) · "viewing as
  instructor" badge · user menu.
- Archived session ⇒ grey "Read-only" banner and all write buttons hidden.
- Dr/Cr learning panel: slide-over on the right after every posting (when enabled).

## 1. Public & account (R1.1)
| Route | Screen | Users | Purpose |
|-------|--------|-------|---------|
| `/login` | Student login | student | Student ID + Phone (no password) |
| `/staff/login` | Staff login | instructor, admin | Username + password |
| `/change-password` | Change password | staff only | Forced on first staff login; simple policy; students have no password |

## 2. Instructor & admin (R1.2, R1.3, R1.13, R1.14)
| Route | Screen | Purpose |
|-------|--------|---------|
| `/instructor` | Instructor dashboard | My classes, active sessions, live activity, pending exam grading |
| `/instructor/classes` | Classes | List / create class |
| `/instructor/classes/[id]` | Class detail | Tabs: **Students** (add, CSV import, reset password) · **Sessions** (list, open new, archive, re-open) · **Templates** |
| `/instructor/classes/[id]/import` | Student import | Upload CSV → preview → errors → confirm |
| `/instructor/sessions/new` | Open session wizard | Name, kind (practice/exam), template, structure (single bank / per group), allowed roles, visibility, Dr/Cr panel, seed profile |
| `/instructor/sessions/[id]` | Session control | Tabs: **Members** (bank/group, active role, visibility override) · **Banks** · **Permissions** (overrides) · **Limits** · **Activity** (audit log, filters) · **Settings** (business date, archive) |
| `/instructor/sessions/[id]/view/[bankId]` | Observe bank | Read-only view of any bank screen (as instructor) |
| `/instructor/templates` | Session & CoA templates | Edit session templates and the CoA template |
| `/instructor/exams/[sessionId]` | Exam setup | Timing, instructions, tasks (check type, params, points), publish |
| `/instructor/exams/[sessionId]/results` | Exam results | Scores per student, task details, manual adjust, export PDF/Excel |
| `/admin/instructors` | Instructors (admin) | Create/disable instructors |

## 3. Student — session entry (R1.3)
| Route | Screen | Purpose |
|-------|--------|---------|
| `/sessions` | My sessions | Active sessions I am in (archived ones hidden); open → role home |
| `/s/[sessionId]` | Role home / dashboard | Redirects to the dashboard of my active role |

All banking routes below live under `/s/[sessionId]/…` and are scoped to my bank.

## 4. Teller (R1.8–R1.10, R1.13)
| Route | Screen | Purpose |
|-------|--------|---------|
| `…/teller` | Teller dashboard | Till status, cash by currency, today's transactions, pending approvals I raised |
| `…/teller/till` | My till | Request open (opening float) · request cash from vault · send to vault / another teller · close with **denomination count** (USD + SOS) |
| `…/teller/deposit` | Cash deposit | Find account → amount → depositor name/ID/phone → confirm → receipt |
| `…/teller/withdraw` | Cash withdrawal | Find account → balance + photo/signature check → amount → withdrawer details → confirm → receipt |
| `…/teller/cheque` | Cheque withdrawal | Account + cheque no. → validity check → amount → receipt |
| `…/teller/transfer` | Transfer | From/to account, amount, narration |
| `…/transactions` | My transactions | List, filters, receipt reprint, **reverse** (own, same day) |

## 5. CSO (R1.6, R1.7, R1.10)
| Route | Screen | Purpose |
|-------|--------|---------|
| `…/cso` | CSO dashboard | Customers/accounts opened today, quick search |
| `…/customers` | Customers | Search/list (own or all per visibility) |
| `…/customers/new` | New customer | Type (individual/company/joint/NGO) → parties → ID documents → photo/signature → next of kin |
| `…/customers/[id]` | Customer 360 | Profile, parties/signatories, documents, accounts, recent transactions |
| `…/accounts/new` | Open account | Customer → product (Savings/Current) → currency → mandate |
| `…/accounts/[id]` | Account | Balance, status, statement, chequebooks, close account |
| `…/accounts/[id]/chequebooks` | Chequebooks | Issue chequebook, cheque list, **stop payment** |

## 6. Manager (R1.5, R1.8, R1.9, R1.11, R1.13)
| Route | Screen | Purpose |
|-------|--------|---------|
| `…/manager` | Manager dashboard | Branch cash (vault + tills per currency), open tills, approvals queue, day status |
| `…/approvals` | Approvals | Queue by type (limit, till open/close, dual control, teller-to-teller); approve/reject with note |
| `…/tills` | Tills overview | Every teller session today: status, balances, over/short |
| `…/limits` | Limits | View bank limits (edit only if instructor allows) |
| `…/eod` | End of Day | Checklist (tills closed, no pending, reconciliation, TB) → close day |
| `…/audit` | Audit log | Bank activity |

## 7. Vault Custodian (R1.5)
| Route | Screen | Purpose |
|-------|--------|---------|
| `…/vault` | Vault | Balances per currency, pending cash transfers to approve (1st approval), history |

## 8. Accountant & reports (R1.12)
| Route | Screen | Purpose |
|-------|--------|---------|
| `…/accountant` | Accountant dashboard | TB status, reconciliation status per currency |
| `…/gl` | Chart of accounts | GL accounts with balances per currency |
| `…/gl/[accountId]` | GL ledger | Lines for one GL account, date range |
| `…/reports/trial-balance` | Trial Balance | Per currency, PDF/Excel |
| `…/reports/balance-sheet` | Balance Sheet | Per currency |
| `…/reports/income-statement` | Income Statement | Date range |
| `…/reports/journal` | Transaction journal | All transactions of a day, filters |
| `…/reports/teller-cash` | Teller cash report | Per teller session |
| `…/reports/branch-daily` | Branch daily report | Totals + vault position |
| `…/accounts/[id]/statement` | Account statement | Date range, opening/closing balance, PDF/Excel (also used by teller/CSO) |

## 9. Exam (R1.14)
| Route | Screen | Purpose |
|-------|--------|---------|
| `…/exam` | Exam home | Instructions, task list with tick status, countdown, **Submit** |
| (all role screens) | — | Same screens as practice, own-work only, no Dr/Cr panel, locked when time ends |
| `…/exam/result` | My result | Shown when the instructor publishes results |

## Shared components
Account picker (search by no./name, shows photo + signature) · Amount input
(currency-aware, amount-in-words) · Party details form (name, ID, phone) ·
Denomination counter · Receipt (PDF) · Status badge · Dr/Cr panel ·
Data table (filters, pagination, export) · Approval card.
