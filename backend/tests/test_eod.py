# ruff: noqa: F811
"""1.11 End of day by the Manager (transactions.md E2)."""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.banking import eod, tellers
from apps.banking.models import Branch, BusinessDay, CashTransfer, Till
from apps.lab import services as lab
from apps.ledger.models import JournalEntry
from apps.ledger.services import LedgerError
from apps.rbac.services import PermissionDenied
from tests.test_customers import Env
from tests.test_lab import _reset_rbac, api, j, world  # noqa: F401
from tests.test_transactions import dep, mk_account, open_till

D = Decimal
ZERO_COUNT = [{"currency": "USD", "lines": []}, {"currency": "SOS", "lines": []}]


@pytest.fixture
def env(world):
    return Env(world)


def url(env, tail=""):
    return f"/api/s/{env.session.pk}/eod{tail}"


def checks(env):
    st = eod.eod_status(env.member("manager"))
    return st, {c["code"]: c for c in st["checks"]}


def close_till(env, ts):
    tellers.submit_close_count(env.member("teller"), ts.pk, ZERO_COUNT)
    return tellers.approve_close(env.member("manager"), ts.pk)


def day(env):
    return BusinessDay.objects.get(bank=env.bank, status="open")


def blocked(env):
    with pytest.raises(LedgerError) as e:
        eod.close_day(env.member("manager"))
    assert e.value.status == 409 and e.value.code == "eod_checks_failed"
    assert day(env).status == "open"


@pytest.mark.django_db
class TestChecks:
    def test_clean_bank_can_close(self, env):
        st, c = checks(env)
        assert st["can_close"] and st["business_date"] == day(env).date
        assert list(c) == [
            "teller_sessions_closed",
            "no_pending_approvals",
            "cash_reconciliation",
            "trial_balance",
        ]
        assert all(x["ok"] for x in c.values())

    def test_open_teller_session_blocks(self, env):
        open_till(env, usd=None)
        st, c = checks(env)
        t = c["teller_sessions_closed"]
        assert not st["can_close"] and not t["ok"] and t["count"] == 1
        assert t["items"][0]["till_code"] == "T1" and t["items"][0]["status"] == "open"
        blocked(env)

    def test_cancelled_session_does_not_block(self, env):
        till = Till.objects.create(
            bank=env.bank, branch=Branch.objects.get(bank=env.bank), code="T9"
        )
        ts = tellers.request_open(env.member("teller"), till.pk, [])
        assert not checks(env)[0]["can_close"]  # pending_open blocks
        tellers.cancel_open(env.member("teller"), ts.pk)
        assert checks(env)[0]["can_close"]

    def test_pending_cash_transfer_blocks(self, env):
        close_till(env, open_till(env))
        assert checks(env)[0]["can_close"]
        till = Till.objects.create(
            bank=env.bank, branch=Branch.objects.get(bank=env.bank), code="T3"
        )
        tellers.request_open(
            env.member("teller2"), till.pk, [{"currency": "USD", "amount": D("10")}]
        )
        _, c = checks(env)
        assert not c["no_pending_approvals"]["ok"] and c["no_pending_approvals"]["count"] == 1
        assert CashTransfer.objects.filter(bank=env.bank, status="pending").count() == 1
        blocked(env)

    def test_pending_transaction_blocks(self, env):
        ts = open_till(env)
        a = mk_account(env)
        assert dep(env, a, "20000.01").status == "pending_approval"
        close_till(env, ts)
        st, c = checks(env)
        assert not c["no_pending_approvals"]["ok"] and not st["can_close"]
        assert c["teller_sessions_closed"]["ok"]
        blocked(env)

    def test_reconciliation_mismatch_blocks(self, env, monkeypatch):
        from apps.ledger import services as ledger

        monkeypatch.setattr(
            ledger,
            "cash_reconciliation",
            lambda bank: [{"currency": "USD", "ok": False}, {"currency": "SOS", "ok": True}],
        )
        st, c = checks(env)
        assert not c["cash_reconciliation"]["ok"] and not st["can_close"]
        blocked(env)

    def test_trial_balance_mismatch_blocks(self, env, monkeypatch):
        class FakeQS:
            def filter(self, **kw):
                return self

            def values(self, *a):
                return self

            def annotate(self, **kw):
                return [{"currency": "USD", "d": D("5"), "c": D("0"), "n": 1}]

        class FakeLine:
            objects = FakeQS()

        monkeypatch.setattr(eod, "JournalLine", FakeLine)  # the DB trigger forbids real skew
        st, c = checks(env)
        assert not c["trial_balance"]["ok"] and c["trial_balance"]["items"][0]["currency"] == "USD"
        assert not st["can_close"]
        blocked(env)


