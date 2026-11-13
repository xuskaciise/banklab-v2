# Load test (ROADMAP 1.15)

Goal: one class of **100–200 students** working at the same time.

## How to run

The test must run on a **throwaway database**, because ledger rows can never
be deleted. `seed_loadtest` refuses to run unless the DB name contains
`loadtest` or `DJANGO_DEBUG=true`.

```bash
# 1. Throwaway DB on the dev Postgres
docker exec banklab-db-1 sh -c 'createdb -U "$POSTGRES_USER" banklab_loadtest'
# 2. Migrate + seed: 200 students in 4 banks, open tills, 10 funded accounts per bank.
#    Pick any password and pass it in LOADTEST_PASSWORD. It is never printed.
docker exec -e LOADTEST_PASSWORD=... banklab-backend-1 sh -c \
  'export DATABASE_URL=${DATABASE_URL%/*}/banklab_loadtest; python manage.py migrate && python manage.py seed_loadtest --students 200 --banks 4'
# 3. Serve that DB the production way (gunicorn, DEBUG off) on port 8001
docker exec -d -e DJANGO_SECRET_KEY=<32+ random chars> -e DJANGO_DEBUG=false -e GUNICORN_WORKERS=6 banklab-backend-1 sh -c \
  'export DATABASE_URL=${DATABASE_URL%/*}/banklab_loadtest; exec gunicorn config.wsgi:application -c gunicorn.conf.py -b 0.0.0.0:8001 --pid /tmp/glt.pid'
# 4. Run Locust: 200 users, 5 new users per second, 6 minutes
docker exec -e LOADTEST_PASSWORD=... banklab-backend-1 \
  locust -f loadtest/locustfile.py --host http://127.0.0.1:8001 -u 200 -r 5 -t 6m --headless --only-summary
```

What a simulated user does (`backend/loadtest/locustfile.py`), with 1–5 s
think time between steps:

- **Student:** logs in once. Then, at random:
  - opens the dashboard and `me`
  - searches customers and opens an account
  - views a statement and the transaction list
- **Teller:** does all of the above, plus cash deposits and withdrawals of 1–20 USD through the real posting API.
- **Instructor:** polls the instructor dashboard, banks and exam results.

The seed creates 184 tellers, 4 managers, 4 CSOs, 4 accountants, 4 vault
custodians and 1 instructor.

## Results

Test machine: dev laptop, Docker Desktop with 8 vCPU. Locust, gunicorn and
Postgres all ran on the same machine, so the numbers are pessimistic. Each
run used gunicorn with 6 workers × 4 threads, DEBUG off.

| Run | Change | Requests (6 min) | Cash txns | Deposit p50 / p95 | Dashboard p50 / p95 | Errors |
|---|---|---|---|---|---|---|
| 1 | baseline; tellers saw no accounts (seed bug) | 9,002 | 0 | n/a | 100 ms / 860 ms | 0.04 % |
| 2 | seed fixed, so cash flows on | 6,364 | 1,503 | **9.5 s / 23 s** | **5.5 s / 18 s** | 0.02 % |
| 3 | posting lock fixes (below) | 18,112 | 5,065 | **660 ms / 2.4 s** | **200 ms / 1.5 s** | 0.41 % (*) |
| 4 | same code as run 3, but the DB already held ~10k transactions for the same business day | 13,562 | 3,733 | 1.5 s / 9.4 s | 690 ms / 7.8 s | 0.27 % (*) |

(*) The only errors were `RemoteDisconnected` / `ConnectionResetError` on
GETs. No 5xx responses and no failed money posts. The cause is the test
setup, not the app: Locust reuses a kept-alive connection right as gunicorn
closes it (5 s keep-alive vs 1–5 s think time). In production, nginx sits in
front and opens its own upstream connections, so students never see this.

### Finding 1 — postings serialised across the whole session (fixed)

Every posting took `FOR NO KEY UPDATE` on the **Session** row, and that lock
conflicts with itself. So all deposits in all banks of a class waited for one
another. Every gunicorn thread ended up blocked on locks, and even read-only
pages took about 5 s (run 2).

The fix:

- **Session lock:** postings take `FOR SHARE` on the session (`apps/lab/locking.py`).
  Archive and exam start/submit still take a stronger lock and wait for
  postings in progress.
- **Approval check:** `needs_approval` (the limits check) runs before the bank lock.
- **Read-back:** the transaction detail read-back (an 8-table join, ~90 ms)
  runs after COMMIT instead of while holding the bank lock.

The lock window is about 40 % shorter, and banks no longer block each other.
Run 3 shows the result.

### Finding 2 — one bank is still serial (by design)

Inside one bank, every posting updates the same GL balance rows (teller cash
and the deposits GL) and the entry number, so postings in one bank stay
serialised. With about 40 ms of lock hold time, that caps out at roughly
15–25 postings per second per bank.

This matters most for **exam sessions**, where 100–200 students share one
bank. At realistic exam pace (one posting per student every ~30 s, which is
about 7 postings per second) this is within the limit. In a practice session
with groups it is not a concern.

### Finding 3 — login burst is CPU-bound

Each password check costs about 1 s of CPU (PBKDF2, 1,000,000 iterations;
Django's default). When 200 students log in within 40 s, logins queue up
(p50 ≈ 6 s, max 20 s) and slow the other pages during that minute. After the
burst, everything returns to normal.

We keep the Django default rather than lowering hash strength. Instead:

- Run gunicorn with workers ≈ vCPU count (`GUNICORN_WORKERS`).
- Let the class log in over a minute or two.
- The per-IP throttle now counts only failed logins, so a whole class behind
  one NAT IP is never locked out by its own successful logins.

### Finding 4 — busy-day pages grow with the day's volume

Run 4 started with 2,600 same-day transactions per bank already in place
(far more than a real class day, which is about 200 students × ~15 = 3,000
per session). It was about 2× slower than run 3. The dashboard and
transaction-list endpoints scan the whole business day.

This is fine at classroom volume. It is a follow-up candidate if sessions
ever run many days without EOD: add an index or a page cap.

## VPS sizing

To serve one class of 200 students:

- **CPU:** 4 vCPU or more.
- **Gunicorn:** `GUNICORN_WORKERS=4`, `GUNICORN_THREADS=4`.
- **Memory:** about 1 GB for BankLab (backend ~4 × 120 MB, Next.js ~150 MB,
  Postgres ~300 MB).

Before the first real class, re-run this test against a throwaway stack on
the VPS itself, with the owner's OK, to confirm the numbers there.
