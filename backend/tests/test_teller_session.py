# ruff: noqa: F811
"""1.8 Teller sessions: open with manager approval, denomination count on close, over/short."""

import uuid
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import Sum

from apps.audit.models import AuditLog
from apps.banking import services as banking
from apps.banking import tellers
from apps.banking.models import (
    Branch,
    CashCount,
    CashPosition,
    CashTransfer,
    Denomination,
    TellerSession,
    TellerSessionStatus,
    Till,
)
from apps.lab import services as lab
from apps.lab.models import Bank
from apps.ledger import services as ledger
from apps.ledger.models import JournalEntry
from apps.ledger.services import LedgerError
from apps.rbac.services import PermissionDenied, assert_maker_checker
from tests.test_cash import Env, add_person, gl_balance, position
from tests.test_lab import (  # noqa: F401  (fixtures)
    _reset_rbac,
    active_session,
    api,
    j,
    world,
)

D = Decimal


@pytest.fixture
def env(world):
    return Env(world)


def mk_till(env, code="T1"):
    return Till.objects.create(bank=env.bank, branch=Branch.objects.get(bank=env.bank), code=code)


def denom(currency, value):
    return Denomination.objects.get(currency=currency, value=D(value))


def lines_for(currency, **spec):
    """lines_for("USD", **{"100": 2}) -> [{denomination_id, quantity}]"""
    return [{"denomination_id": denom(currency, v).pk, "quantity": q} for v, q in spec.items()]


def open_session(env, till=None, floats=None):
    return tellers.request_open(env.member("teller"), (till or mk_till(env)).pk, floats or [])


def approve_float(env, transfer):
    banking.approve_custodian(env.member("vault_custodian"), transfer.pk)
    banking.approve_manager(env.member("manager"), transfer.pk)


def opened(env, usd="500.00", sos=None):
    """Open session whose float went through the normal dual-control flow."""
    floats = [{"currency": c, "amount": D(a)} for c, a in (("USD", usd), ("SOS", sos)) if a]
    ts = open_session(env, floats=floats)
    for t in CashTransfer.objects.filter(bank=env.bank, to_id=ts.pk):
        approve_float(env, t)
    return tellers.approve_open(env.member("manager"), ts.pk)


def balanced(entry):
    agg = entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
    assert agg["d"] == agg["c"] and agg["d"] > 0


def close_flow(env, ts, usd_lines, sos_lines=None):
    tellers.submit_close_count(
        env.member("teller"),
        ts.pk,
        [
            {"currency": "USD", "lines": usd_lines},
            {"currency": "SOS", "lines": sos_lines or []},
        ],
    )
    return tellers.approve_close(env.member("manager"), ts.pk)


def teller_to_vault(env, amount="10"):
    return banking.request_vault_transfer(
        env.member("teller"),
        from_type="teller_session",
        to_type="vault",
        to_id=env.vault.pk,
        currency="USD",
        amount=D(amount),
    )


# ---------------------------------------------------------------------------- open


