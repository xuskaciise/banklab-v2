# ruff: noqa: F811
"""1.14 Exam sessions: set-up rules, timer guard, per-student seed data, auto-checks,
submit/auto-submit, grading, results visibility and export, isolation."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.banking.models import (
    Branch,
    CashCount,
    TellerSession,
    TellerSessionStatus,
    Till,
)
from apps.customers import services as cs
from apps.exams import checks, seed
from apps.exams import services as es
from apps.exams.models import Exam, ExamAttempt, ExamTaskResult
from apps.lab import services as lab
from apps.lab.models import Session, SessionMember
from apps.ledger import services as ledger
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.services import LedgerError
from apps.products import services as ps
from apps.products.models import Account
from tests.test_customers import Env, _jsonable, _media, individual  # noqa: F401
from tests.test_lab import _reset_rbac, api, j, world  # noqa: F401
from tests.test_transactions import PARTY, dep  # noqa: F401
from tests.test_transactions import open_till as _open_till

D = Decimal


def open_till(env, **kw):
    """Set-up work before the exam exists: the session is briefly a practice session."""
    Session.objects.filter(pk=env.session.pk).update(kind="practice")
    try:
        return _open_till(env, **kw)
    finally:
        Session.objects.filter(pk=env.session.pk).update(kind="exam")


SEED = [{"product_code": "SAV-USD", "amount": "500.00"}]


def iso(dt):
    return dt.isoformat()


def exam_payload(start=-60, end=60, duration=30, seed_cfg=None):
    now = timezone.now()
    return {
        "starts_at": iso(now + timedelta(minutes=start)),
        "ends_at": iso(now + timedelta(minutes=end)),
        "duration_minutes": duration,
        "instructions": "Do the tasks.",
        "seed": SEED if seed_cfg is None else seed_cfg,
    }


def mk_exam(env, *, tasks=(), publish=True, **kw):
    ia = env.world["ia"]
    body = exam_payload(**kw)
    r = j(api(ia), "put", f"/api/sessions/{env.session.pk}/exam", body)
    assert r.status_code == 200, r.content
    for t in tasks:
        r = j(api(ia), "post", f"/api/sessions/{env.session.pk}/exam/tasks", t)
        assert r.status_code == 200, r.content
    if publish:
        r = j(api(ia), "post", f"/api/sessions/{env.session.pk}/exam/publish")
        assert r.status_code == 200, r.content
    return Exam.objects.get(session=env.session)


def task(title, check_type, params, points="10"):
    return {"title": title, "check_type": check_type, "check_params": params, "points": points}


BAL = task("Deposit 100 to your account", "account_balance_equals",
           {"account": "seed", "delta": "100"}, "10")  # fmt: skip
TXN = task("Post a deposit of 100", "txn_exists",
           {"type": "cash_deposit", "amount": "100", "currency": "USD"}, "5")  # fmt: skip
CUST = task("Create a customer", "customer_created", {}, "5")


@pytest.fixture
def env(world):
    return Env(world, "x", kind="exam")


def url(env, path=""):
    return f"/api/sessions/{env.session.pk}/exam{path}"


def surl(env, path=""):
    return f"/api/s/{env.session.pk}/exam{path}"


def start(env, key):
    return es.start_exam(env.member(key))


def seed_account(env, key):
    return Account.objects.get(seed_owner=env.member(key), is_seed=True)


def lines_balanced(bank):
    assert ledger.balances_match_lines(bank)
    for entry in JournalEntry.objects.filter(bank=bank):
        agg = entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        assert agg["d"] == agg["c"]


# ----------------------------------------------------------------------------- set-up rules


@pytest.mark.django_db
class TestSetup:
    def test_practice_session_rejects_exam(self, world):
        practice = Env(world, "p")
        r = j(api(world["ia"]), "put", url(practice), exam_payload())
        assert r.status_code == 400
        assert Exam.objects.count() == 0

    def test_save_get_and_audit(self, env, world):
        assert api(world["ia"]).get(url(env)).json() is None
        exam = mk_exam(env, publish=False)
        body = api(world["ia"]).get(url(env)).json()
        assert body["status"] == "draft" and body["seed"][0]["product_code"] == "SAV-USD"
        assert AuditLog.objects.filter(action="exam.saved", entity_id=str(exam.pk)).exists()

    def test_bad_window_and_naive_time(self, env, world):
        body = exam_payload()
        body["ends_at"] = body["starts_at"]
        assert j(api(world["ia"]), "put", url(env), body).status_code == 400
        body = exam_payload()
        body["starts_at"] = body["starts_at"][:19]  # no zone
        assert j(api(world["ia"]), "put", url(env), body).status_code == 400
        body = exam_payload(duration=0)
        assert j(api(world["ia"]), "put", url(env), body).status_code == 400

    def test_bad_seed_and_check_params(self, env, world):
        bad = exam_payload(seed_cfg=[{"product_code": "NOPE", "amount": "5"}])
        assert j(api(world["ia"]), "put", url(env), bad).status_code == 400
        mk_exam(env, publish=False)
        for ct, params in (
            ("nope", {}),
            ("account_balance_equals", {"account": "seed"}),
            ("account_balance_equals", {"account": "opened", "delta": "5"}),
            ("txn_exists", {"type": "reversal", "amount": "5", "currency": "USD"}),
            ("txn_exists", {"type": "cash_deposit", "amount": "-1", "currency": "USD"}),
            ("customer_created", {"type": "alien"}),
        ):
            r = j(api(world["ia"]), "post", url(env, "/tasks"), task("x", ct, params))
            assert r.status_code == 400, (ct, params)

    def test_publish_needs_task_and_locks_edits(self, env, world):
        ia = api(world["ia"])
        mk_exam(env, publish=False)
        assert j(ia, "post", url(env, "/publish")).status_code == 400
        t = j(ia, "post", url(env, "/tasks"), BAL).json()["tasks"][0]
        assert j(ia, "post", url(env, "/publish")).status_code == 200
        assert j(ia, "post", url(env, "/publish")).status_code == 409
        assert j(ia, "put", url(env), exam_payload()).status_code == 409
        assert j(ia, "post", url(env, "/tasks"), TXN).status_code == 409
        assert j(ia, "put", url(env, f"/tasks/{t['id']}"), {"title": "n"}).status_code == 409
        assert ia.delete(url(env, f"/tasks/{t['id']}")).status_code == 409

    def test_task_update_delete_reorder(self, env, world):
        ia = api(world["ia"])
        mk_exam(env, tasks=[BAL, TXN, CUST], publish=False)
        tasks = ia.get(url(env)).json()["tasks"]
        assert [t["position"] for t in tasks] == [1, 2, 3]
        ids = [t["id"] for t in tasks]
        r = j(ia, "post", url(env, "/tasks/reorder"), {"task_ids": [ids[2], ids[0], ids[1]]})
        assert [t["id"] for t in r.json()["tasks"]] == [ids[2], ids[0], ids[1]]
        assert j(ia, "post", url(env, "/tasks/reorder"), {"task_ids": ids[:2]}).status_code == 400
        r = j(ia, "put", url(env, f"/tasks/{ids[0]}"), {"points": "7.50"})
        assert r.status_code == 200
        assert {t["id"]: t["points"] for t in r.json()["tasks"]}[ids[0]] == "7.50"
        r = ia.delete(url(env, f"/tasks/{ids[1]}"))
        assert len(r.json()["tasks"]) == 2 and r.json()["total_points"] == "12.50"
        for action in ("exam.task_added", "exam.task_updated", "exam.task_removed"):
            assert AuditLog.objects.filter(action=action).exists()

    def test_permissions(self, env, world):
        mk_exam(env, tasks=[BAL])
        stud = api(world["studs"][0])
        assert stud.get(url(env)).status_code == 403
        assert j(stud, "put", url(env), exam_payload()).status_code == 403
        assert stud.get(url(env, "/results")).status_code == 403
        ib = api(world["ib"])  # instructor of another class
        assert ib.get(url(env)).status_code == 404
        assert j(ib, "put", url(env), exam_payload()).status_code == 404
        assert ib.get(url(env, "/results")).status_code == 404
        assert api(world["admin"]).get(url(env)).status_code == 200
        # instructors cannot use the student routes
        assert api(world["ia"]).get(surl(env)).status_code == 403

    def test_archived_session_read_only(self, env, world):
        mk_exam(env, tasks=[BAL], publish=False)
        lab.archive_session(world["ia"], env.session.pk)
        assert j(api(world["ia"]), "put", url(env), exam_payload()).status_code == 409
        assert api(world["ia"]).get(url(env)).status_code == 200


# ----------------------------------------------------------------------------- seed data


@pytest.mark.django_db
class TestSeed:
    def test_publish_seeds_every_placed_student(self, env):
        exam = mk_exam(env, tasks=[BAL])
        members = SessionMember.objects.filter(session=env.session, bank__isnull=False)
        assert members.count() == 10
        for m in members:
            (acc,) = Account.objects.filter(seed_owner=m)
            assert acc.is_seed and acc.ledger_balance == D("500.00") and acc.currency == "USD"
            assert acc.customer.is_seed and acc.customer.seed_owner_id == m.pk
            assert acc.bank_id == env.bank.pk
        assert AuditLog.objects.filter(action="exam.seeded").count() == 10
        assert exam.status == "published"

    def test_seed_posts_balanced_entries_via_ledger(self, env):
        before = JournalEntry.objects.filter(bank=env.bank).count()
        mk_exam(env, tasks=[BAL])
        entries = JournalEntry.objects.filter(bank=env.bank, source_type="exam_seed")
        assert (
            entries.count() == 10
            and JournalEntry.objects.filter(bank=env.bank).count() == before + 10
        )
        for e in entries:
            dr, cr = e.lines.get(debit__gt=0), e.lines.get(credit__gt=0)
            assert dr.gl_account.system_tag == "CASH_VAULT" and cr.gl_account.code == "2110"
            assert dr.debit == cr.credit == D("500.00") and cr.account_id
        lines_balanced(env.bank)

    def test_idempotent(self, env):
        exam = mk_exam(env, tasks=[BAL])
        entries = JournalEntry.objects.count()
        accounts = Account.objects.count()
        assert es.seed_all(exam) == (0, [])
        assert seed.ensure_member_seed(exam, env.member("teller")) == 0
        assert JournalEntry.objects.count() == entries and Account.objects.count() == accounts

    def test_vary_amounts_and_names_differ_per_student(self, env):
        mk_exam(
            env, tasks=[BAL], seed_cfg=[{"product_code": "SAV-USD", "amount": "500", "vary": True}]
        )
        amounts = {a.ledger_balance for a in Account.objects.filter(is_seed=True)}
        assert len(amounts) > 1 and all(D("500") <= a <= D("545") for a in amounts)
        assert len({a.customer.display_name for a in Account.objects.filter(is_seed=True)}) > 3

    def test_seed_isolation_between_students(self, env):
        mk_exam(env, tasks=[BAL])
        mine, theirs = seed_account(env, "teller"), seed_account(env, "teller2")
        assert {a.pk for a in ps.list_accounts(env.member("teller"))} == {mine.pk}
        assert {c.pk for c in cs.list_customers(env.member("teller"))} == {mine.customer_id}
        r = api(env.user("teller")).get(f"/api/s/{env.session.pk}/accounts/{theirs.pk}")
        assert r.status_code == 404
        r = api(env.user("teller")).get(f"/api/s/{env.session.pk}/customers/{theirs.customer_id}")
        assert r.status_code == 404
        # whole-bank roles are limited to their own rows in exams too
        assert {a.pk for a in ps.list_accounts(env.member("manager"))} == {
            seed_account(env, "manager").pk
        }

    def test_late_member_seeded_on_start(self, env, world):
        exam = mk_exam(env, tasks=[BAL])
        user, _ = lab.add_student(world["ia"], world["ca"].pk, "late1", "Late One", "0611110000")
        (late,) = lab.add_members(world["ia"], env.session.pk, [user.pk], bank_id=env.bank.pk)
        assert not Account.objects.filter(seed_owner=late).exists()
        es.start_exam(late)
        assert Account.objects.get(seed_owner=late).ledger_balance == D("500.00")
        lines_balanced(env.bank)
        assert exam.pk

    def test_seed_after_session_opens(self, world):
        """Publish on a draft session: no bank yet, seed is created at start."""
        s = lab.create_session(world["ia"], world["ca"].pk, "Late exam", kind="exam")
        lab.add_members(world["ia"], s.pk, all_enrolled=True)
        r = j(api(world["ia"]), "put", f"/api/sessions/{s.pk}/exam", exam_payload())
        assert r.status_code == 200
        assert (
            j(api(world["ia"]), "post", f"/api/sessions/{s.pk}/exam/tasks", BAL).status_code == 200
        )
        assert j(api(world["ia"]), "post", f"/api/sessions/{s.pk}/exam/publish").status_code == 200
        assert Account.objects.filter(is_seed=True).count() == 0
        lab.open_session(world["ia"], s.pk)
        member = SessionMember.objects.get(session=s, user=world["studs"][0])
        es.start_exam(member)
        assert Account.objects.filter(seed_owner=member).count() == 1


# ----------------------------------------------------------------------------- timer guard


def deposit_own(env, key="teller", amount="100"):
    acc = seed_account(env, key)
    return dep(env, acc, amount, key=key)


@pytest.mark.django_db
class TestTimerGuard:
    @pytest.fixture
    def ready(self, env):
        open_till(env)  # before the exam is published: set-up work is not guarded
        mk_exam(env, tasks=[BAL, TXN])
        return env

    def code(self, call):
        with pytest.raises(LedgerError) as e:
            call()
        assert e.value.status == 409
        return e.value.code

    def test_before_start_pressed(self, ready):
        assert self.code(lambda: deposit_own(ready)) == "exam_not_started"
        assert Account.objects.get(pk=seed_account(ready, "teller").pk).ledger_balance == D(
            "500.00"
        )

    def test_before_window_opens(self, env):
        open_till(env)
        mk_exam(env, tasks=[BAL], start=30, end=120)
        assert self.code(lambda: deposit_own(env)) == "exam_not_open"
        with pytest.raises(es.Conflict):
            start(env, "teller")

    def test_unpublished_exam_blocks_students(self, env):
        mk_exam(env, tasks=[BAL], publish=False)
        assert (
            self.code(lambda: cs.create_customer(env.member("cso"), **individual()))
            == "exam_not_open"
        )

    def test_after_start_ok_and_after_deadline_blocked(self, ready):
        start(ready, "teller")
        txn = deposit_own(ready)
        assert txn.amount == D("100.00")
        ExamAttempt.objects.filter(session_member=ready.member("teller")).update(
            deadline_at=timezone.now() - timedelta(seconds=1)
        )
        assert self.code(lambda: deposit_own(ready)) == "exam_time_over"
        assert seed_account(ready, "teller").ledger_balance == D("600.00")

    def test_after_submit_blocked(self, ready):
        start(ready, "teller")
        es.submit_exam(ready.member("teller"))
        assert self.code(lambda: deposit_own(ready)) == "exam_submitted"

    def test_other_students_unaffected_and_api_error_code(self, ready):
        start(ready, "teller")
        es.submit_exam(ready.member("teller"))
        # cso did not start: customer create rejected with a clear 409 + code
        r = j(api(ready.user("cso")), "post", ready.url(), _jsonable(individual()))
        assert r.status_code == 409 and r.json()["code"] == "exam_not_started"
        start(ready, "cso")
        c = cs.create_customer(ready.member("cso"), **individual())
        assert c.pk

    def test_personal_deadline_is_min_of_window_and_duration(self, env):
        mk_exam(env, tasks=[BAL], start=-10, end=20, duration=90)
        start(env, "teller")
        a = ExamAttempt.objects.get(session_member=env.member("teller"))
        assert a.deadline_at == Exam.objects.get(session=env.session).ends_at
        assert (a.deadline_at - a.started_at) < timedelta(minutes=21)

    def test_cannot_publish_exam_that_already_ended(self, env):
        mk_exam(env, tasks=[BAL], start=-120, end=-1, publish=False)
        r = j(api(env.world["ia"]), "post", url(env, "/publish"))
        assert r.status_code == 400

    def test_start_after_window_is_closed(self, env):
        mk_exam(env, tasks=[BAL])
        Exam.objects.filter(session=env.session).update(
            ends_at=timezone.now() - timedelta(seconds=1),
            starts_at=timezone.now() - timedelta(hours=1),
        )
        with pytest.raises(es.Conflict):
            start(env, "teller")
        assert api(env.user("teller")).get(surl(env)).json()["state"] == "missed"

    def test_instructor_not_blocked(self, ready, world):
        # instructor-side writes on the same session still work while students are locked
        lab.set_visibility_override(world["ia"], ready.session.pk, ready.member("cso").pk, "own")
        assert api(world["ia"]).get(url(ready, "/results")).status_code == 200

    def test_lock_writable_session_guard(self, ready):
        from django.db import transaction
        from django.test import RequestFactory

        from apps.rbac import context

        request = RequestFactory().post("/x")
        request.user = ready.user("teller")
        context.resolve_bank_context(request, ready.session.pk)
        with transaction.atomic(), pytest.raises(LedgerError) as e:
            context.lock_writable_session(request)
        assert e.value.code == "exam_not_started"
        start(ready, "teller")
        with transaction.atomic():
            assert context.lock_writable_session(request).pk == ready.session.pk

    def test_practice_session_not_guarded(self, world):
        practice = Env(world, "pp")
        assert cs.create_customer(practice.member("cso"), **individual()).pk


# ----------------------------------------------------------------------------- checks


@pytest.mark.django_db
class TestChecks:
    @pytest.fixture
    def ready(self, env):
        open_till(env)
        mk_exam(env, tasks=[BAL, TXN, CUST])
        return env

    def run(self, env, key, check, params):
        attempt = ExamAttempt.objects.filter(session_member=env.member(key)).first()
        since = attempt.started_at if attempt else timezone.now()
        return checks.CHECKS[check].run(
            env.member(key), checks.validate_params(check, params), since
        )

    def test_account_balance_equals(self, ready):
        env = ready
        start(env, "teller")
        start(env, "teller2")
        params = {"account": "seed", "delta": "100"}
        assert self.run(env, "teller", "account_balance_equals", params)[0] is False
        deposit_own(env)
        ok, details = self.run(env, "teller", "account_balance_equals", params)
        assert ok and details["expected"] == "600.00" and details["actual"] == "600.00"
        # the other student's untouched seed account does not pass, mine is not theirs
        assert self.run(env, "teller2", "account_balance_equals", params)[0] is False
        assert self.run(
            env, "teller", "account_balance_equals", {"account": "seed", "amount": "600"}
        )[0]
        assert not self.run(
            env,
            "teller",
            "account_balance_equals",
            {"account": "seed", "seed_index": 3, "amount": "600"},
        )[0]

    def test_account_balance_opened_account(self, ready):
        env = ready
        start(env, "cso")
        c = cs.create_customer(env.member("cso"), **individual(address="Hodan"))
        from tests.test_customers import complete_kyc

        complete_kyc(env, c, "cso")
        acct = ps.open_account(
            env.member("cso"), customer_id=c.pk, product_id=_product(env, "CUR-USD").pk
        )
        p = {"account": "opened", "amount": "0", "product_code": "CUR-USD"}
        assert self.run(env, "cso", "account_balance_equals", p)[0]
        assert not self.run(env, "cso", "account_balance_equals", {**p, "product_code": "SAV-USD"})[
            0
        ]
        assert not self.run(env, "cso", "account_balance_equals", {**p, "amount": "5"})[0]
        assert not self.run(env, "cso2", "account_balance_equals", p)[0]  # not their account
        assert acct.pk

    def test_txn_exists(self, ready):
        env = ready
        start(env, "teller")
        p = {"type": "cash_deposit", "amount": "100", "currency": "USD"}
        assert self.run(env, "teller", "txn_exists", p)[0] is False
        deposit_own(env)
        ok, d = self.run(env, "teller", "txn_exists", p)
        assert ok and d["found"] == 1
        assert not self.run(env, "teller", "txn_exists", {**p, "amount": "101"})[0]
        assert not self.run(env, "teller", "txn_exists", {**p, "currency": "SOS"})[0]
        assert not self.run(env, "teller", "txn_exists", {**p, "min_count": 2})[0]
        assert not self.run(env, "teller2", "txn_exists", p)[0]  # posted by someone else

    def test_till_closed_balanced(self, ready):
        env = ready
        ts = TellerSession.objects.get(teller_member=env.member("teller"))
        assert self.run(env, "teller", "till_closed_balanced", {}) == (
            False,
            {"reason": "till_not_closed"},
        )
        ts.status = TellerSessionStatus.CLOSED
        ts.save(update_fields=["status"])
        assert self.run(env, "teller", "till_closed_balanced", {}) == (
            False,
            {"reason": "no_closing_count"},
        )
        mk_count(ts, env, "USD", "-5")
        ok, d = self.run(env, "teller", "till_closed_balanced", {})
        assert not ok and d["over_short"] == {"USD": "-5.00"}
        mk_count(ts, env, "USD", "0", attempt=2)  # recount balanced
        assert self.run(env, "teller", "till_closed_balanced", {})[0]
        assert not self.run(env, "teller2", "till_closed_balanced", {})[0]

    def test_customer_created(self, ready):
        env = ready
        start(env, "cso")
        assert not self.run(env, "cso", "customer_created", {})[0]
        cs.create_customer(env.member("cso"), **individual())
        assert self.run(env, "cso", "customer_created", {})[0]
        assert self.run(env, "cso", "customer_created", {"type": "individual"})[0]
        assert not self.run(env, "cso", "customer_created", {"type": "company"})[0]
        assert not self.run(env, "cso", "customer_created", {"min_count": 2})[0]
        assert not self.run(env, "cso2", "customer_created", {})[0]
        # seed customers never count as "created by the student"
        assert not self.run(env, "teller", "customer_created", {})[0]


def _product(env, code):
    from apps.products.models import Product

    return Product.objects.get(bank=env.bank, code=code)


def mk_count(ts, env, currency, diff, attempt=1):
    return CashCount.objects.create(
        teller_session=ts,
        kind="close",
        currency=currency,
        attempt=attempt,
        counted_total=D("100"),
        system_total=D("100") - D(diff),
        difference=D(diff),
        counted_by=env.member("teller"),
    )


# ----------------------------------------------------------------------------- submit / scoring


@pytest.mark.django_db
class TestSubmitAndScore:
    @pytest.fixture
    def ready(self, env):
        open_till(env)
        mk_exam(env, tasks=[BAL, TXN, CUST])
        return env

    def test_student_view_hides_tasks_until_start(self, ready):
        c = api(ready.user("teller"))
        body = c.get(surl(ready)).json()
        assert (
            body["state"] == "ready" and body["tasks"] == [] and body["remaining_seconds"] is None
        )
        assert "check_type" not in str(body) and "server_time" in body
        body = j(c, "post", surl(ready, "/start")).json()
        assert body["state"] == "in_progress" and len(body["tasks"]) == 3
        assert 0 < body["remaining_seconds"] <= 30 * 60
        assert all(t["passed"] is None for t in body["tasks"])
        assert "check_params" not in str(body)

    def test_start_is_idempotent(self, ready):
        c = api(ready.user("teller"))
        a = j(c, "post", surl(ready, "/start")).json()
        b = j(c, "post", surl(ready, "/start")).json()
        assert a["started_at"] == b["started_at"]
        assert ExamAttempt.objects.filter(session_member=ready.member("teller")).count() == 1

    def test_submit_scores_and_shows_ticks(self, ready):
        c = api(ready.user("teller"))
        j(c, "post", surl(ready, "/start"))
        deposit_own(ready)
        body = j(c, "post", surl(ready, "/submit")).json()
        assert body["state"] == "submitted" and body["auto_submitted"] is False
        assert [t["passed"] for t in body["tasks"]] == [True, True, False]
        a = ExamAttempt.objects.get(session_member=ready.member("teller"))
        assert a.score == D("15.00") and a.results.count() == 3
        assert AuditLog.objects.filter(action="exam.submitted", actor=ready.user("teller")).exists()
        # second submit is rejected, results stay
        assert j(c, "post", surl(ready, "/submit")).status_code == 409
        assert a.results.count() == 3

    def test_submit_without_start(self, ready):
        assert j(api(ready.user("teller")), "post", surl(ready, "/submit")).status_code == 409

    def test_auto_submit_when_deadline_passed(self, ready):
        c = api(ready.user("teller"))
        j(c, "post", surl(ready, "/start"))
        deposit_own(ready)
        ExamAttempt.objects.update(deadline_at=timezone.now() - timedelta(seconds=5))
        body = c.get(surl(ready)).json()  # lazy auto-submit on read
        assert body["state"] == "submitted" and body["auto_submitted"] is True
        a = ExamAttempt.objects.get(session_member=ready.member("teller"))
        assert a.score == D("15.00") and a.auto_submitted
        assert AuditLog.objects.filter(action="exam.auto_submitted").exists()

    def test_auto_submit_job_and_instructor_read(self, ready, world):
        start(ready, "teller")
        start(ready, "teller2")
        ExamAttempt.objects.update(deadline_at=timezone.now() - timedelta(seconds=5))
        assert es.auto_submit_overdue() == 2
        assert es.auto_submit_overdue() == 0
        assert ExamAttempt.objects.filter(submitted_at__isnull=False).count() == 2

    def test_results_hidden_until_published(self, ready, world):
        ia = api(world["ia"])
        c = api(ready.user("teller"))
        assert c.get(surl(ready, "/result")).status_code == 409  # not submitted
        j(c, "post", surl(ready, "/start"))
        j(c, "post", surl(ready, "/submit"))
        assert c.get(surl(ready, "/result")).status_code == 409  # not published
        assert j(ia, "post", url(ready, "/results/publish")).status_code == 200
        res = c.get(surl(ready, "/result")).json()
        assert res["score"] == "0.00" and res["max_score"] == "20.00"

    def test_publish_results_flow(self, ready, world):
        ia = api(world["ia"])
        start(ready, "teller")
        start(ready, "teller2")
        c = api(ready.user("teller"))
        deposit_own(ready)
        j(c, "post", surl(ready, "/submit"))
        # teller2 still working -> cannot publish
        assert j(ia, "post", url(ready, "/results/publish")).status_code == 409
        j(api(ready.user("teller2")), "post", surl(ready, "/submit"))
        assert j(ia, "post", url(ready, "/results/publish")).status_code == 200
        assert j(ia, "post", url(ready, "/results/publish")).status_code == 409
        res = c.get(surl(ready, "/result")).json()
        assert res["score"] == "15.00" and res["max_score"] == "20.00"
        assert [t["passed"] for t in res["tasks"]] == [True, True, False]
        assert api(ready.user("teller2")).get(surl(ready, "/result")).json()["score"] == "0.00"
        # a student that never started has no result
        assert api(ready.user("cso")).get(surl(ready, "/result")).status_code == 409
        assert AuditLog.objects.filter(action="exam.results_published").exists()

    def test_instructor_results_and_adjust(self, ready, world):
        ia = api(world["ia"])
        start(ready, "teller")
        deposit_own(ready)
        es.submit_exam(ready.member("teller"))
        data = ia.get(url(ready, "/results")).json()
        assert data["max_score"] == "20.00" and len(data["students"]) == 10
        row = next(s for s in data["students"] if s["username"] == ready.user("teller").username)
        assert row["status"] == "submitted" and row["score"] == "15.00"
        assert {s["status"] for s in data["students"]} == {"submitted", "not_started"}
        cust = next(t for t in row["tasks"] if t["title"] == "Create a customer")
        assert cust["passed"] is False and cust["auto_points"] == "0.00"
        # adjust: give partial credit
        r = j(
            ia, "post", url(ready, f"/results/{cust['result_id']}/adjust"), {"adjusted_points": "3"}
        )
        assert r.status_code == 200
        row = next(
            s for s in r.json()["students"] if s["member_id"] == str(ready.member("teller").pk)
        )
        assert row["score"] == "18.00"
        t = next(t for t in row["tasks"] if t["result_id"] == cust["result_id"])
        assert (
            t["adjusted_points"] == "3.00" and t["points"] == "3.00" and t["auto_points"] == "0.00"
        )
        res = ExamTaskResult.objects.get(pk=cust["result_id"])
        assert res.adjusted_by_id == world["ia"].pk and res.adjusted_at
        assert AuditLog.objects.filter(action="exam.result_adjusted", actor=world["ia"]).exists()
        # over max / negative rejected
        assert (
            j(
                ia,
                "post",
                url(ready, f"/results/{cust['result_id']}/adjust"),
                {"adjusted_points": "6"},
            ).status_code
            == 400
        )
        assert (
            j(
                ia,
                "post",
                url(ready, f"/results/{cust['result_id']}/adjust"),
                {"adjusted_points": "-1"},
            ).status_code
            == 400
        )
        # zero is allowed (take points away), null clears the adjustment
        bal = next(t for t in row["tasks"] if t["title"].startswith("Deposit"))
        r = j(
            ia, "post", url(ready, f"/results/{bal['result_id']}/adjust"), {"adjusted_points": "0"}
        )
        assert (
            next(s for s in r.json()["students"] if s["member_id"] == row["member_id"])["score"]
            == "8.00"
        )
        r = j(
            ia, "post", url(ready, f"/results/{bal['result_id']}/adjust"), {"adjusted_points": None}
        )
        assert (
            next(s for s in r.json()["students"] if s["member_id"] == row["member_id"])["score"]
            == "18.00"
        )
        # the student sees the final points after publish
        assert j(ia, "post", url(ready, "/results/publish")).status_code == 200
        assert api(ready.user("teller")).get(surl(ready, "/result")).json()["score"] == "18.00"

    def test_adjust_permissions_and_isolation(self, ready, world):
        start(ready, "teller")
        es.submit_exam(ready.member("teller"))
        rid = ExamTaskResult.objects.first().pk
        body = {"adjusted_points": "1"}
        assert (
            j(
                api(ready.user("teller")), "post", url(ready, f"/results/{rid}/adjust"), body
            ).status_code
            == 403
        )
        assert (
            j(api(world["ib"]), "post", url(ready, f"/results/{rid}/adjust"), body).status_code
            == 404
        )
        # a result id from another session cannot be adjusted through this session
        other = Env(world, "o", kind="exam")
        open_till(other)
        mk_exam(other, tasks=[BAL])
        start(other, "teller")
        es.submit_exam(other.member("teller"))
        orid = ExamTaskResult.objects.filter(attempt__exam__session=other.session).first().pk
        assert (
            j(api(world["ia"]), "post", url(ready, f"/results/{orid}/adjust"), body).status_code
            == 404
        )
        assert ExamTaskResult.objects.get(pk=orid).adjusted_points is None

    def test_cross_session_isolation(self, ready, world):
        other = Env(world, "o", kind="exam")
        mk_exam(other, tasks=[BAL])
        c = api(world["other"])  # a student of another class
        # a non-member has no access to session B and session A exams
        assert c.get(surl(ready)).status_code == 403
        assert c.get(surl(other)).status_code == 403
        assert j(c, "post", surl(other, "/start")).status_code == 403
        # attempts and seed rows are per session / bank
        start(ready, "teller")
        assert not ExamAttempt.objects.filter(exam__session=other.session).exists()
        assert not Account.objects.filter(
            seed_owner=ready.member("teller"), bank=other.bank
        ).exists()
        # results of A list only A's members
        names = {
            s["username"] for s in api(world["ia"]).get(url(ready, "/results")).json()["students"]
        }
        assert ready.user("teller").username in names
        assert other.user("teller").username not in names

    def test_ledger_balanced_after_whole_flow(self, ready):
        start(ready, "teller")
        deposit_own(ready)
        es.submit_exam(ready.member("teller"))
        lines_balanced(ready.bank)
        assert JournalLine.objects.filter(entry__bank=ready.bank).exists()


# ----------------------------------------------------------------------------- export + clock


@pytest.mark.django_db
class TestExportAndClock:
    @pytest.fixture
    def ready(self, env):
        open_till(env)
        mk_exam(env, tasks=[BAL, TXN])
        start(env, "teller")
        es.submit_exam(env.member("teller"))
        return env

    def test_xlsx_and_pdf(self, ready, world):
        ia = api(world["ia"])
        r = ia.get(url(ready, "/results.xlsx"))
        assert r.status_code == 200 and r.content[:2] == b"PK"
        assert "spreadsheetml" in r["Content-Type"]
        r = ia.get(url(ready, "/results.pdf"))
        assert r.status_code == 200 and r.content[:4] == b"%PDF"

    def test_export_permissions(self, ready, world):
        for ext in ("xlsx", "pdf"):
            assert api(ready.user("teller")).get(url(ready, f"/results.{ext}")).status_code == 403
            assert api(world["ib"]).get(url(ready, f"/results.{ext}")).status_code == 404

    def test_session_me_exam_clock(self, ready):
        me = api(ready.user("teller2")).get(f"/api/s/{ready.session.pk}/me").json()
        assert me["exam"]["state"] == "ready" and me["exam"]["remaining_seconds"] is None
        start(ready, "teller2")
        me = api(ready.user("teller2")).get(f"/api/s/{ready.session.pk}/me").json()
        assert me["exam"]["state"] == "in_progress" and 0 < me["exam"]["remaining_seconds"] <= 1800
        assert me["exam"]["deadline_at"] and me["exam"]["server_time"]
        me = api(ready.user("teller")).get(f"/api/s/{ready.session.pk}/me").json()
        assert me["exam"]["state"] == "submitted"

    def test_practice_session_has_no_exam_clock(self, world):
        practice = Env(world, "pr")
        me = api(practice.user("cso")).get(f"/api/s/{practice.session.pk}/me").json()
        assert me["exam"] is None
        assert (
            api(practice.user("cso")).get(f"/api/s/{practice.session.pk}/exam").status_code == 404
        )

    def test_unused_helpers_import(self):
        assert Till and Branch


# ----------------------------------------------------------------------------- review fixes


@pytest.mark.django_db
class TestReviewFixes:
    def test_exam_session_without_exam_fails_closed(self, env):
        with pytest.raises(LedgerError) as e:
            cs.create_customer(env.member("cso"), **individual())
        assert e.value.code == "exam_not_open" and e.value.status == 409
        r = j(api(env.user("cso")), "post", env.url(), _jsonable(individual()))
        assert r.status_code == 409 and r.json()["code"] == "exam_not_open"

    def test_checks_ignore_rows_created_before_start(self, env):
        open_till(env)
        mk_exam(env, tasks=[CUST, TXN])
        start(env, "cso")
        start(env, "teller")
        cs.create_customer(env.member("cso"), **individual())
        deposit_own(env)
        p_c, p_t = {}, {"type": "cash_deposit", "amount": "100", "currency": "USD"}
        for key, check, params in (
            ("cso", "customer_created", p_c),
            ("teller", "txn_exists", p_t),
        ):
            attempt = ExamAttempt.objects.get(session_member=env.member(key))
            ok = checks.CHECKS[check].run(env.member(key), params, attempt.started_at)[0]
            assert ok
            later = timezone.now() + timedelta(minutes=5)  # rows now predate the attempt
            assert not checks.CHECKS[check].run(env.member(key), params, later)[0]

    def test_seed_failure_does_not_break_publish_and_blocks_start(self, env):
        from apps.banking.models import BusinessDay

        BusinessDay.objects.filter(bank=env.bank).update(status="closed")
        exam = mk_exam(env, tasks=[BAL], publish=False)
        r = j(api(env.world["ia"]), "post", url(env, "/publish"))
        assert r.status_code == 200 and len(r.json()["seed_failures"]) == 10
        assert AuditLog.objects.filter(action="exam.seed_failed").count() == 10
        assert Account.objects.filter(is_seed=True).count() == 0
        r = j(api(env.user("teller")), "post", surl(env, "/start"))
        assert r.status_code == 409 and r.json()["code"] == "exam_seed_failed"
        assert not ExamAttempt.objects.filter(exam=exam).exists()
        # fixed: the day reopens and the next start seeds + creates the attempt
        BusinessDay.objects.filter(bank=env.bank).update(status="open")
        assert j(api(env.user("teller")), "post", surl(env, "/start")).status_code == 200
        assert Account.objects.filter(seed_owner=env.member("teller")).count() == 1

    def test_missing_vault_gl_blocks_start(self, env):
        from apps.ledger.models import GLAccount

        exam = mk_exam(env, tasks=[BAL])
        Exam.objects.filter(pk=exam.pk).update(seed=[*SEED, *SEED])
        exam.refresh_from_db()
        GLAccount.objects.filter(bank=env.bank, system_tag="CASH_VAULT").update(system_tag="X")
        with pytest.raises(LedgerError) as e:
            seed.ensure_member_seed(exam, env.member("teller"))
        assert e.value.code == "exam_seed_failed" and e.value.status == 409

    def pending(self, env, amount="6000"):
        open_till(env)
        mk_exam(env, tasks=[BAL], seed_cfg=[{"product_code": "SAV-USD", "amount": "20000"}])
        start(env, "teller")
        start(env, "manager")
        from tests.test_transactions import wd

        t = wd(env, seed_account(env, "teller"), amount)
        assert t.status == "pending_approval"
        from apps.banking.models import Approval

        return t, Approval.objects.get(subject_id=t.pk)

    def test_approval_blocked_after_makers_deadline(self, env):
        from apps.banking import approvals

        t, ap = self.pending(env)
        ExamAttempt.objects.filter(session_member=env.member("teller")).update(
            deadline_at=timezone.now() - timedelta(seconds=1)
        )
        with pytest.raises(LedgerError) as e:
            approvals.approve(env.member("manager"), ap.pk)
        assert e.value.code == "exam_time_over"
        t.refresh_from_db()
        assert t.status == "pending_approval"
        assert seed_account(env, "teller").ledger_balance == D("20000.00")

    def test_finalize_auto_rejects_pending_approvals(self, env):
        from apps.banking.models import Approval

        t, ap = self.pending(env)
        es.submit_exam(env.member("teller"))
        t.refresh_from_db()
        ap = Approval.objects.get(pk=ap.pk)
        assert t.status == "rejected" and ap.status == "rejected" and t.journal_entry_id is None
        assert seed_account(env, "teller").ledger_balance == D("20000.00")
        assert AuditLog.objects.filter(action="exam.approval_auto_rejected").exists()
        lines_balanced(env.bank)

    def test_seed_rows_private_even_in_scope_all(self, env, world):
        mk_exam(env, tasks=[BAL])
        for key in ("manager", "vault", "accountant"):
            m = env.member(key)
            mine = seed_account(env, key)
            assert {a.pk for a in ps._visible(m, "all")} == {mine.pk}
            assert {c.pk for c in cs._visible(m, "all")} == {mine.customer_id}
        # the instructor still sees every seed row through the staff route
        base = f"/api/sessions/{env.session.pk}/banks/{env.bank.pk}/customers"
        assert api(world["ia"]).get(base).json()["count"] == 10

    def test_cannot_transfer_to_another_students_seed_account(self, env):
        from tests.test_transactions import xfer

        open_till(env)
        mk_exam(env, tasks=[BAL])
        start(env, "teller")
        theirs = seed_account(env, "teller2")
        with pytest.raises(LedgerError) as e:
            xfer(env, seed_account(env, "teller"), theirs, "10")
        assert e.value.status == 404
        theirs.refresh_from_db()
        assert theirs.ledger_balance == D("500.00")
