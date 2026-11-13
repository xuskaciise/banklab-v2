"""Locust scenario for a class of 100-200 students (and one instructor).

Prepare the data with `manage.py seed_loadtest` (see README.md next to this file); it writes
`students.csv` (no passwords). The shared password is read from env LOADTEST_PASSWORD.

    LOADTEST_PASSWORD=... locust -f loadtest/locustfile.py --host http://localhost:8000 \
        -u 200 -r 10 -t 5m --headless

Each simulated student logs in once (csrf -> student-login), then repeats weighted tasks with
1-5 s think time through the real API. Tellers deposit/withdraw small USD amounts; other roles
browse. The instructor polls the dashboard and exam results.
"""

import csv
import itertools
import os
import random
import threading
from datetime import date
from pathlib import Path

from locust import HttpUser, between, events, task

CSV_PATH = Path(os.environ.get("LOADTEST_CSV", Path(__file__).with_name("students.csv")))
PASSWORD = os.environ.get("LOADTEST_PASSWORD", "")

_lock = threading.Lock()
_students: list[dict] = []
_staff: list[dict] = []
_cursor = itertools.count()


def _load() -> None:
    with CSV_PATH.open(newline="") as fh:
        for row in csv.DictReader(fh):
            (_staff if row["kind"] == "staff" else _students).append(row)


@events.test_start.add_listener
def _on_start(environment, **_):
    if not PASSWORD:
        raise SystemExit("Set LOADTEST_PASSWORD")
    if not _students:
        _load()


def _next_student() -> dict:
    with _lock:
        return _students[next(_cursor) % len(_students)]


class BankLabUser(HttpUser):
    abstract = True
    wait_time = between(1, 5)

    login_path = ""
    id_field = ""

    def on_start(self):
        self.ok = False
        self.csrf()
        r = self.client.post(
            self.login_path,
            json={self.id_field: self.identity["student_id"], "password": PASSWORD},
            headers=self.headers(),
            name="login",
        )
        if r.status_code == 200:
            self.ok = True
            self.csrf()  # login rotates the CSRF token

    def csrf(self):
        self.client.get("/api/auth/csrf", name="csrf")
        self._allow_cookies_over_http()
        self.token = self.client.cookies.get("csrftoken", "")

    def _allow_cookies_over_http(self):
        # With DJANGO_DEBUG=false the server marks cookies Secure; a local
        # plain-HTTP load test would then never send them back.
        if self.host.startswith("http://"):
            for cookie in self.client.cookies:
                cookie.secure = False

    def headers(self):
        return {"X-CSRFToken": self.token}

    def logged_in(self) -> bool:
        return self.ok


class StudentUser(BankLabUser):
    weight = 20
    login_path = "/api/auth/student-login"
    id_field = "student_id"

    def on_start(self):
        self.identity = _next_student()
        self.role = self.identity["role"]
        super().on_start()
        self.session_id = None
        self.account_ids: list[str] = []
        if self.ok:
            self.discover()

    def discover(self):
        r = self.client.get("/api/auth/me", name="auth/me")
        if r.status_code != 200:
            return
        r = self.client.get("/api/my/sessions", name="my/sessions")
        if r.status_code == 200 and r.json():
            self.session_id = r.json()[0]["session_id"]
        if self.session_id and self.role in ("teller", "cso", "manager"):
            self.refresh_accounts()

    def refresh_accounts(self):
        r = self.client.get(f"/api/s/{self.session_id}/accounts", name="accounts/list")
        if r.status_code == 200:
            body = r.json()
            items = body["items"] if isinstance(body, dict) else body
            self.account_ids = [a["id"] for a in items]

    def s(self, path: str) -> str:
        return f"/api/s/{self.session_id}{path}"

    # ------------------------------------------------------------------ browse
    @task(5)
    def dashboard(self):
        if self.session_id:
            self.client.get(self.s("/dashboard"), name="s/dashboard")

    @task(2)
    def me(self):
        if self.session_id:
            self.client.get(self.s("/me"), name="s/me")

    @task(4)
    def customers(self):
        if self.session_id and self.role in ("teller", "cso", "manager"):
            self.client.get(self.s("/customers?q=LOADTEST"), name="customers/search")

    @task(3)
    def account_lookup(self):
        if self.account_ids:
            acc = random.choice(self.account_ids)
            self.client.get(self.s(f"/accounts/{acc}"), name="accounts/get")

    @task(2)
    def statement(self):
        if self.account_ids:
            today = date.today().isoformat()
            self.client.get(
                self.s("/reports/account-statement"),
                params={
                    "account_id": random.choice(self.account_ids),
                    "date_from": today,
                    "date_to": today,
                },
                name="reports/account-statement",
            )

    @task(2)
    def transactions_list(self):
        if self.session_id and self.role in ("teller", "manager"):
            self.client.get(self.s("/transactions"), name="transactions/list")

    # ------------------------------------------------------------------ money
    def cash(self, kind: str):
        if not (self.account_ids and self.role == "teller"):
            return
        payload = {
            "account_id": random.choice(self.account_ids),
            "amount": f"{random.randint(1, 20)}.00",
            "currency": "USD",
            "party_name": "Load Tester",
            "party_id_no": "LT-1",
            "party_phone": "+252611000111",
            "narration": "loadtest",
        }
        with self.client.post(
            self.s(f"/transactions/{kind}"),
            json=payload,
            headers=self.headers(),
            name=f"transactions/{kind}",
            catch_response=True,
        ) as r:
            # Business rejections (limits, insufficient balance, pending approval) are expected
            # under random amounts; only 5xx and auth failures are real errors.
            if r.status_code >= 500 or r.status_code in (401, 403):
                r.failure(f"{r.status_code}: {r.text[:120]}")
            else:
                r.success()

    @task(6)
    def deposit(self):
        self.cash("deposit")

    @task(3)
    def withdrawal(self):
        self.cash("withdrawal")


class InstructorUser(BankLabUser):
    weight = 1
    login_path = "/api/auth/staff-login"
    id_field = "username"

    def on_start(self):
        self.identity = _staff[0]
        self.csrf()
        r = self.client.post(
            self.login_path,
            json={"username": self.identity["student_id"], "password": PASSWORD},
            headers=self.headers(),
            name="login",
        )
        self.ok = r.status_code == 200
        self.csrf()
        self.session_ids: list[str] = []
        if self.ok:
            r = self.client.get("/api/classes", name="instructor/classes")
            if r.status_code == 200 and r.json():
                r = self.client.get(
                    f"/api/classes/{r.json()[0]['id']}/sessions", name="instructor/sessions"
                )
                if r.status_code == 200:
                    self.session_ids = [x["id"] for x in r.json()]

    @task(5)
    def dashboard(self):
        self.client.get("/api/dashboard", name="instructor/dashboard")

    @task(2)
    def banks(self):
        if self.session_ids:
            sid = self.session_ids[0]
            self.client.get(f"/api/sessions/{sid}/banks", name="instructor/banks")

    @task(2)
    def exam_results(self):
        if self.session_ids:
            sid = self.session_ids[0]
            with self.client.get(
                f"/api/sessions/{sid}/exam/results",
                name="instructor/exam-results",
                catch_response=True,
            ) as r:
                # A practice session has no exam: 4xx is fine, 5xx is not.
                if r.status_code >= 500:
                    r.failure(r.text[:120])
                else:
                    r.success()