@pytest.mark.django_db
class TestOpen:
    def test_request_approve_flow_and_audit(self, env):
        ts = open_session(env, floats=[{"currency": "USD", "amount": D("300")}])
        assert ts.status == TellerSessionStatus.PENDING_OPEN and ts.business_date
        # float is requested against the pending_open session; dual control applies
        t = CashTransfer.objects.get(bank=env.bank)
        assert (t.to_type, t.to_id, t.amount) == ("teller_session", ts.pk, D("300.00"))
        assert t.requested_by_id == env.member("teller").pk
        approve_float(env, t)
        assert position(env.bank, ts.pk) == D("300.00")
        ts = tellers.approve_open(env.member("manager"), ts.pk)
        assert ts.status == TellerSessionStatus.OPEN
        assert ts.open_approved_by_id == env.member("manager").pk and ts.opened_at
        actions = set(AuditLog.objects.filter(bank_id=env.bank.pk).values_list("action", flat=True))
        assert {"till.open_requested", "till.open_approved"} <= actions

    def test_maker_checker(self, env):
        ts = open_session(env)
        with pytest.raises(PermissionDenied):
            tellers.approve_open(env.member("teller"), ts.pk)  # role check
        with pytest.raises(PermissionDenied):  # hard person-level check
            assert_maker_checker(ts.teller_member.user_id, env.member("teller").user_id)

    def test_permissions(self, env):
        till = mk_till(env)
        for role in ("manager", "cso", "vault_custodian"):
            with pytest.raises(PermissionDenied):
                tellers.request_open(env.member(role), till.pk, [])
        ts = open_session(env, till)
        for role in ("teller", "cso", "vault_custodian"):
            with pytest.raises(PermissionDenied):
                tellers.approve_open(env.member(role), ts.pk)
            with pytest.raises(PermissionDenied):
                tellers.reject_open(env.member(role), ts.pk, "x")

    def test_one_session_per_teller_per_day_and_per_till(self, env, world):
        till = mk_till(env)
        ts = open_session(env, till)
        with pytest.raises(LedgerError) as e:
            tellers.request_open(env.member("teller"), mk_till(env, "T2").pk, [])
        assert e.value.code == "session_exists"
        _, teller2 = add_person(world, env.session, env.bank, "tell2", "teller")
        with pytest.raises(LedgerError) as e:
            tellers.request_open(teller2, till.pk, [])
        assert e.value.code == "till_in_use"
        with pytest.raises(IntegrityError), transaction.atomic():  # DB constraint backs it
            TellerSession.objects.create(
                bank=env.bank, till=till, teller_member=teller2, business_date=ts.business_date
            )

    def test_reject_keeps_pending_and_cancel_releases_till(self, env):
        till = mk_till(env)
        ts = open_session(env, till, floats=[{"currency": "USD", "amount": D("50")}])
        with pytest.raises(LedgerError):
            tellers.reject_open(env.member("manager"), ts.pk, " ")
        ts = tellers.reject_open(env.member("manager"), ts.pk, "Count the float first")
        assert ts.status == TellerSessionStatus.PENDING_OPEN
        assert ts.open_reject_note == "Count the float first"
        with pytest.raises(PermissionDenied):  # only the owner cancels
            tellers.cancel_open(env.member("manager"), ts.pk)
        ts = tellers.cancel_open(env.member("teller"), ts.pk)
        assert ts.status == TellerSessionStatus.CANCELLED
        assert CashTransfer.objects.get(bank=env.bank).status == "cancelled"
        again = tellers.request_open(env.member("teller"), till.pk, [])  # till + day are free
        assert again.pk != ts.pk and again.status == TellerSessionStatus.PENDING_OPEN

    def test_cancel_blocked_when_cash_issued(self, env):
        ts = open_session(env, floats=[{"currency": "USD", "amount": D("50")}])
        approve_float(env, CashTransfer.objects.get(bank=env.bank))
        with pytest.raises(LedgerError) as e:
            tellers.cancel_open(env.member("teller"), ts.pk)
        assert e.value.code == "session_holds_cash"

    def test_float_validation_and_vault_balance(self, env):
        till = mk_till(env)
        for bad in (
            [{"currency": "EUR", "amount": D("1")}],
            [{"currency": "USD", "amount": D("-1")}],
            [{"currency": "USD", "amount": D("1")}, {"currency": "USD", "amount": D("2")}],
            [{"currency": "USD", "amount": D("999999999")}],  # more than the vault holds
        ):
            with pytest.raises(LedgerError):
                tellers.request_open(env.member("teller"), till.pk, bad)
        assert not TellerSession.objects.filter(bank=env.bank).exists()  # all rolled back
        assert not CashTransfer.objects.filter(bank=env.bank).exists()

    def test_wrong_status(self, env):
        ts = opened(env)
        with pytest.raises(LedgerError) as e:
            tellers.approve_open(env.member("manager"), ts.pk)
        assert e.value.code == "invalid_status"


# ---------------------------------------------------------------------------- transfers


