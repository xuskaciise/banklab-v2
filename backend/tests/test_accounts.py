# ruff: noqa: F811
"""1.7 Products & Accounts: default products, KYC gate, sequential numbers, permissions,
own-visibility, bank/session isolation, closing rules and audit.

Opening/closing an account moves no money, so there is no journal entry to balance
(Dr = Cr) here; the tests prove no entry is created and the ledger stays untouched."""

import threading
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from apps.audit.models import AuditLog
from apps.lab import services as lab
from apps.ledger.models import GLAccount, JournalEntry
from apps.ledger.services import LedgerError
from apps.products import services as ps
from apps.products.models import Account, Product
from apps.rbac import services as rbac
from tests.test_customers import (  # noqa: F401  (fixtures + helpers)
    Env,
    _media,
    complete_kyc,
    individual,
    make,
)
from tests.test_lab import _reset_rbac, api, j, world  # noqa: F401


@pytest.fixture
def env(world):
    return Env(world)


def kyc_customer(env, key="cso", **kw):
    c = make(env, key, individual(address="Hodan", **kw))
    complete_kyc(env, c, key)
    return c


def product(env, code="SAV-USD", bank=None):
    return Product.objects.get(bank=bank or env.bank, code=code)


def open_(env, c, code="SAV-USD", key="cso", **kw):
    return ps.open_account(
        env.member(key), customer_id=c.pk, product_id=product(env, code).pk, **kw
    )


def url(env, path=""):
    return f"/api/s/{env.session.pk}{path}"


def post_open(client, env, c, code="SAV-USD"):
    return j(
        client,
        "post",
        url(env, "/accounts"),
        {"customer_id": str(c.pk), "product_id": str(product(env, code).pk)},
    )


@pytest.mark.django_db
class TestProducts:
    def test_defaults_provisioned(self, env):
        rows = {p.code: p for p in Product.objects.filter(bank=env.bank)}
        assert set(rows) == {"SAV-USD", "SAV-SOS", "CUR-USD", "CUR-SOS"}
        for code, tag, cheques in (
            ("SAV-USD", "DEP_SAVINGS", False),
            ("SAV-SOS", "DEP_SAVINGS", False),
            ("CUR-USD", "DEP_CURRENT", True),
            ("CUR-SOS", "DEP_CURRENT", True),
        ):
            p = rows[code]
            assert p.gl_account.system_tag == tag and p.gl_account.bank_id == env.bank.pk
            assert p.allows_cheques is cheques and p.banking_model == "conventional"
            assert p.currency == code[-3:] and p.min_balance == 0
        assert GLAccount.objects.get(pk=rows["SAV-USD"].gl_account_id).code == "2110"
        assert rows["CUR-SOS"].gl_account.code == "2120"

    def test_provisioning_idempotent(self, env):
        from apps.products.provisioning import provision_bank_products

        provision_bank_products(env.bank)
        assert Product.objects.filter(bank=env.bank).count() == 4

    def test_list_endpoint_bank_scoped(self, world, env):
        other = Env(world, "x")
        r = api(env.user("cso")).get(url(env, "/products"))
        assert r.status_code == 200
        ids = {p["id"] for p in r.json()}
        assert ids == {str(p.pk) for p in Product.objects.filter(bank=env.bank)}
        assert not ids & {str(p.pk) for p in Product.objects.filter(bank=other.bank)}
        assert api(env.user("vault")).get(url(env, "/products")).status_code == 403


