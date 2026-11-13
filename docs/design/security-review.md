# Security review (ROADMAP 1.15)

**Scope:**

- Every Django Ninja endpoint, focusing on money paths, file downloads and
  student/exam access.
- Auth and login throttling.
- Production settings.
- Deploy topology: shared VPS → nginx → containers, with Cloudflare in front.

The review was done by grep sweeps plus two `ledger-reviewer` passes over all
`apps/*/api.py` files and their services.

## Fixed

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | Medium | **Exam answer leak:** in exam sessions (one bank, "own work only"), a student with the Accountant or Manager role could read every other student's postings. This was possible through `/journal`, `/gl/accounts` balances, the bank-wide GL reports (trial balance, balance sheet, income statement, GL ledger), `/vault`, `/cash-transfers` and EOD status. | Own-visibility readers now see only their own journal entries. The GL chart shows no balances. Bank-wide GL reports, the vault and EOD status return 403. Cash transfers list only the reader's own. Tests: `tests/test_own_visibility.py`. The UI shows a "not available in this session" state. |
| 2 | Medium | **Client IP:** the login throttle and audit used `REMOTE_ADDR`, which behind Cloudflare and nginx is one proxy IP for everyone. | `apps/core/net.py client_ip()` reads `CLIENT_IP_HEADER`, but only when the value is a valid IP *and* the request carries the nginx shared secret (`PROXY_SHARED_SECRET` / `X-BankLab-Proxy`). Other containers on the shared proxy network cannot forge it. nginx restores the real IP from `CF-Connecting-IP`, trusted only from Cloudflare ranges. `ProxyTrustMiddleware` drops a forged `X-Forwarded-Proto` the same way. |
| 3 | Medium | **Login throttle vs one-NAT classroom:** the per-IP budget counted successful logins too, so a class of 200 behind one IP could lock itself out. | The per-IP budget counts failures only. The per-user+IP and per-ID caps still count every attempt. |
| 4 | Medium | **Case-insensitive usernames:** `S5101` and `s5101` could both exist. Instructor create and CSV import used case-sensitive checks. | Migration `accounts.0006` adds `UniqueConstraint(Lower("username"))`; the dev DB had 0 collisions. All create, import, rename and login lookups use `Lower()`, so login accepts any case of the ID. |
| 5 | Medium | `/api/docs` and `/api/openapi.json` were public in production. | They are staff-only when `DEBUG` is off and still open in dev for type generation. |
| 6 | Medium | The `seed_loadtest` command could be run against a real DB. That would create 200 shared-password users and ledger rows that can never be deleted. | It refuses unless the DB name contains `loadtest` or `DJANGO_DEBUG=true`. |
| 7 | Low | A placeholder or short `DJANGO_SECRET_KEY` was accepted in production. | Settings refuse to start with `DEBUG` off and a key shorter than 32 characters or one containing `change-me`. |
| 8 | Low | Production hardening was missing. | Env-driven `SECURE_PROXY_SSL_HEADER`, HSTS, nosniff, `Referrer-Policy: same-origin`, COOP, `X-Frame-Options: DENY`, WhiteNoise static files, DB `conn_health_checks`, and stdout logging. `manage.py check --deploy` shows only W004 (HSTS) and W008 (SSL redirect), which are intentional behind Cloudflare and are explained in `docs/deploy.md`. |
| 9 | Low | Production containers ran as root, and the dev server was the only runtime. | `Dockerfile.prod` images use a non-root user, gunicorn and Next.js standalone. Ports bind to 127.0.0.1 only, and the DB sits on a private network. |

## Checked, no issue found

- **Auth on endpoints:** `auth=None` is used only on csrf, both logins and health. Every other endpoint uses the active-session auth.
- **Unsafe code patterns:** there is no `csrf_exempt`, raw SQL string building, `mark_safe` or `|safe`.
- **Bank scoping:** every get-by-id is filtered by bank, session or institution, and by owner where visibility is "own".
- **Money paths:** cash transfers, tills, transactions, cheques and EOD lock rows in a fixed order, enforce maker-checker, and write audit.
- **Archived sessions:** all writes return 409.
- **File downloads:** these go through the visibility check and the party link. Responses carry `nosniff`, `no-store` and a sandbox CSP. Media is never served statically.
- **Error responses:** no traceback is exposed outside DEBUG.

## Open / accepted

- **Cloudflare SSL mode is likely "Flexible"** (Cloudflare → nginx over plain HTTP). Recommended: switch to "Full (strict)" with a Cloudflare Origin Certificate, and firewall ports 80/443 to Cloudflare's IP ranges so the origin cannot be reached directly. This is a VPS/Cloudflare change for the owner (`docs/deploy.md`).
- **`PROXY_SHARED_SECRET` unset:** the app trusts proxy headers from anyone that can reach it. The documented setup always sets it.
- **Limit-rule race:** the limit check (`needs_approval`) now runs before the bank lock. A limit rule edited at the same instant could apply to one in-flight transaction. Balances and tills are still checked under lock. Accepted.
- **Non-ASCII usernames:** usernames differing only in non-ASCII case (e.g. "ß") are not normalised beyond `lower()`. IDs are ASCII in practice.
- **Password hashing:** stays at Django's default (PBKDF2, 1M iterations). Login bursts are CPU-bound; see `loadtest.md`.