@pytest.mark.django_db
class TestTellerTransfers:
    def test_teller_uses_own_session_and_foreign_id_rejected(self, env, world):
        ts = opened(env, usd="200.00")
        _, teller2 = add_person(world, env.session, env.bank, "tell2", "teller")
        ts2 = tellers.request_open(teller2, mk_till(env, "T2").pk, [])
        for bad in (uuid.uuid4(), ts2.pk):
            with pytest.raises(LedgerError) as e:
                banking.request_vault_transfer(
                    env.member("teller"),
                    from_type="teller_session",
                    from_id=bad,
                    to_type="vault",
                    to_id=env.vault.pk,
                    currency="USD",
                    amount=D("10"),
                )
            assert e.value.code == "foreign_teller_session" and e.value.status == 403
        assert teller_to_vault(env).from_id == ts.pk

    def test_no_session_no_cash_movement(self, env):
        with pytest.raises(LedgerError) as e:
            banking.request_vault_transfer(
                env.member("teller"),
                from_type="vault",
                from_id=env.vault.pk,
                to_type="teller_session",
                currency="USD",
                amount=D("10"),
            )
        assert e.value.code == "no_open_till"

    def test_pending_open_cannot_send_cash(self, env):
        open_session(env)
        with pytest.raises(LedgerError) as e:
            teller_to_vault(env, "1")
        assert e.value.code == "till_not_open"

    def test_manager_issues_to_named_session(self, env):
        ts = opened(env)
        t = banking.request_vault_transfer(
            env.member("manager"),
            from_type="vault",
            from_id=env.vault.pk,
            to_type="teller_session",
            to_id=ts.pk,
            currency="USD",
            amount=D("5"),
        )
        assert t.to_id == ts.pk
        with pytest.raises(LedgerError) as e:  # a manager must name the session
            banking.request_vault_transfer(
                env.member("manager"),
                from_type="vault",
                from_id=env.vault.pk,
                to_type="teller_session",
                currency="USD",
                amount=D("5"),
            )
        assert e.value.code == "teller_session_required"


# ---------------------------------------------------------------------------- close


