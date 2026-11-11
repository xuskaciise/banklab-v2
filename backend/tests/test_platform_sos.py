# ruff: noqa: F811
"""1.12a Platform SOS on/off: Admin setting, server-side rejection of new SOS business,
history/reversals/till close/reports stay available."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.banking import cheques, tellers, transactions
from apps.banking import services as banking
from apps.banking.models import Branch, CashTransfer, Cheque, TellerSession, Till
from apps.core import platform
from apps.core.models import PlatformSettings
from apps.products import services as ps
from apps.products.models import Account, Product
from tests.test_customers import Env, _media, complete_kyc, individual, make  # noqa: F401
from tests.test_lab import _reset_rbac, api, j, world  # noqa: F401
from tests.test_teller_session import close_flow, lines_for
from tests.test_transactions import (  # noqa: F401
    PARTY,
    bal,
    dep,
    env,
    err,
    mk_account,
    open_till,
    wd,
    xfer,
)

D = Decimal
URL = "/api/platform/settings"


def opened(env, usd, sos):
    till = Till.objects.create(bank=env.bank, branch=Branch.objects.get(bank=env.bank), code="T1")
    floats = [{"currency": "USD", "amount": D(usd)}, {"currency": "SOS", "amount": D(sos)}]
    ts = tellers.request_open(env.member("teller"), till.pk, floats)
    for t in CashTransfer.objects.filter(bank=env.bank, to_id=ts.pk):
        banking.approve_custodian(env.member("vault"), t.pk)
        banking.approve_manager(env.member("manager"), t.pk)
    return tellers.approve_open(env.member("manager"), ts.pk)


def set_sos(on: bool):
    s = platform.get_platform_settings()
    s.sos_enabled = on
    s.save()


@pytest.fixture
def sos_ready(env):
    """Open till with a USD + SOS float, one funded SOS account, while SOS is still on."""
    ts = opened(env, usd="500.00", sos="100000.00")
    a = mk_account(env, "SAV-SOS")
    b = mk_account(env, "SAV-SOS")
    dep(env, a, "5000")
    return env, ts, a, b


@pytest.mark.django_db
class TestSettingsApi:
    def test_default_on_and_any_user_reads(self, world):
        assert platform.enabled_currencies() == ["USD", "SOS"]
        for user in (world["admin"], world["ia"], world["studs"][0]):
            r = api(user).get(URL)
            assert r.status_code == 200
            assert r.json() == {"sos_enabled": True, "currencies": ["USD", "SOS"]}

    def test_unauthenticated(self, client):
        assert client.get(URL).status_code in (401, 403)

    def test_only_admin_writes(self, world):
        for user in (world["ia"], world["studs"][0]):
            r = j(api(user), "put", URL, {"sos_enabled": False})
            assert r.status_code == 403
        assert platform.get_platform_settings().sos_enabled is True
        assert not AuditLog.objects.filter(action="platform.settings_updated").exists()

    def test_admin_toggles_and_audits(self, world):
        r = j(api(world["admin"]), "put", URL, {"sos_enabled": False})
        assert r.status_code == 200
        assert r.json() == {"sos_enabled": False, "currencies": ["USD"]}
        assert api(world["studs"][0]).get(URL).json()["currencies"] == ["USD"]
        row = AuditLog.objects.get(action="platform.settings_updated")
        assert row.actor_id == world["admin"].id
        assert row.before == {"sos_enabled": True} and row.after == {"sos_enabled": False}
        j(api(world["admin"]), "put", URL, {"sos_enabled": True})
        assert AuditLog.objects.filter(action="platform.settings_updated").count() == 2
        assert PlatformSettings.objects.count() == 1


@pytest.mark.django_db
class TestRejectionsWhenOff:
    def test_open_account(self, env):
        c = make(env, "cso", individual(address="Hodan"))
        complete_kyc(env, c, "cso")
        sos = Product.objects.get(bank=env.bank, code="SAV-SOS")
        usd = Product.objects.get(bank=env.bank, code="SAV-USD")
        set_sos(False)
        e = err(
            lambda: ps.open_account(env.member("cso"), customer_id=c.pk, product_id=sos.pk),
            "currency_disabled",
            400,
        )
        assert e.message == "SOS currency is disabled"
        assert not Account.objects.filter(bank=env.bank, currency="SOS").exists()
        ps.open_account(env.member("cso"), customer_id=c.pk, product_id=usd.pk)  # USD still fine
        set_sos(True)
        assert ps.open_account(env.member("cso"), customer_id=c.pk, product_id=sos.pk)

    def test_api_returns_400_with_code(self, sos_ready):
        env, _, a, _ = sos_ready
        set_sos(False)
        body = {"account_id": str(a.pk), "amount": "10", "currency": "SOS", **PARTY}
        url = f"/api/s/{env.session.pk}/transactions/deposit"
        r = j(api(env.user("teller")), "post", url, body)
        assert r.status_code == 400 and r.json()["code"] == "currency_disabled"
        assert "SOS currency is disabled" in r.json()["detail"]

    def test_deposit_withdraw_transfer_and_back_on(self, sos_ready):
        env, _, a, b = sos_ready
        before = bal(a)
        set_sos(False)
        err(lambda: dep(env, a, "10"), "currency_disabled")
        err(lambda: wd(env, a, "10"), "currency_disabled")
        err(lambda: xfer(env, a, b, "10"), "currency_disabled")
        assert bal(a) == before and bal(b) == 0
        set_sos(True)
        dep(env, a, "10")
        wd(env, a, "5")
        xfer(env, a, b, "5")
        assert bal(a) == before + D("10") - D("5") - D("5") and bal(b) == D("5")

    def test_cheque_withdrawal(self, env):
        opened(env, usd="500.00", sos="100000.00")
        acc = mk_account(env, "CUR-SOS")
        dep(env, acc, "5000")
        cheques.issue_chequebook(env.member("cso"), acc.pk, 10)
        no = Cheque.objects.filter(chequebook__account=acc).order_by("number").first().number
        kw = dict(account_id=acc.pk, cheque_no=no, amount=D("10"), currency="SOS", **PARTY)
        set_sos(False)
        err(lambda: transactions.cheque_withdraw(env.member("teller"), **kw), "currency_disabled")
        assert Cheque.objects.get(chequebook__account=acc, number=no).status != "paid"
        set_sos(True)
        transactions.cheque_withdraw(env.member("teller"), **kw)

    def test_till_float_and_vault_transfer(self, env):
        till = Till.objects.create(
            bank=env.bank, branch=Branch.objects.get(bank=env.bank), code="T1"
        )
        set_sos(False)
        floats = [{"currency": "SOS", "amount": D("1000")}]
        err(lambda: tellers.request_open(env.member("teller"), till.pk, floats), "currency_disabled")
        assert not TellerSession.objects.filter(bank=env.bank).exists()
        set_sos(True)
        ts = tellers.request_open(env.member("teller"), till.pk, floats)
        set_sos(False)
        err(
            lambda: banking.request_vault_transfer(
                env.member("teller"),
                from_type="vault",
                from_id=till.branch.vault.pk,
                to_type="teller_session",
                to_id=ts.pk,
                currency="SOS",
                amount=D("5"),
            ),
            "currency_disabled",
        )


@pytest.mark.django_db
class TestHistoryStillWorks:
    def test_reversal_with_sos_off(self, sos_ready):
        env, _, a, _ = sos_ready
        t = dep(env, a, "200")
        set_sos(False)
        r = transactions.reverse(env.member("teller"), t.pk, "typo")
        assert r.status == "reversed" and bal(a) == D("5000.00")

    def test_till_close_with_sos_cash_with_sos_off(self, sos_ready):
        env, ts, _, _ = sos_ready
        set_sos(False)
        usd = lines_for("USD", **{"100": 5})
        sos = lines_for("SOS", **{"1000": 105})
        closed = close_flow(env, ts, usd, sos)
        assert closed.status == "closed"

    def test_reads_stay_available(self, sos_ready):
        env, _, a, _ = sos_ready
        set_sos(False)
        c = api(env.user("manager"))
        assert c.get(f"/api/s/{env.session.pk}/accounts/{a.pk}").status_code == 200
        assert c.get(f"/api/s/{env.session.pk}/transactions").status_code == 200
        assert c.get(f"/api/s/{env.session.pk}/reports/trial-balance").status_code == 200


@pytest.mark.django_db
class TestReports:
    def titles(self, env, slug, key="manager"):
        r = api(env.user(key)).get(f"/api/s/{env.session.pk}/reports/{slug}")
        assert r.status_code == 200, r.content
        return [s["title"] for s in r.json()["sections"]]

    def test_sos_sections_hidden_without_sos_data(self, env):
        open_till(env)
        a = mk_account(env)
        dep(env, a, "100")
        assert any("SOS" in t for t in self.titles(env, "trial-balance"))
        set_sos(False)
        for slug in ("trial-balance", "balance-sheet", "income-statement", "branch-daily"):
            assert not any("SOS" in t for t in self.titles(env, slug)), slug
        r = api(env.user("manager")).get(
            f"/api/s/{env.session.pk}/reports/trial-balance", {"currency": "SOS"}
        )
        assert r.status_code == 200 and "SOS" in r.json()["sections"][0]["title"]

    def test_sos_sections_kept_when_bank_has_sos_data(self, sos_ready):
        env, *_ = sos_ready
        set_sos(False)
        for slug in ("trial-balance", "balance-sheet", "income-statement"):
            assert any("SOS" in t for t in self.titles(env, slug)), slug

    def test_cross_bank_and_session_isolation(self, sos_ready, world):
        env, _, a, _ = sos_ready
        other = Env(world, "x")
        set_sos(False)
        # other bank has no SOS data: SOS sections hidden even though bank A has SOS history
        assert not any("SOS" in t for t in self.titles(other, "trial-balance"))
        assert any("SOS" in t for t in self.titles(env, "trial-balance"))
        # the other bank's manager cannot read bank A's SOS account
        c = api(other.user("manager"))
        assert c.get(f"/api/s/{env.session.pk}/accounts/{a.pk}").status_code in (403, 404)
        assert c.get(f"/api/s/{other.session.pk}/accounts/{a.pk}").status_code == 404
