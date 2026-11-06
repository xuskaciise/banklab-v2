# ERD — BankLab V2 (Phase 0.1)

Entities, keys and scoping for the MVP (ROADMAP Phase 1). Later-phase tables
(loans, FX, fees, interest) are out of scope but must fit without breaking
these keys.

Conventions
- PK `id` = UUID (except lookup tables). `created_at`, `updated_at` on every table.
- Money: `NUMERIC(18,2)` + `currency` (`USD` | `SOS`).
- `*_by` columns reference `session_member.id` inside a bank (who acted in a
  role), or `user.id` for platform actions (instructor/admin).
- **Scoping key = `bank_id`.** Every banking row carries `bank_id`; a bank
  belongs to exactly one session, so session isolation follows from it.
  Queries always filter by `bank_id`.
- **"Own work only" filter:** `created_by = me OR (is_seed AND (seed_owner_id IS NULL OR seed_owner_id = me))`.
  Shared seed data (`seed_owner_id` null) is visible to everyone; exam seed data is
  assigned to one student (`seed_owner_id`) and only they see it.

```
Institution ─< Class ─< Session ─< Bank ─< (all banking data)
                 │          │        └─< SessionMember ─< RoleAssignment
                 └─< Enrollment >─ User
```

---

## 1. Platform & Lab

| Table | Key columns | Notes |
|-------|-------------|-------|
| `institution` | name | One row for now; keeps multi-institution open |
| `user` | institution_id, username (unique, = student ID / staff ID), full_name, phone, password_hash, must_change_password, platform_role (`admin`/`instructor`/`student`), is_active | First password = last 4 digits of phone |
| `class` | institution_id, instructor_id, name, code | e.g. "Banking – Semester 5"; one instructor per class |
| `enrollment` | class_id, user_id | Students in a class (manual or CSV import) |
| `session_template` | class_id (nullable = institution-wide), name, kind, structure, allowed_roles[], default_visibility, learning_panel, seed_profile, coa_template_id, product_set | "Teller lecture" preset → one click |
| `session` | class_id, template_id?, name, kind (`practice`/`exam`), structure (`single_bank`/`per_group`), status (`draft`/`active`/`archived`), default_visibility (`own`/`all`), learning_panel (bool), opened_at, archived_at | One lecture or one exam. Archived ⇒ read-only |
| `bank` | session_id, name, group_no | The lab bank. 1 per session (single) or 1 per group |
| `session_member` | session_id, bank_id, user_id, visibility_override (`own`/`all`/null) | Student placed in a bank; override beats session default |
| `role_assignment` | session_member_id, role (`teller`/`cso`/`supervisor`/`vault_custodian`/`accountant`), assigned_by, active_from, active_to | Rotation history; instructor assigns |
| `permission` | code (PK), description | Catalog, e.g. `txn.cash_deposit.create` |
| `role_permission` | role, permission_code | Defaults |
| `permission_override` | session_id, role, permission_code, allowed | Instructor edits per session |
| `audit_log` | session_id, bank_id?, actor_user_id, actor_role, action, entity_type, entity_id, before (json), after (json), at | Every write. Doubles as the instructor's activity log |

## 2. Organisation, cash & business day

| Table | Key columns | Notes |
|-------|-------------|-------|
| `branch` | bank_id, code, name, address | |
| `business_day` | bank_id, date, status (`open`/`closed`), closed_by, closed_at | One open day per bank; EOD closes it and opens the next |
| `denomination` | currency, value, kind (`note`/`coin`) | Lookup (USD 100…1, SOS notes) |
| `vault` | bank_id, branch_id | One per branch |
| `till` | bank_id, branch_id, code | Physical teller drawer |
| `cash_position` | bank_id, holder_type (`vault`/`teller_session`), holder_id, currency, balance | Cash on hand; updated only by the posting service |
| `teller_session` | bank_id, till_id, teller_member_id, business_date, status (`pending_open`/`open`/`closing`/`closed`), open_approved_by, opened_at, closed_at | One per teller per day |
| `cash_count` | teller_session_id, kind (`open`/`close`), currency, counted_total, system_total, difference, approved_by | Over/short = difference |
| `cash_count_line` | cash_count_id, denomination_id, quantity | |
| `cash_transfer` | bank_id, from_type/from_id, to_type/to_id (vault/teller_session), currency, amount, status (`pending`/`approved`/`rejected`/`posted`), requested_by, approved_by_1, approved_by_2, journal_entry_id | Vault ⇄ teller, teller ⇄ teller; vault moves need two approvers |

## 3. Customers (CIF)