@pytest.mark.django_db
class TestClose:
    def test_exact_count(self, env):
        ts = opened(env, usd="500.00")
        vault_before = position(env.bank, env.vault.pk)
        ts = close_flow(env, ts, lines_for("USD", **{"100": 5}))
        assert ts.status == TellerSessionStatus.CLOSED and ts.closed_at
        assert ts.close_approved_by_id == env.member("manager").pk
        assert position(env.bank, ts.pk) == 0
        assert position(env.bank, env.vault.pk) == vault_before + D("500")
        assert not JournalEntry.objects.filter(bank=env.bank, source_type="till_close").exists()
        ret = CashTransfer.objects.get(bank=env.bank, from_type="teller_session", currency="USD")
        assert ret.status == "posted" and ret.approved_by_2_id == env.member("manager").pk
        balanced(ret.journal_entry)
        assert all(r["ok"] for r in ledger.cash_reconciliation(env.bank))
        assert ledger.cash_matches_lines(env.bank)

    def test_over(self, env):
        ts = opened(env, usd="500.00")
        vault_before = position(env.bank, env.vault.pk)
        close_flow(env, ts, lines_for("USD", **{"100": 5, "20": 1, "5": 1}))  # 525
        e = JournalEntry.objects.get(bank=env.bank, source_type="till_close")
        balanced(e)
        by = {ln.gl_account.system_tag: ln for ln in e.lines.select_related("gl_account")}
        assert by["CASH_TELLER"].debit == D("25") and by["CASH_OVER"].credit == D("25")
        assert by["CASH_TELLER"].cash_holder_id == ts.pk
        assert gl_balance(env.bank, "CASH_OVER") == D("25")
        assert position(env.bank, ts.pk) == 0
        assert position(env.bank, env.vault.pk) == vault_before + D("525")
        count = CashCount.objects.get(teller_session=ts, currency="USD")
        assert (count.counted_total, count.system_total, count.difference) == (
            D("525"),
            D("500"),
            D("25"),
        )
        assert count.approved_by_id and count.journal_entry_id == e.pk
        assert all(r["ok"] for r in ledger.cash_reconciliation(env.bank))

    def test_short(self, env):
        ts = opened(env, usd="500.00")
        vault_before = position(env.bank, env.vault.pk)
        close_flow(env, ts, lines_for("USD", **{"100": 4, "50": 1}))  # 450
        e = JournalEntry.objects.get(bank=env.bank, source_type="till_close")
        balanced(e)
        by = {ln.gl_account.system_tag: ln for ln in e.lines.select_related("gl_account")}
        assert by["CASH_SHORT"].debit == D("50") and by["CASH_TELLER"].credit == D("50")
        assert gl_balance(env.bank, "CASH_SHORT") == D("50")
        assert position(env.bank, ts.pk) == 0
        assert position(env.bank, env.vault.pk) == vault_before + D("450")
        assert all(r["ok"] for r in ledger.cash_reconciliation(env.bank))

    def test_both_currencies_and_nothing_counted(self, env):
        ts = opened(env, usd="100.00", sos="5000.00")
        close_flow(env, ts, [], lines_for("SOS", **{"1000": 3}))  # USD short 100, SOS short 2000
        for cur, diff in (("USD", D("-100")), ("SOS", D("-2000"))):
            assert CashCount.objects.get(teller_session=ts, currency=cur).difference == diff
            assert position(env.bank, ts.pk, cur) == 0
        assert JournalEntry.objects.filter(bank=env.bank, source_type="till_close").count() == 2
        assert all(r["ok"] for r in ledger.cash_reconciliation(env.bank))

    def test_server_computes_totals(self, env):
        ts = opened(env, usd="500.00")
        tellers.submit_close_count(
            env.member("teller"),
            ts.pk,
            [{"currency": "USD", "lines": lines_for("USD", **{"100": 3, "1": 7})}],
        )
        c = CashCount.objects.get(teller_session=ts, currency="USD")
        assert c.counted_total == D("307") and c.lines.count() == 2
        assert CashCount.objects.get(teller_session=ts, currency="SOS").counted_total == 0

    def test_reject_goes_back_to_open_and_recount_keeps_history(self, env):
        ts = opened(env, usd="500.00")
        tellers.submit_close_count(
            env.member("teller"),
            ts.pk,
            [{"currency": "USD", "lines": lines_for("USD", **{"100": 4})}],
        )
        ts = tellers.reject_close(env.member("manager"), ts.pk, "Recount the 100s")
        assert ts.status == TellerSessionStatus.OPEN and ts.close_reject_note
        assert position(env.bank, ts.pk) == D("500")
        close_flow(env, ts, lines_for("USD", **{"100": 5}))
        usd = CashCount.objects.filter(teller_session=ts, currency="USD")
        assert sorted(usd.values_list("attempt", flat=True)) == [1, 2]
        assert usd.get(attempt=2).approved_by_id and not usd.get(attempt=1).approved_by_id
        view = tellers.session_view(TellerSession.objects.get(pk=ts.pk))
        assert {c["attempt"] for c in view["latest_counts"]} == {2}

    def test_close_blocked_while_transfers_pending(self, env):
        ts = opened(env, usd="500.00")
        t = teller_to_vault(env)
        with pytest.raises(LedgerError) as e:
            tellers.submit_close_count(env.member("teller"), ts.pk, [])
        assert e.value.code == "transfers_pending"
        banking.reject_transfer(env.member("teller"), t.pk, "")
        tellers.submit_close_count(env.member("teller"), ts.pk, [])

    def test_closing_session_is_frozen(self, env):
        ts = opened(env, usd="500.00")
        tellers.submit_close_count(env.member("teller"), ts.pk, [])
        with pytest.raises(LedgerError) as e:
            teller_to_vault(env, "1")
        assert e.value.code == "till_not_open"
        with pytest.raises(LedgerError) as e:
            banking.request_vault_transfer(
                env.member("manager"),
                from_type="vault",
                from_id=env.vault.pk,
                to_type="teller_session",
                to_id=ts.pk,
                currency="USD",
                amount=D("1"),
            )
        assert e.value.code == "till_not_open"

    def test_permissions_and_ownership(self, env, world):
        ts = opened(env)
        _, teller2 = add_person(world, env.session, env.bank, "tell2", "teller")
        with pytest.raises(PermissionDenied):
            tellers.submit_close_count(teller2, ts.pk, [])
        for role in ("manager", "cso", "vault_custodian"):
            with pytest.raises(PermissionDenied):
                tellers.submit_close_count(env.member(role), ts.pk, [])
        tellers.submit_close_count(env.member("teller"), ts.pk, [])
        for role in ("teller", "cso", "vault_custodian"):
            with pytest.raises(PermissionDenied):
                tellers.approve_close(env.member(role), ts.pk)
            with pytest.raises(PermissionDenied):
                tellers.reject_close(env.member(role), ts.pk, "x")
        with pytest.raises(LedgerError):  # reason required
            tellers.reject_close(env.member("manager"), ts.pk, "")

    def test_count_validation(self, env):
        ts = opened(env)
        usd100, sos_note = denom("USD", "100"), denom("SOS", "1000")
        for counts in (
            [{"currency": "USD", "lines": [{"denomination_id": sos_note.pk, "quantity": 1}]}],
            [{"currency": "USD", "lines": [{"denomination_id": usd100.pk, "quantity": -1}]}],
            [{"currency": "USD", "lines": [{"denomination_id": 0, "quantity": 1}]}],
            [{"currency": "USD", "lines": [{"denomination_id": usd100.pk, "quantity": 1}] * 2}],
            [{"currency": "EUR", "lines": []}],
            [{"currency": "USD", "lines": []}, {"currency": "USD", "lines": []}],
        ):
            with pytest.raises(LedgerError):
                tellers.submit_close_count(env.member("teller"), ts.pk, counts)
        assert not CashCount.objects.filter(teller_session=ts).exists()
        assert TellerSession.objects.get(pk=ts.pk).status == TellerSessionStatus.OPEN

    def test_cannot_close_before_open_or_twice(self, env):
        ts = open_session(env)
        with pytest.raises(LedgerError) as e:
            tellers.submit_close_count(env.member("teller"), ts.pk, [])
        assert e.value.code == "invalid_status"
        ts = tellers.approve_open(env.member("manager"), ts.pk)
        close_flow(env, ts, [])
        with pytest.raises(LedgerError):
            tellers.approve_close(env.member("manager"), ts.pk)
        with pytest.raises(LedgerError):
            tellers.submit_close_count(env.member("teller"), ts.pk, [])
        with pytest.raises(LedgerError) as e:  # today's session is used up
            tellers.request_open(env.member("teller"), mk_till(env, "T9").pk, [])
        assert e.value.code == "session_exists"

    def test_no_deletes(self, env):
        ts = opened(env)
        close_flow(env, ts, lines_for("USD", **{"100": 5}))
        with pytest.raises(NotImplementedError):
            ts.delete()
        with pytest.raises(NotImplementedError):
            TellerSession.objects.all().delete()
        with pytest.raises(NotImplementedError):
            CashCount.objects.all().delete()
        assert CashPosition.objects.filter(holder_id=ts.pk).count() == 2