@pytest.mark.django_db
class TestOpen:
    def test_kyc_incomplete_rejected(self, env):
        c = make(env, "cso", individual(address=""))
        with pytest.raises(LedgerError) as e:
            open_(env, c)
        assert e.value.code == "kyc_incomplete" and e.value.status == 400
        assert "address_missing" in {m["code"] for m in e.value.extra["kyc_missing"]}
        assert Account.objects.count() == 0

    def test_kyc_incomplete_api_returns_list(self, env):
        c = make(env, "cso", individual(address=""))
        r = post_open(api(env.user("cso")), env, c)
        assert r.status_code == 400
        body = r.json()
        assert body["code"] == "kyc_incomplete" and body["kyc_missing"]

    def test_open_ok(self, env):
        c = kyc_customer(env)
        entries = JournalEntry.objects.count()
        a = open_(env, c, "CUR-SOS", mandate="all_jointly")
        assert (a.account_no, a.status, a.currency, a.mandate) == (
            1000001,
            "active",
            "SOS",
            "all_jointly",
        )
        assert a.ledger_balance == Decimal("0.00") and a.created_by_id == env.member("cso").pk
        assert JournalEntry.objects.count() == entries  # no money moved

    def test_bad_mandate(self, env):
        c = kyc_customer(env)
        with pytest.raises(LedgerError) as e:
            open_(env, c, mandate="nope")
        assert e.value.code == "invalid_account"

    def test_numbers_sequential_and_independent_per_bank(self, world, env):
        other = Env(world, "y")
        c, c2 = kyc_customer(env), kyc_customer(other)
        nos = [open_(env, c).account_no, open_(env, c, "CUR-USD").account_no]
        assert nos == [1000001, 1000002]
        assert open_(other, c2).account_no == 1000001

    def test_permission_denied(self, env):
        c = kyc_customer(env)
        for key in ("teller", "accountant", "vault"):
            with pytest.raises(rbac.PermissionDenied):
                open_(env, c, key=key)
        assert post_open(api(env.user("teller")), env, c).status_code == 403
        assert Account.objects.count() == 0

    def test_manager_can_open(self, env):
        c = kyc_customer(env)
        assert open_(env, c, key="manager").created_by_id == env.member("manager").pk

    def test_audit_written(self, env):
        a = open_(env, kyc_customer(env))
        row = AuditLog.objects.get(action="account.opened", entity_id=str(a.pk))
        assert row.bank_id == env.bank.pk and row.after["account_no"] == 1000001


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_open_numbers_unique(world):
    env = Env(world, "c")
    c = kyc_customer(env)
    results, errors = [], []

    def work():
        try:
            results.append(open_(env, c).account_no)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=work) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and sorted(results) == [1000001, 1000002, 1000003]


@pytest.mark.django_db
class TestIsolation:
    def test_cross_bank_and_session(self, world, env):
        other = Env(world, "z")
        oc = kyc_customer(other)
        oa = open_(other, oc)
        mine = kyc_customer(env)
        cso, manager = env.member("cso"), env.member("manager")
        with pytest.raises(LedgerError) as e:
            ps.open_account(cso, customer_id=oc.pk, product_id=product(env).pk)
        assert e.value.status == 404
        with pytest.raises(LedgerError) as e:
            ps.open_account(cso, customer_id=mine.pk, product_id=product(other).pk)
        assert e.value.status == 404
        assert ps.list_accounts(manager).count() == 0
        for call in (ps.get_account, ps.close_account):
            with pytest.raises(LedgerError) as e:
                call(manager, oa.pk)
            assert e.value.status == 404
        mgr = api(env.user("manager"))
        assert mgr.get(url(env, f"/accounts/{oa.pk}")).status_code == 404
        assert j(mgr, "post", url(env, f"/accounts/{oa.pk}/close")).status_code == 404
        assert mgr.get(url(other, "/accounts")).status_code in (403, 404)
        assert Account.objects.get(pk=oa.pk).status == "active"

    def test_own_visibility(self, world):
        env = Env(world, default_visibility="own")
        c1, c2 = kyc_customer(env, "cso"), kyc_customer(env, "cso2")
        a1, a2 = open_(env, c1), open_(env, c2, key="cso2")
        shared = Account.objects.create(
            bank=env.bank,
            account_no=5,
            customer=c1,
            product=product(env),
            currency="USD",
            is_seed=True,
            opened_at=a1.opened_at,
        )
        assert {a.pk for a in ps.list_accounts(env.member("cso"))} == {a1.pk, shared.pk}
        assert {a.pk for a in ps.list_accounts(env.member("cso2"))} == {a2.pk, shared.pk}
        assert {a.pk for a in ps.list_accounts(env.member("teller"))} == {shared.pk}
        with pytest.raises(LedgerError) as e:
            ps.get_account(env.member("cso"), a2.pk)
        assert e.value.status == 404
        with pytest.raises(LedgerError) as e:
            ps.close_account(env.member("cso"), a2.pk)
        assert e.value.status == 404
        with pytest.raises(LedgerError) as e:
            open_(env, c2)  # another cso's customer is invisible in own mode
        assert e.value.status == 404
        for key in ("manager", "accountant"):
            assert ps.list_accounts(env.member(key)).count() == 3

    def test_vault_cannot_view(self, env):
        with pytest.raises(rbac.PermissionDenied):
            ps.list_accounts(env.member("vault"))
        assert api(env.user("vault")).get(url(env, "/accounts")).status_code == 403

    def test_archived_read_only(self, env):
        c = kyc_customer(env)
        a = open_(env, c)
        lab.archive_session(env.world["ia"], env.session.pk)
        with pytest.raises(LedgerError) as e:
            open_(env, c)
        assert e.value.code == "session_archived"
        with pytest.raises(LedgerError) as e:
            ps.close_account(env.member("cso"), a.pk)
        assert e.value.code == "session_archived"
        assert ps.get_account(env.member("cso"), a.pk).pk == a.pk