| Table | Key columns | Notes |
|-------|-------------|-------|
| `customer` | bank_id, cif_no (seq per bank), type (`individual`/`company`/`joint`/`ngo`), display_name, phone, email, address, reg_no (company/NGO), created_by, is_seed, seed_owner_id? | `seed_owner_id` = session_member for per-student exam seeds |
| `party` | bank_id, full_name, sex, date_of_birth, phone, photo, signature | A real person (owner, joint holder, signatory, director) |
| `customer_party` | customer_id, party_id, relation (`owner`/`joint_holder`/`signatory`/`director`), can_sign | Joint and company mandates |
| `identity_document` | party_id, type (`national_id`/`passport`/`local_letter`), number, issue_date, expiry_date, file | |
| `next_of_kin` | party_id, name, phone, relationship | |

## 4. Products & accounts

| Table | Key columns | Notes |
|-------|-------------|-------|
| `product` | bank_id, code, name, kind (`savings`/`current`), banking_model (`conventional`/`islamic`), currency, min_balance, allows_cheques, gl_account_id | Copied from the template product set when the bank is created |
| `account` | bank_id, account_no (seq per bank), customer_id, product_id, currency, status (`active`/`closed`), mandate (`any_one`/`all_jointly`), ledger_balance, created_by, is_seed, seed_owner_id?, opened_at, closed_at | `ledger_balance` only via posting service; CHECK ≥ 0 (no overdraft in MVP) |

## 5. Ledger (GL)

| Table | Key columns | Notes |
|-------|-------------|-------|
| `coa_template` / `coa_template_line` | name / code, name, type, parent_code, postable, system_tag | Institution template, instructor-editable |
| `gl_account` | bank_id, code, name, type (`asset`/`liability`/`equity`/`income`/`expense`), parent_id, postable, system_tag | `system_tag` e.g. `CASH_VAULT`, `CASH_TELLER`, `DEPOSITS_SAVINGS`, `CASH_OVER_SHORT` |
| `journal_entry` | bank_id, entry_no, business_date, source_type, source_id, description, reversal_of_id, posted_by, posted_at | Immutable |
| `journal_line` | entry_id, gl_account_id, currency, debit, credit, account_id?, cash_holder_type/id? | Σdebit = Σcredit per currency per entry (enforced in service + deferred DB check) |
| `gl_balance` | bank_id, gl_account_id, currency, balance | Running balance for fast TB/BS |

## 6. Transactions, approvals, cheques

| Table | Key columns | Notes |
|-------|-------------|-------|
| `transaction` | bank_id, ref_no, type (`cash_deposit`/`cash_withdrawal`/`transfer`/`cheque_withdrawal`/`reversal`), status (`pending_approval`/`posted`/`rejected`/`reversed`), amount, currency, account_id, counter_account_id?, teller_session_id?, cheque_id?, party_name, party_id_no, party_phone, narration, business_date, created_by, journal_entry_id, reversal_of_id | Receipt PDF is rendered from this row |
| `limit_rule` | bank_id, role, txn_type, currency, max_amount | Above max ⇒ approval |
| `approval` | bank_id, subject_type, subject_id, reason (`limit`/`till_open`/`dual_control`), requested_by, decided_by, status, decided_at, note | Generic maker–checker queue |
| `chequebook` | bank_id, account_id, first_no, last_no, issued_by, issued_at | |
| `cheque` | chequebook_id, number, status (`issued`/`paid`/`stopped`), transaction_id?, stopped_by, stop_reason | `paid` once only |

## 7. Exam

| Table | Key columns | Notes |
|-------|-------------|-------|
| `exam` | session_id (1:1), starts_at, ends_at, duration_minutes, instructions, results_published | Exam session = one bank, visibility forced to `own`; each student gets own seed customers/accounts (`seed_owner_id`) and own till |
| `exam_task` | exam_id, position, title, instructions, check_type, check_params (json), points | Checks run on the student's own rows only, e.g. `account_balance_equals` (their seed account), `till_closed_balanced` (their teller session), `txn_exists` (posted by them). Bank-wide GL checks are not per-student |
| `exam_attempt` | exam_id, session_member_id, started_at, submitted_at, score | |
| `exam_task_result` | attempt_id, task_id, passed, points, details (json), adjusted_by, adjusted_points | Auto-check + instructor adjustment |

## 8. Jobs & files

| Table | Key columns | Notes |
|-------|-------------|-------|
| `report_export` | bank_id, requested_by, report_type, params (json), format (`pdf`/`xlsx`), status, file | Large reports built in the background |
| `student_import` | class_id, file, status, rows_ok, rows_failed, errors (json) | CSV import |

---

## Key rules this design enforces
- Isolation: nothing references across banks; every FK chain ends at one `bank_id`.
- Balances (`account.ledger_balance`, `cash_position.balance`, `gl_balance.balance`)
  are written only by the posting service inside the entry's transaction.
- No deletes on `transaction`, `journal_*`, `cheque`, `cash_*`; reversal rows instead.
- Seed data (`is_seed = true`) is created by the system when a bank is created
  from the template's `seed_profile`.