@pytest.mark.django_db
class TestClose:
    def test_happy_path_next_date_audit_no_entries(self, env):
        close_till(env, open_till(env))
        old = day(env)
        entries = JournalEntry.objects.filter(bank=env.bank).count()
        res = eod.close_day(env.member("manager"))
        old.refresh_from_db()
        assert old.status == "closed" and old.closed_by_id == env.user("manager").pk
        assert old.closed_at
        new = day(env)
        assert new.date == old.date + timedelta(days=1) == res["business_date"]
        assert res["closed_date"] == old.date
        assert JournalEntry.objects.filter(bank=env.bank).count() == entries
        log = AuditLog.objects.get(bank_id=env.bank.pk, action="eod.closed")
        assert log.actor_id == env.user("manager").pk and log.entity_id == str(old.pk)

    def test_teller_can_open_till_on_new_date(self, env):
        first = open_till(env, usd=None)
        close_till(env, first)
        eod.close_day(env.member("manager"))
        second = open_till(env, usd=None, code="T2")
        assert second.business_date == day(env).date
        assert second.business_date == first.business_date + timedelta(days=1)

    def test_can_close_consecutive_days(self, env):
        eod.close_day(env.member("manager"))
        d2 = day(env).date
        eod.close_day(env.member("manager"))
        assert day(env).date == d2 + timedelta(days=1)

    def test_archived_session_read_only(self, env):
        lab.archive_session(env.world["ia"], env.session.pk)
        with pytest.raises(LedgerError) as e:
            eod.close_day(env.member("manager"))
        assert e.value.code == "session_archived"
        assert eod.eod_status(env.member("manager"))["can_close"]  # reads stay allowed
        assert day(env).status == "open"


@pytest.mark.django_db
class TestPermissionsAndIsolation:
    def test_non_managers_forbidden(self, env):
        for role in ("teller", "cso", "vault"):
            with pytest.raises(PermissionDenied):
                eod.eod_status(env.member(role))
            with pytest.raises(PermissionDenied):
                eod.close_day(env.member(role))
        assert day(env).status == "open"

    def test_api_roles_and_shape(self, env):
        assert api(env.user("teller")).get(url(env)).status_code == 403
        assert j(api(env.user("teller")), "post", url(env, "/close")).status_code == 403
        body = api(env.user("manager")).get(url(env)).json()
        assert body["can_close"] is True and len(body["checks"]) == 4
        assert body["business_date"] == str(day(env).date)
        r = j(api(env.user("manager")), "post", url(env, "/close"))
        assert r.status_code == 200
        assert r.json()["business_date"] == str(day(env).date)

    def test_api_blocked_close_returns_409(self, env):
        open_till(env, usd=None)
        r = j(api(env.user("manager")), "post", url(env, "/close"))
        assert r.status_code == 409 and r.json()["code"] == "eod_checks_failed"

    def test_cross_session_and_bank_isolation(self, world):
        a, b = Env(world, "a"), Env(world, "b")
        assert api(a.user("manager")).get(url(b)).status_code in (403, 404)
        assert j(api(a.user("manager")), "post", url(b, "/close")).status_code in (403, 404)
        before = day(b).date
        open_till(b, usd=None)  # B has an open till; A must not care
        eod.close_day(a.member("manager"))
        assert day(b).date == before and day(b).status == "open"
        assert BusinessDay.objects.filter(bank=a.bank).count() == 2
        assert BusinessDay.objects.filter(bank=b.bank).count() == 1
        assert not eod.eod_status(b.member("manager"))["can_close"]
