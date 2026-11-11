# ruff: noqa: F811
"""1.13 Dashboards (student, instructor) and the Dr/Cr learning panel."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.banking import services as banking
from apps.banking import tellers, transactions
from apps.banking.models import Branch, CashTransfer, Till, Transaction
from apps.lab import services as lab
from apps.rbac import services as rbac
from tests.test_customers import Env, _media, complete_kyc, individual, make  # noqa: F401
from tests.test_lab import _reset_rbac, active_session, api, j, world  # noqa: F401
from tests.test_transactions import dep, mk_account, wd

D = Decimal


@pytest.fixture
def env(world):
    return Env(world)


def get(user, url):
    return api(user).get(url)


def cur(rows, currency, key="amount"):
    return next(r[key] for r in rows if r["currency"] == currency)


def open_till_both(env, key="teller", usd="50000", sos="2000000", code="T1"):
    till = Till.objects.create(bank=env.bank, branch=Branch.objects.get(bank=env.bank), code=code)
    floats = [{"currency": "USD", "amount": D(usd)}, {"currency": "SOS", "amount": D(sos)}]
    ts = tellers.request_open(env.member(key), till.pk, floats)
    for t in CashTransfer.objects.filter(bank=env.bank, to_id=ts.pk):
        banking.approve_custodian(env.member("vault"), t.pk)
        banking.approve_manager(env.member("manager"), t.pk)
    return tellers.approve_open(env.member("manager"), ts.pk)


@pytest.fixture
def ready(env):
    ts = open_till_both(env)
    usd = mk_account(env)
    sos = mk_account(env, code="SAV-SOS")
    return env, ts, usd, sos


def dash(env, key):
    r = get(env.user(key), f"/api/s/{env.session.pk}/dashboard")
    assert r.status_code == 200, r.content
    return r.json()


# ---------------------------------------------------------------------------- student dashboard


@pytest.mark.django_db
class TestStudentDashboard:
    def test_teller_section_totals_per_currency(self, ready):
        env, ts, usd, sos = ready
        dep(env, usd, "1000")
        dep(env, usd, "500")
        dep(env, sos, "30000")
        wd(env, usd, "200")
        d = dash(env, "teller")
        assert d["role"] == "teller" and d["business_date"]
        assert d["manager"] is None
        t = d["teller"]
        assert t["till_status"] == "open" and t["teller_session"]["till_code"] == "T1"
        assert D(cur(t["till_cash"], "USD")) == D("51300.00")
        assert D(cur(t["till_cash"], "SOS")) == D("2030000.00")
        assert t["today"]["count"] == 4 and t["today"]["pending_count"] == 0
        assert D(cur(t["today"]["total_in"], "USD")) == D("1500.00")
        assert D(cur(t["today"]["total_in"], "SOS")) == D("30000.00")
        assert D(cur(t["today"]["total_out"], "USD")) == D("200.00")
        assert D(cur(t["today"]["total_out"], "SOS")) == D("0")
        assert t["pending_approvals"] == 0

    def test_teller_only_counts_own_work_and_pending(self, ready):
        env, ts, usd, _ = ready
        dep(env, usd, "10000")
        over = wd(env, usd, "6000")  # above the teller limit -> approval
        assert over.status == "pending_approval"
        t = dash(env, "teller")["teller"]
        assert t["pending_approvals"] == 1 and t["today"]["pending_count"] == 1
        assert t["today"]["count"] == 1
        assert D(cur(t["today"]["total_out"], "USD")) == D("0")
        # another teller in the same bank has no till and sees none of this work
        t2 = dash(env, "teller2")["teller"]
        assert t2["till_status"] == "none" and t2["teller_session"] is None
        assert t2["today"]["count"] == 0 and t2["pending_approvals"] == 0
        assert D(cur(t2["till_cash"], "USD")) == D("0")

    def test_manager_section(self, ready):
        env, ts, usd, sos = ready
        dep(env, usd, "10000")
        wd(env, usd, "6000")  # pending limit approval
        d = dash(env, "manager")
        assert d["teller"] is None
        m = d["manager"]
        assert m["business_day"]["status"] == "open"
        assert m["open_tills"] == 1 and m["closing_tills"] == 0
        # vault + tills must equal the whole branch cash; opening floats moved vault -> till
        usd_cash = next(c for c in m["cash"] if c["currency"] == "USD")
        sos_cash = next(c for c in m["cash"] if c["currency"] == "SOS")
        assert D(usd_cash["tills"]) == D("60000.00")
        assert D(usd_cash["vault"]) + D(usd_cash["tills"]) == D(usd_cash["total"])
        assert D(sos_cash["tills"]) == D("2000000.00")
        by_type = {p["type"]: p["count"] for p in m["pending_approvals"]}
        assert by_type["transaction_limit"] == 1
        assert by_type["till_open"] == 0 and by_type["till_close"] == 0
        assert by_type["cash_transfer"] == 0

    def test_manager_sees_pending_till_open(self, env):
        till = Till.objects.create(
            bank=env.bank, branch=Branch.objects.get(bank=env.bank), code="T9"
        )
        tellers.request_open(env.member("teller"), till.pk, [])
        m = dash(env, "manager")["manager"]
        assert {p["type"]: p["count"] for p in m["pending_approvals"]}["till_open"] == 1
        assert dash(env, "teller")["teller"]["till_status"] == "pending_open"

    def test_sections_follow_permissions(self, ready):
        env, *_ = ready
        # CSO: neither teller nor manager data
        d = dash(env, "cso")
        assert d["teller"] is None and d["manager"] is None
        # vault custodian: vault cash but no approval-decision counts
        m = dash(env, "vault")["manager"]
        assert m["cash"] is not None and m["open_tills"] is None
        assert "transaction_limit" not in {p["type"] for p in m["pending_approvals"]}
        # accountant: cash only
        assert dash(env, "accountant")["manager"]["cash"] is not None

    def test_override_removes_section(self, ready):
        env, *_ = ready
        lab.set_permission_override(env.world["ia"], env.session.pk, "manager", "vault.view", False)
        m = dash(env, "manager")["manager"]
        assert m["cash"] is None and m["open_tills"] == 1

    def test_non_member_and_unplaced_denied(self, ready, world):
        env, *_ = ready
        url = f"/api/s/{env.session.pk}/dashboard"
        assert get(world["other"], url).status_code == 403
        assert get(world["ia"], url).status_code == 403  # instructors use /api/dashboard
        assert get(env.user("teller"), url).status_code == 200

    def test_cross_bank_isolation(self, world):
        env_a = Env(world, "a", structure="per_group")
        # same session, second group bank: its manager must not see bank A's money
        banks = list(type(env_a.bank).objects.filter(session=env_a.session).order_by("group_no"))
        assert len(banks) == 3
        ts = open_till_both(env_a)
        usd = mk_account(env_a)
        dep(env_a, usd, "700")
        from tests.test_cash import add_person

        user_b, member_b = add_person(world, env_a.session, banks[1], "mgrb1", "manager")
        m = get(user_b, f"/api/s/{env_a.session.pk}/dashboard").json()["manager"]
        assert m["open_tills"] == 0
        assert D(next(c for c in m["cash"] if c["currency"] == "USD")["tills"]) == D("0")
        assert ts.bank_id == env_a.bank.pk != banks[1].pk

    def test_cross_session_isolation(self, ready, world):
        env, ts, usd, _ = ready
        dep(env, usd, "900")
        other = Env(world, "x")  # a second session, own bank and people
        t = dash(other, "teller")["teller"]
        assert t["today"]["count"] == 0 and t["till_status"] == "none"
        m = dash(other, "manager")["manager"]
        assert m["open_tills"] == 0
        # a member of the other session cannot read this session's dashboard
        r = get(other.user("manager"), f"/api/s/{env.session.pk}/dashboard")
        assert r.status_code == 403

    def test_archived_session_readable(self, ready, world):
        env, *_ = ready
        lab.archive_session(world["ia"], env.session.pk)
        assert get(env.user("manager"), f"/api/s/{env.session.pk}/dashboard").status_code == 200


# ---------------------------------------------------------------------------- instructor dashboard


@pytest.mark.django_db
class TestStaffDashboard:
    def test_counts_and_sessions(self, ready, world):
        env, ts, usd, _ = ready
        dep(env, usd, "1000")
        r = get(world["ia"], "/api/dashboard")
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["counts"]["classes"] == 1
        assert body["counts"]["active_sessions"] == 1
        assert body["counts"]["students"] == 10
        (s,) = body["sessions"]
        assert s["id"] == str(env.session.pk) and s["class_name"] == "Banking A"
        assert s["kind"] == "practice" and s["learning_panel"] is True
        assert s["banks_count"] == 1 and s["members_count"] == 10
        assert s["today_transactions"] == 1 and s["pending_approvals"] == 0

    def test_pending_approvals_counted(self, ready, world):
        env, ts, usd, _ = ready
        dep(env, usd, "10000")
        wd(env, usd, "6000")
        (s,) = get(world["ia"], "/api/dashboard").json()["sessions"]
        assert s["pending_approvals"] == 1 and s["today_transactions"] == 2

    def test_recent_activity_capped_and_ordered(self, ready, world):
        env, ts, usd, _ = ready
        for _i in range(25):
            dep(env, usd, "1")
        ev = get(world["ia"], "/api/dashboard").json()["recent_activity"]
        assert len(ev) == 20
        assert [e["at"] for e in ev] == sorted((e["at"] for e in ev), reverse=True)
        e = ev[0]
        assert e["session_name"] == env.session.name and e["bank_name"] == env.bank.name
        assert e["action"] and e["actor_name"]

    def test_instructor_sees_only_own_classes(self, ready, world):
        env, *_ = ready
        body = get(world["ib"], "/api/dashboard").json()
        assert body["counts"] == {"classes": 1, "active_sessions": 0, "students": 1}
        assert body["sessions"] == [] and body["recent_activity"] == []

    def test_admin_sees_institution(self, ready, world):
        env, *_ = ready
        body = get(world["admin"], "/api/dashboard").json()
        assert body["counts"]["classes"] == 2 and body["counts"]["active_sessions"] == 1

    def test_students_denied(self, world):
        assert get(world["studs"][0], "/api/dashboard").status_code == 403

    def test_draft_and_archived_not_listed(self, world):
        lab.create_session(world["ia"], world["ca"].pk, "Draft")
        s = active_session(world, "Arch")
        lab.archive_session(world["ia"], s.pk)
        body = get(world["ia"], "/api/dashboard").json()
        assert body["counts"]["active_sessions"] == 0 and body["sessions"] == []


# ---------------------------------------------------------------------------- learning panel toggle


@pytest.mark.django_db
class TestLearningPanelToggle:
    def url(self, s):
        return f"/api/sessions/{s.pk}/learning-panel"

    def test_toggle_and_audit(self, world):
        s = active_session(world, "LP")
        r = j(api(world["ia"]), "post", self.url(s), {"enabled": False})
        assert r.status_code == 200 and r.json()["learning_panel"] is False
        row = AuditLog.objects.get(action="lab.session_learning_panel", entity_id=str(s.pk))
        assert row.before == {"learning_panel": True} and row.after == {"learning_panel": False}
        assert row.session_id == s.pk and row.actor_id == world["ia"].pk
        r = j(api(world["ia"]), "post", self.url(s), {"enabled": True})
        assert r.json()["learning_panel"] is True
        assert AuditLog.objects.filter(action="lab.session_learning_panel").count() == 2

    def test_admin_allowed(self, world):
        s = active_session(world, "LP")
        r = j(api(world["admin"]), "post", self.url(s), {"enabled": False})
        assert r.status_code == 200

    def test_other_instructor_and_student_denied(self, world):
        s = active_session(world, "LP")
        assert j(api(world["ib"]), "post", self.url(s), {"enabled": False}).status_code == 404
        assert j(api(world["studs"][0]), "post", self.url(s), {"enabled": False}).status_code == 403
        s.refresh_from_db()
        assert s.learning_panel is True

    def test_exam_cannot_enable(self, world):
        s = active_session(world, "Exam", kind="exam")
        assert s.learning_panel is False
        r = j(api(world["ia"]), "post", self.url(s), {"enabled": True})
        assert r.status_code == 400
        s.refresh_from_db()
        assert s.learning_panel is False

    def test_archived_rejected(self, world):
        s = active_session(world, "LP")
        lab.archive_session(world["ia"], s.pk)
        r = j(api(world["ia"]), "post", self.url(s), {"enabled": False})
        assert r.status_code == 409
        s.refresh_from_db()
        assert s.learning_panel is True


# ---------------------------------------------------------------------------- learning endpoint


@pytest.mark.django_db
class TestLearningEndpoint:
    def url(self, env, txn):
        return f"/api/s/{env.session.pk}/transactions/{txn.pk}/learning"

    def test_deposit_lines_balanced(self, ready):
        env, ts, usd, _ = ready
        txn = dep(env, usd, "250")
        r = get(env.user("teller"), self.url(env, txn))
        assert r.status_code == 200, r.content
        b = r.json()
        assert b["type"] == "cash_deposit" and b["ref_no"] == txn.ref_no
        assert b["journal_entry_no"] == txn.journal_entry.entry_no
        assert len(b["lines"]) == 2
        assert D(b["total_debit"]) == D(b["total_credit"]) == D("250.00")
        debit = next(ln for ln in b["lines"] if D(ln["debit"]) > 0)
        credit = next(ln for ln in b["lines"] if D(ln["credit"]) > 0)
        assert debit["gl_code"] and debit["gl_name"] and debit["currency"] == "USD"
        assert credit["gl_code"] != debit["gl_code"]
        assert "till" in b["explanation"] and b["note"] is None

    def test_other_types_have_explanations(self, ready):
        env, ts, usd, sos = ready
        dep(env, usd, "1000")
        w = wd(env, usd, "100")
        other_usd = mk_account(env)
        t = transactions.transfer(
            env.member("teller"),
            from_account_id=usd.pk,
            to_account_id=other_usd.pk,
            amount=D("50"),
            currency="USD",
        )
        transactions.reverse(env.member("teller"), w.pk, "oops")
        rv = Transaction.objects.get(reversal_of=w)
        for txn, kind in ((w, "cash_withdrawal"), (t, "transfer"), (rv, "reversal")):
            b = get(env.user("teller"), self.url(env, txn)).json()
            assert b["type"] == kind and b["explanation"]
            assert D(b["total_debit"]) == D(b["total_credit"]) > 0

    def test_pending_txn_has_no_lines(self, ready):
        env, ts, usd, _ = ready
        dep(env, usd, "10000")
        p = wd(env, usd, "6000")
        b = get(env.user("teller"), self.url(env, p)).json()
        assert b["status"] == "pending_approval" and b["lines"] == []
        assert b["journal_entry_no"] is None and b["note"]

    def test_403_when_panel_off(self, ready, world):
        env, ts, usd, _ = ready
        txn = dep(env, usd, "10")
        lab.set_learning_panel(world["ia"], env.session.pk, False)
        assert get(env.user("teller"), self.url(env, txn)).status_code == 403

    def test_403_in_exam(self, world):
        env = Env(world, "e", kind="exam")
        open_till_both(env)
        usd = mk_account(env)
        txn = dep(env, usd, "10")
        assert get(env.user("teller"), self.url(env, txn)).status_code == 403

    def test_does_not_need_gl_view(self, ready):
        env, ts, usd, _ = ready
        txn = dep(env, usd, "10")
        assert not rbac.role_has_permission("teller", "gl.view", session=env.session)
        assert get(env.user("teller"), self.url(env, txn)).status_code == 200

    def test_own_work_visibility(self, ready):
        env, ts, usd, _ = ready
        txn = dep(env, usd, "10")
        # another teller (own-work scope) cannot see it
        assert get(env.user("teller2"), self.url(env, txn)).status_code == 404
        # manager sees the whole bank
        assert get(env.user("manager"), self.url(env, txn)).status_code == 200
        # a role without report.operational is refused outright
        assert get(env.user("vault"), self.url(env, txn)).status_code == 403

    def test_cross_bank_and_session_isolation(self, ready, world):
        env, ts, usd, _ = ready
        txn = dep(env, usd, "10")
        other = Env(world, "y")
        assert get(other.user("manager"), self.url(other, txn)).status_code == 404
        assert get(other.user("manager"), self.url(env, txn)).status_code == 403
        assert get(world["ia"], self.url(env, txn)).status_code == 403