# ---------------------------------------------------------------------------- isolation + API


@pytest.mark.django_db
class TestIsolationAndApi:
    def test_cross_bank_and_cross_session(self, world):
        env_a = Env(world, "a", structure="per_group")
        bank2 = Bank.objects.filter(session=env_a.session, group_no=2).get()
        mgr2 = add_person(world, env_a.session, bank2, "mgr2", "manager")
        tel2 = add_person(world, env_a.session, bank2, "tel2", "teller")
        ts = opened(env_a)
        sid = env_a.session.pk
        m2 = api(mgr2[0])
        assert m2.get(f"/api/s/{sid}/teller-sessions").json() == []
        assert m2.get(f"/api/s/{sid}/teller-sessions/{ts.pk}").status_code == 404
        r = j(m2, "post", f"/api/s/{sid}/teller-sessions/{ts.pk}/approve-open")
        assert r.status_code == 404
        with pytest.raises(LedgerError) as e:
            tellers.approve_close(mgr2[1], ts.pk)
        assert e.value.status == 404
        with pytest.raises(LedgerError) as e:  # a till of bank 1
            tellers.request_open(tel2[1], mk_till(env_a, "X").pk, [])
        assert e.value.status == 404
        assert api(tel2[0]).get(f"/api/s/{sid}/tills").json() == []
        env_b = Env(world, "b")  # another session: not a member here
        assert api(env_b.user("manager")).get(f"/api/s/{sid}/teller-sessions").status_code == 403

    def test_archived_session_read_only(self, env, world):
        ts = opened(env)
        tellers.submit_close_count(env.member("teller"), ts.pk, [])
        lab.archive_session(world["ia"], env.session.pk)
        with pytest.raises(LedgerError) as e:
            tellers.approve_close(env.member("manager"), ts.pk)
        assert e.value.code == "session_archived"
        with pytest.raises(LedgerError):
            tellers.reject_close(env.member("manager"), ts.pk, "x")
        sid = env.session.pk
        mgr = api(env.user("manager"))
        assert mgr.get(f"/api/s/{sid}/teller-sessions").status_code == 200
        r = j(mgr, "post", f"/api/s/{sid}/teller-sessions/{ts.pk}/approve-close")
        assert r.status_code == 409
        assert TellerSession.objects.get(pk=ts.pk).status == TellerSessionStatus.CLOSING

    def test_full_flow_over_api(self, env):
        till = mk_till(env)
        sid = env.session.pk
        base = f"/api/s/{sid}/teller-sessions"
        teller, mgr = api(env.user("teller")), api(env.user("manager"))
        tills = teller.get(f"/api/s/{sid}/tills").json()
        assert [(t["code"], t["available"]) for t in tills] == [("T1", True)]
        assert teller.get(f"{base}/me").json() is None
        r = j(
            teller,
            "post",
            f"{base}/open-request",
            {"till_id": str(till.pk), "floats": [{"currency": "USD", "amount": "400.00"}]},
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["status"] == "pending_open" and len(body["pending_transfers"]) == 1
        assert teller.get(f"/api/s/{sid}/tills").json()[0]["available"] is False
        assert j(teller, "post", f"{base}/{body['id']}/approve-open").status_code == 403
        assert [s["id"] for s in mgr.get(base).json()] == [body["id"]]
        assert teller.get(base).status_code == 403
        t_id = body["pending_transfers"][0]["id"]
        cust = api(env.user("vault_custodian"))
        r = j(cust, "post", f"/api/s/{sid}/cash-transfers/{t_id}/approve-custodian")
        assert r.status_code == 200
        r = j(mgr, "post", f"/api/s/{sid}/cash-transfers/{t_id}/approve-manager")
        assert r.status_code == 200
        r = j(mgr, "post", f"{base}/{body['id']}/approve-open")
        assert r.json()["status"] == "open"
        assert r.json()["balances"] == [
            {"currency": "SOS", "balance": "0.00"},
            {"currency": "USD", "balance": "400.00"},
        ]
        assert teller.get(f"{base}/me").json()["id"] == body["id"]
        # a teller request without a holder id uses the own session
        r = j(
            teller,
            "post",
            f"/api/s/{sid}/cash-transfers",
            {
                "from_type": "teller_session",
                "to_type": "vault",
                "to_id": str(env.vault.pk),
                "currency": "USD",
                "amount": "50",
            },
        )
        assert r.status_code == 200 and r.json()["from_id"] == body["id"]
        j(teller, "post", f"/api/s/{sid}/cash-transfers/{r.json()['id']}/reject", {"reason": ""})
        dens = teller.get("/api/denominations").json()
        usd100 = next(d for d in dens if d["currency"] == "USD" and d["value"] == "100.00")
        payload = {
            "counts": [
                {"currency": "USD", "lines": [{"denomination_id": usd100["id"], "quantity": 4}]}
            ]
        }
        r = j(teller, "post", f"{base}/{body['id']}/close-count", payload)
        assert r.status_code == 200, r.content
        assert r.json()["status"] == "closing"
        usd = next(c for c in r.json()["latest_counts"] if c["currency"] == "USD")
        assert (usd["counted_total"], usd["system_total"], usd["difference"]) == (
            "400.00",
            "400.00",
            "0.00",
        )
        assert j(teller, "post", f"{base}/{body['id']}/approve-close").status_code == 403
        r = j(mgr, "post", f"{base}/{body['id']}/approve-close")
        assert r.json()["status"] == "closed"
        assert all(b["balance"] == "0.00" for b in r.json()["balances"])
        assert teller.get(f"{base}/{body['id']}").status_code == 200
