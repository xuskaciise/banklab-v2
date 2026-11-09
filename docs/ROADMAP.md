# BankLab V2 — Build Roadmap

Single source of truth for **what to build next**. Work top to bottom: an item
starts only when everything in its `Needs` column is `[x]`. One item = one
feature branch = one PR. When an item is merged, tick it and add the PR link.

Status: `[ ]` todo · `[~]` in progress (branch name) · `[x]` done (PR)

Domain details for every item live in [CONCEPT.md](CONCEPT.md).

## Phase 0 — Design & scaffold

| # | Item | Needs | Status |
|---|------|-------|--------|
| 0.1 | ERD: all entities, keys, `bank_id` scoping (`docs/design/erd.md`) | – | [x] feat/0.1-erd |
| 0.2 | Chart of Accounts template, USD + SOS (`docs/design/coa.md`) | 0.1 | [x] feat/0.2-coa |
| 0.3 | Transaction catalog: every transaction type with its Dr/Cr lines (`docs/design/transactions.md`) | 0.2 | [x] feat/0.3-transactions |
| 0.4 | Roles × permissions matrix, limits, approvals (`docs/design/permissions.md`) | 0.1 | [x] feat/0.4-permissions |
| 0.5 | Screen list per role + navigation (`docs/design/screens.md`) | 0.4 | [x] feat/0.5-screens |
| 0.6 | Scaffold monorepo: `backend/` (Django + Ninja + pytest), `frontend/` (Next.js + TS + Tailwind + shadcn), Docker Compose, OpenAPI → TS types, CI checks | 0.1 | [x] feat/0.6-scaffold |

## Phase 1 — MVP (build order)

| # | Item | Needs | Status |
|---|------|-------|--------|
| 1.1 | Auth: student ID + last-4-phone first login, forced change, instructor reset | 0.6 | [x] feat/1.1-auth |
| 1.1b | Student login: Student ID + password (first = last 4 phone digits, forced change); staff login separate | 1.1 | [x] feat/1.1b-student-login |
| 1.2 | Roles & permissions catalog + defaults + permission check service, audit log (per-session overrides move to 1.3, they need Session) | 1.1, 0.4 | [x] feat/1.2-permissions-audit |
| 1.3 | Classes & Sessions: create/open/archive, templates, permission overrides, students (manual + CSV), role assignment, visibility mode, business date | 1.2 | [x] feat/1.3-classes-sessions |
| 1.3b | UI shell & design system: collapsible navy sidebar (mobile drawer), topbar (breadcrumbs, user menu, role badge), reusable components (PageHeader, StatCard, DataTable, StatusBadge, EmptyState, Skeleton, ConfirmDialog, toasts), staff overview dashboard from real data, redesign of 1.3 screens. Only built pages appear in the nav. | 1.3 | [x] feat/1.3b-ui-shell |
| 1.4 | Ledger engine: CoA per session from template, journal entries, posting service, balances (Decimal, row locks, Dr = Cr enforced) | 1.3, 0.3 | [x] |
| 1.5 | Branch & Vault (dual control) | 1.4 | [x] feat/1.5-branch-vault |
| 1.6 | Customers (CIF): individual, company, joint, NGO; ID documents; signatories | 1.3 | [x] feat/1.6-customers |
| 1.7 | Products (Savings, Current) & Accounts (Active/Closed, sequential numbers, USD/SOS); open only if customer `kyc_complete` (see CONCEPT §3) | 1.4, 1.6 | [x] feat/1.7-accounts |
| 1.8 | Teller session: open with supervisor approval, denomination count on close, over/short | 1.5 | [x] feat/1.8-teller-session |
| 1.9 | Transactions: cash deposit, cash withdrawal, transfer (same currency), depositor name/ID/phone, teller limits + supervisor approval, reversal, PDF receipt | 1.7, 1.8 | [x] |
| 1.10 | Cheques: chequebook issue (series), paid once, stop payment | 1.9 | [ ] |
| 1.11 | End-of-Day by Manager: all tellers closed → close day → next business date | 1.9 | [ ] |
| 1.12 | Reports: statement, teller cash, branch daily, transaction journal, TB, BS, IS, GL ledger — PDF + Excel | 1.11 | [ ] |
| 1.13 | Dashboards (instructor, manager, teller) + Dr/Cr learning panel toggle | 1.12 | [ ] |
| 1.14 | Exam sessions: timer, tasks, per-student seed data, auto-check, scores, results export | 1.13 | [ ] |
| 1.15 | Hardening: load test (100–200 students), security review, deploy to VPS | 1.14 | [ ] |

## Later phases (do not start before Phase 1 is done)

- **Phase 2:** guided practice scenarios, instructor-injected events
- **Phase 3:** Loans; Murabaha, Musharakah, Qard Hasan
- **Phase 4:** FX (buy/sell, cross-currency), fees, interest/profit engine, Fixed Deposit, Mudarabah Savings/Term
- **Phase 5:** customer internet/mobile banking portal, mobile money simulation
- **Backlog:** KYC approval, risk rating/AML, Dormant/Frozen, Wadiah, bounced/cancelled cheques