@pytest.mark.django_db
class TestClose:
    def test_close_ok_and_audit(self, env):
        a = open_(env, kyc_customer(env))
        closed = ps.close_account(env.member("manager"), a.pk)
        assert closed.status == "closed" and closed.closed_at is not None
        row = AuditLog.objects.get(action="account.closed", entity_id=str(a.pk))
        assert row.before["status"] == "active" and row.after["status"] == "closed"

    def test_cannot_close_twice(self, env):
        a = open_(env, kyc_customer(env))
        ps.close_account(env.member("cso"), a.pk)
        with pytest.raises(LedgerError) as e:
            ps.close_account(env.member("cso"), a.pk)
        assert e.value.code == "account_not_active" and e.value.status == 409

    def test_requires_zero_balance(self, env):
        a = open_(env, kyc_customer(env))
        Account.objects.filter(pk=a.pk).update(ledger_balance=Decimal("5.00"))
        with pytest.raises(LedgerError) as e:
            ps.close_account(env.member("cso"), a.pk)
        assert e.value.code == "balance_not_zero"
        assert Account.objects.get(pk=a.pk).status == "active"

    def test_permission_denied(self, env):
        a = open_(env, kyc_customer(env))
        for key in ("teller", "accountant", "vault"):
            with pytest.raises(rbac.PermissionDenied):
                ps.close_account(env.member(key), a.pk)
        r = j(api(env.user("teller")), "post", url(env, f"/accounts/{a.pk}/close"))
        assert r.status_code == 403

    def test_negative_balance_blocked_by_db(self, env):
        a = open_(env, kyc_customer(env))
        with pytest.raises(IntegrityError), transaction.atomic():
            Account.objects.filter(pk=a.pk).update(ledger_balance=Decimal("-1"))

    def test_no_delete(self, env):
        a = open_(env, kyc_customer(env))
        with pytest.raises(NotImplementedError):
            Account.objects.get(pk=a.pk).delete()


@pytest.mark.django_db
class TestApi:
    def test_flow(self, env):
        c = kyc_customer(env)
        cso = api(env.user("cso"))
        r = post_open(cso, env, c, "CUR-USD")
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["account_no"] == 1000001 and body["cif_no"] == c.cif_no
        assert body["customer_name"] == c.display_name and body["product_kind"] == "current"
        assert body["currency"] == "USD" and body["ledger_balance"] == "0.00"
        listed = cso.get(url(env, f"/accounts?customer_id={c.pk}&status=active")).json()
        assert listed["count"] == 1
        assert cso.get(url(env, "/accounts?status=closed")).json()["count"] == 0
        assert cso.get(url(env, "/accounts?status=bogus")).status_code == 400
        by_no = cso.get(url(env, "/accounts?account_no=1000001")).json()
        assert by_no["count"] == 1 and by_no["items"][0]["id"] == body["id"]
        assert cso.get(url(env, "/accounts?account_no=1000002")).json()["count"] == 0
        assert cso.get(url(env, "/accounts?account_no=99999999999")).status_code == 422
        assert cso.get(url(env, f"/accounts/{body['id']}")).json()["id"] == body["id"]
        closed = j(cso, "post", url(env, f"/accounts/{body['id']}/close"))
        assert closed.status_code == 200 and closed.json()["status"] == "closed"
        assert j(cso, "post", url(env, f"/accounts/{body['id']}/close")).status_code == 409
