# ruff: noqa: F811
"""1.11 End-of-day status: day summary and recent closings."""

from decimal import Decimal

import pytest

from apps.banking import eod
from apps.banking.models import BusinessDay
from tests.test_customers import Env
from tests.test_eod import close_till
from tests.test_lab import _reset_rbac, api, world  # noqa: F401
from tests.test_transactions import dep, mk_account, open_till, wd, xfer

D = Decimal


@pytest.fixture
def env(world):
    return Env(world)


def summary(env):
    return eod.eod_status(env.member("manager"))["summary"]


def by_type(env):
    return {(r["type"], r["currency"]): r for r in summary(env)["by_type"]}


@pytest.mark.django_db
class TestSummary:
    def test_counts_and_amounts(self, env):
        open_till(env)
        a, b = mk_account(env), mk_account(env)
        dep(env, a, "1000")
        dep(env, a, "500.50")
        wd(env, a, "200")
        xfer(env, a, b, "300")
        s = summary(env)
        t = by_type(env)
        assert s["transactions_total"] == 4 and s["reversed_count"] == 0
        assert t[("cash_deposit", "USD")]["count"] == 2
        assert t[("cash_deposit", "USD")]["amount"] == D("1500.50")
        assert t[("cash_withdrawal", "USD")]["amount"] == D("200.00")
        assert t[("transfer", "USD")]["count"] == 1
        assert t[("transfer", "USD")]["amount"] == D("300.00")
        assert s["teller_sessions"] == {"closed": 0, "total": 1}

    def test_pending_excluded(self, env):
        open_till(env)
        a = mk_account(env)
        dep(env, a, "100")
        assert dep(env, a, "20000.01").status == "pending_approval"
        s = summary(env)
        assert s["transactions_total"] == 1
        assert by_type(env)[("cash_deposit", "USD")]["amount"] == D("100.00")

    def test_vault_and_sessions(self, env):
        ts = open_till(env, usd="50000")
        before = {v["currency"]: v["amount"] for v in summary(env)["vault_balances"]}
        assert "USD" in before
        close_till(env, ts)
        s = summary(env)
        assert s["teller_sessions"] == {"closed": 1, "total": 1}
        assert all(isinstance(v["amount"], Decimal) for v in s["vault_balances"])

    def test_other_bank_excluded(self, world):
        a, b = Env(world, "a"), Env(world, "b")
        open_till(b)
        acc = mk_account(b)
        dep(b, acc, "700")
        s = summary(a)
        assert s["transactions_total"] == 0 and s["by_type"] == []
        assert s["teller_sessions"] == {"closed": 0, "total": 0}
        assert summary(b)["transactions_total"] == 1

    def test_api_shape_money_as_string(self, env):
        open_till(env)
        dep(env, mk_account(env), "10")
        body = api(env.user("manager")).get(f"/api/s/{env.session.pk}/eod").json()
        row = body["summary"]["by_type"][0]
        assert row["type"] == "cash_deposit" and row["amount"] == "10.00"
        assert set(body["summary"]) == {
            "transactions_total",
            "reversed_count",
            "by_type",
            "teller_sessions",
            "vault_balances",
        }
        assert body["recent_closings"] == []


@pytest.mark.django_db
class TestRecentClosings:
    def test_newest_first_limit_and_scope(self, world):
        a, b = Env(world, "a"), Env(world, "b")
        for _ in range(6):
            eod.close_day(a.member("manager"))
        eod.close_day(b.member("manager"))
        rows = eod.eod_status(a.member("manager"))["recent_closings"]
        assert len(rows) == 5
        dates = [r["date"] for r in rows]
        assert dates == sorted(dates, reverse=True)
        assert rows[0]["closed_by_name"]
        newest = BusinessDay.objects.filter(bank=a.bank, status="closed").order_by("-date").first()
        assert rows[0]["date"] == newest.date
        assert len(eod.eod_status(b.member("manager"))["recent_closings"]) == 1
