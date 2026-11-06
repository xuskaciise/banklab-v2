# BankLab V2 — working rules

BankLab is a **training bank** for college banking students (not a real bank).
Instructors open class sessions; students play bank roles (Teller, CSO,
Supervisor/Manager, Vault Custodian, Accountant). V1 (PHP) lives in
`C:\projects\updated_bank` as a feature reference only — never copy its code.

- Product concept and all decisions: `docs/CONCEPT.md`
- **What to build next: `docs/ROADMAP.md`** — always take the first item whose
  `Needs` are done. Never build out of order or pull in later-phase features.
- Design docs (Phase 0 output): `docs/design/`

## Communication
- Talk to the user **in Somali**. Code, comments, commits, identifiers and UI
  text stay in English.
- Non-trivial feature: show the plan in Somali first and wait for approval.

## Stack
- `backend/`: Python 3.12, Django 5, Django Ninja (REST + OpenAPI), PostgreSQL,
  django-q2 (jobs), pytest.
- `frontend/`: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui +
  TanStack Query. API types are generated from the backend OpenAPI schema —
  never hand-write API types. Colours, status badges and amount formatting
  follow `docs/design/theme.md` (SIU bank tokens) — never hard-code hex
  values in components.
- Docker Compose for local and VPS.

## Domain invariants (never break)
1. **Ledger-first:** every money movement is a balanced journal entry
   (sum Dr = sum Cr) posted through the single posting service. No code
   updates a balance directly.
2. Money is `Decimal` (`NUMERIC(18,2)`), never float. Currency (USD/SOS) is
   stored with every amount. Totals are always computed on the server.
3. **Session scoping:** every business row has `session_id`; every query is
   filtered by the current session (and by owner when visibility is
   "own work only"). Tests must prove cross-session isolation.
4. Financial records are never deleted or edited — corrections are reversals.
   Archived sessions are read-only.
5. Multi-step writes run in one `transaction.atomic()` with
   `select_for_update()` on balances/tills. Balances never go negative unless
   a product allows it.
6. Every write is checked on the server for role permission, limits and
   approvals, and is written to the audit log.

## Workflow
- One ROADMAP item per feature branch `feat/<roadmap-no>-<slug>`; PR into
  `main`; never push to `main` directly. Tick the item in ROADMAP.md in the PR.
- Order inside a feature: model + migration → service (business rules) →
  API → tests → regenerate TS types → UI → e2e check in the browser.
- Before every push (all must pass):
  ```
  cd backend && ruff check . && pytest
  cd frontend && npm run typecheck && npm run lint && npm run build
  ```
- Migrations only via `python manage.py makemigrations`; never edit a
  migration that is already on `main`.

## Agents (`.claude/agents/`) and token economy
- `backend-dev` — Django models/services/API/tests for one ROADMAP item.
- `frontend-dev` — Next.js screens for an API that already exists.
- `ledger-reviewer` — read-only review of anything touching money, ledger,
  permissions or session scoping. Run before every PR that touches them.
- `test-runner` — runs checks and reports only failures (cheap model).
- Delegate searches, test runs and reviews to agents; they return short
  summaries. The main session plans, decides and talks to the user.
- Don't re-read files already in context; read only the needed range of big
  files; don't paste long logs — summarize.
- Keep one ROADMAP item per conversation where possible; start a fresh
  session for the next item instead of growing one long context.

## Secrets & servers
- Never print, log or commit secrets (`.env*`, DB URLs, keys, tokens). To
  check a value, print only whether it is set or its host.
- Never touch the VPS or a production database without the user's explicit OK.
  The VPS is shared with other projects — only touch BankLab's own compose
  project there.
