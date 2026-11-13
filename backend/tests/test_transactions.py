# ruff: noqa: F811
"""1.9 Transactions: cash deposit/withdrawal, transfer, limits + approval, reversal, receipt."""

from decimal import Decimal

import pytest
from django.db.models import Sum

from apps.audit.models import AuditLog
from apps.banking import approvals, receipts, tellers, transactions
from apps.banking import services as banking
from apps.banking.models import (
    Approval,
    Branch,
    BusinessDay,
    CashPosition,
    CashTransfer,
    LimitRule,
    TellerSession,
    TellerSessionStatus,
    Till,
    Transaction,
)
from apps.lab import services as lab
from apps.ledger.models import GLBalance, JournalEntry
from apps.ledger.services import LedgerError
from apps.products import services as ps
from apps.products.models import Account, Product
from apps.rbac.services import PermissionDenied
from tests.test_customers import Env, _media, complete_kyc, individual, make  # noqa: F401
from tests.test_lab import _reset_rbac, api, j, world  # noqa: F401

D = Decimal
PARTY = {"party_name": "Ali Warsame", "party_id_no": "ID-77", "party_phone": "+252611000111"}


@pytest.fixture
def env(world):
    return Env(world)


def mk_account(env, code="SAV-USD", key="cso"):
    c = make(env, key, individual(address="Hodan"))
    complete_kyc(env, c, key)
    product = Product.objects.get(bank=env.bank, code=code)
    return ps.open_account(env.member(key), customer_id=c.pk, product_id=product.pk)


def open_till(env, key="teller", usd="50000", code="T1"):
    till = Till.objects.create(bank=env.bank, branch=Branch.objects.get(bank=env.bank), code=code)
    floats = [{"currency": "USD", "amount": D(usd)}] if usd else []
    ts = tellers.request_open(env.member(key), till.pk, floats)
    for t in CashTransfer.objects.filter(bank=env.bank, to_id=ts.pk):
        banking.approve_custodian(env.member("vault"), t.pk)
        banking.approve_manager(env.member("manager"), t.pk)
    return tellers.approve_open(env.member("manager"), ts.pk)


def dep(env, acc, amount, key="teller", **kw):
    return transactions.deposit(
        env.member(key),
        account_id=acc.pk,
        amount=D(amount),
        currency=acc.currency,
        **{**PARTY, **kw},
    )


def wd(env, acc, amount, key="teller", **kw):
    return transactions.withdraw(
        env.member(key),
        account_id=acc.pk,
        amount=D(amount),
        currency=acc.currency,
        **{**PARTY, **kw},
    )


def xfer(env, a, b, amount, key="teller", **kw):
    return transactions.transfer(
        env.member(key),
        from_account_id=a.pk,
        to_account_id=b.pk,
        amount=D(amount),
        currency=a.currency,
        **kw,
    )


def bal(acc):
    return Account.objects.get(pk=acc.pk).ledger_balance


def till_cash(ts, currency="USD"):
    return CashPosition.objects.get(holder_id=ts.pk, currency=currency).balance


def gl(bank, tag, currency="USD"):
    return GLBalance.objects.get(
        gl_account__bank=bank, gl_account__system_tag=tag, currency=currency
    ).balance


def balanced(entry):
    agg = entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
    assert agg["d"] == agg["c"] and agg["d"] > 0


def err(call, code=None, status=None):
    with pytest.raises(LedgerError) as e:
        call()
    if code:
        assert e.value.code == code
    if status:
        assert e.value.status == status
    return e.value


@pytest.fixture
def ready(env):
    """Bank with an open till for `teller`, one funded savings account and an empty one."""
    ts = open_till(env)
    a = mk_account(env)
    b = mk_account(env)
    dep(env, a, "1000")
    return env, ts, a, b


@pytest.mark.django_db
class TestDeposit:
    def test_posts_balanced_entry_and_moves_balances(self, ready):
        env, ts, a, _ = ready
        cash_before, dep_before = till_cash(ts), gl(env.bank, "DEP_SAVINGS")
        t = dep(env, a, "250.50", narration="salary")
        assert t.status == "posted" and t.type == "cash_deposit"
        assert t.ref_no == f"B00-{t.business_date:%Y%m%d}-0002"
        assert (t.party_name, t.party_id_no, t.party_phone) == tuple(PARTY.values())
        assert bal(a) == D("1250.50")
        assert till_cash(ts) == cash_before + D("250.50")
        assert gl(env.bank, "DEP_SAVINGS") == dep_before + D("250.50")
        entry = t.journal_entry
        balanced(entry)
        assert entry.source_type == "transaction" and entry.source_id == t.pk
        lines = {ln.gl_account.code: ln for ln in entry.lines.select_related("gl_account")}
        assert lines["1120"].debit == D("250.50") and lines["1120"].cash_holder_id == ts.pk
        assert lines["2110"].credit == D("250.50") and lines["2110"].account_id == a.pk
        assert AuditLog.objects.filter(action="txn.posted", entity_id=str(t.pk)).exists()

    @pytest.mark.parametrize("amount", ["0", "-5", "1.234"])
    def test_bad_amount(self, ready, amount):
        env, _, a, _ = ready
        err(lambda: dep(env, a, amount), "invalid_amount")

    def test_party_fields_required(self, ready):
        env, _, a, _ = ready
        for field in PARTY:
            err(lambda f=field: dep(env, a, "5", **{f: " "}), status=400)

    def test_currency_mismatch_and_inactive_account(self, ready):
        env, _, a, _ = ready
        err(
            lambda: transactions.deposit(
                env.member("teller"), account_id=a.pk, amount=D("5"), currency="SOS", **PARTY
            ),
            "currency_mismatch",
        )
        z = mk_account(env)
        ps.close_account(env.member("cso"), z.pk)
        err(lambda: dep(env, z, "5"), "account_not_active", 409)

    def test_requires_own_open_till(self, env):
        a = mk_account(env)
        err(lambda: dep(env, a, "5"), "no_open_till", 409)  # no session at all
        ts = open_till(env)
        TellerSession.objects.filter(pk=ts.pk).update(status=TellerSessionStatus.CLOSED)
        err(lambda: dep(env, a, "5"), "no_open_till", 409)

    def test_other_tellers_till_is_not_used(self, ready):
        env, ts, a, _ = ready
        ts2 = open_till(env, "teller2", usd="100", code="T2")
        dep(env, a, "10", key="teller2")
        assert till_cash(ts2) == D("110.00") and till_cash(ts) == D("51000.00")

    def test_permission_denied(self, ready):
        env, _, a, _ = ready
        for key in ("cso", "manager", "accountant", "vault"):
            with pytest.raises(PermissionDenied):
                dep(env, a, "5", key=key)

    def test_archived_session_read_only(self, ready, world):
        env, _, a, _ = ready
        lab.archive_session(world["ia"], env.session.pk)
        err(lambda: dep(env, a, "5"), "session_archived", 409)

    def test_closed_business_day(self, ready):
        env, _, a, _ = ready
        BusinessDay.objects.filter(bank=env.bank).update(status="closed")
        err(lambda: dep(env, a, "5"), "day_closed", 409)

    def test_over_limit_waits_for_approval_and_posts_nothing(self, ready):
        env, ts, a, _ = ready
        before = JournalEntry.objects.filter(bank=env.bank).count()
        t = dep(env, a, "20000.01")
        assert t.status == "pending_approval" and t.journal_entry_id is None
        assert (
            bal(a) == D("1000.00") and JournalEntry.objects.filter(bank=env.bank).count() == before
        )
        ap = Approval.objects.get(subject_id=t.pk)
        assert (ap.reason, ap.status, ap.requested_by_id) == (
            "limit",
            "pending",
            env.member("teller").pk,
        )
        dep(env, a, "20000.00")  # exactly at the limit posts immediately
        assert bal(a) == D("21000.00")


@pytest.mark.django_db
class TestWithdrawal:
    def test_posts_and_moves(self, ready):
        env, ts, a, _ = ready
        cash = till_cash(ts)
        t = wd(env, a, "400")
        assert t.status == "posted" and bal(a) == D("600.00") and till_cash(ts) == cash - 400
        balanced(t.journal_entry)
        dr = t.journal_entry.lines.get(debit__gt=0)
        assert dr.gl_account.code == "2110" and dr.account_id == a.pk

    def test_insufficient_account_balance(self, ready):
        env, _, a, _ = ready
        err(lambda: wd(env, a, "1000.01"), "insufficient_balance", 409)
        assert bal(a) == D("1000.00")

    def test_insufficient_till_cash(self, env):
        open_till(env, usd="100")
        a = mk_account(env)
        dep(env, a, "500")  # till now 600
        ts2 = open_till(env, "teller2", usd="", code="T2")
        err(lambda: wd(env, a, "50", key="teller2"), "insufficient_cash", 409)
        assert till_cash(ts2) == 0 and bal(a) == D("500.00")

    def test_permission_denied(self, ready):
        env, _, a, _ = ready
        for key in ("cso", "manager"):
            with pytest.raises(PermissionDenied):
                wd(env, a, "5", key=key)


@pytest.mark.django_db
class TestLimitApproval:
    def pending(self, env, a, amount="6000"):
        dep(env, a, "10000")
        t = wd(env, a, amount)
        assert t.status == "pending_approval"
        return t, Approval.objects.get(subject_id=t.pk)

    def test_seeded_limit_rules(self, env):
        rules = {
            (r.role, r.txn_type, r.currency): r.max_amount
            for r in LimitRule.objects.filter(bank=env.bank)
        }
        assert len(rules) == 10
        assert rules[("teller", "cash_withdrawal", "USD")] == D("5000.00")
        assert rules[("teller", "cash_deposit", "SOS")] == D("500000000.00")
        assert rules[("cso", "transfer", "USD")] == D("10000.00")
        assert rules[("teller", "transfer", "SOS")] == D("250000000.00")

    def test_approve_posts_and_audits(self, ready):
        env, ts, a, _ = ready
        t, ap = self.pending(env, a)
        assert bal(a) == D("11000.00")
        res = approvals.approve(env.member("manager"), ap.pk, "ok")
        t = Transaction.objects.get(pk=t.pk)
        assert res.status == "approved" and res.decided_by_id == env.member("manager").pk
        assert t.status == "posted" and bal(a) == D("5000.00")
        balanced(t.journal_entry)
        assert t.journal_entry.posted_by_id == env.member("manager").pk
        assert AuditLog.objects.filter(action="approval.approved", entity_id=str(t.pk)).exists()
        err(lambda: approvals.approve(env.member("manager"), ap.pk), "already_decided", 409)
        err(lambda: approvals.reject(env.member("manager"), ap.pk, "late"), "already_decided")

    def test_reject_posts_nothing(self, ready):
        env, ts, a, _ = ready
        t, ap = self.pending(env, a)
        entries = JournalEntry.objects.filter(bank=env.bank).count()
        err(lambda: approvals.reject(env.member("manager"), ap.pk, " "), status=400)
        approvals.reject(env.member("manager"), ap.pk, "too risky")
        t = Transaction.objects.get(pk=t.pk)
        assert t.status == "rejected" and t.journal_entry_id is None
        assert (
            bal(a) == D("11000.00")
            and JournalEntry.objects.filter(bank=env.bank).count() == entries
        )
        assert Approval.objects.get(pk=ap.pk).note == "too risky"
        err(lambda: transactions.reverse(env.member("teller"), t.pk), "not_reversible", 409)

    def test_only_manager_decides_and_maker_is_not_checker(self, ready):
        env, _, a, _ = ready
        _, ap = self.pending(env, a)
        for key in ("teller", "cso", "accountant", "vault"):
            with pytest.raises(PermissionDenied):
                approvals.approve(env.member(key), ap.pk)
            with pytest.raises(PermissionDenied):
                approvals.list_approvals(env.member(key))
        Approval.objects.filter(pk=ap.pk).update(requested_by=env.member("manager"))
        with pytest.raises(PermissionDenied):
            approvals.approve(env.member("manager"), ap.pk)
        with pytest.raises(PermissionDenied):
            approvals.reject(env.member("manager"), ap.pk, "no")
        assert Approval.objects.get(pk=ap.pk).status == "pending"

    def test_approve_revalidates_balance(self, ready):
        env, _, a, _ = ready
        t, ap = self.pending(env, a, "6000")
        wd(env, a, "5000")
        wd(env, a, "5000")  # drains the account below the pending amount
        err(lambda: approvals.approve(env.member("manager"), ap.pk), "insufficient_balance", 409)
        assert Transaction.objects.get(pk=t.pk).status == "pending_approval"
        assert Approval.objects.get(pk=ap.pk).status == "pending"

    def test_approve_needs_open_till_and_open_day(self, ready):
        env, ts, a, _ = ready
        t, ap = self.pending(env, a)
        TellerSession.objects.filter(pk=ts.pk).update(status=TellerSessionStatus.CLOSED)
        err(lambda: approvals.approve(env.member("manager"), ap.pk), "no_open_till", 409)
        TellerSession.objects.filter(pk=ts.pk).update(status=TellerSessionStatus.OPEN)
        Transaction.objects.filter(pk=t.pk).update(business_date="2000-01-01")
        err(lambda: approvals.approve(env.member("manager"), ap.pk), "other_business_day", 409)

    def test_queue_lists_pending_only(self, ready):
        env, _, a, _ = ready
        t, ap = self.pending(env, a)
        rows = approvals.list_approvals(env.member("manager"))
        assert [r.pk for r in rows] == [ap.pk] and rows[0].transaction.pk == t.pk
        approvals.reject(env.member("manager"), ap.pk, "no")
        assert approvals.list_approvals(env.member("manager")) == []
        assert len(approvals.list_approvals(env.member("manager"), "rejected")) == 1


@pytest.mark.django_db
class TestTransfer:
    def test_teller_transfer_no_cash(self, ready):
        env, ts, a, b = ready
        cash = till_cash(ts)
        t = xfer(env, a, b, "300")
        assert t.status == "posted" and t.counter_account_id == b.pk
        assert bal(a) == D("700.00") and bal(b) == D("300.00") and till_cash(ts) == cash
        balanced(t.journal_entry)
        assert not t.journal_entry.lines.filter(cash_holder_id__isnull=False).exists()

    def test_cso_transfer_needs_no_till(self, ready):
        env, _, a, b = ready
        t = xfer(env, a, b, "100", key="cso")
        assert t.status == "posted" and t.teller_session_id is None
        assert bal(b) == D("100.00")

    def test_teller_without_open_till_cannot_transfer(self, env):
        a, b = mk_account(env), mk_account(env)
        err(lambda: xfer(env, a, b, "1"), "no_open_till", 409)

    def test_rules(self, ready):
        env, _, a, b = ready
        err(lambda: xfer(env, a, a, "5"), "same_account", 400)
        err(lambda: xfer(env, a, b, "1000.01"), "insufficient_balance", 409)
        sos = mk_account(env, "SAV-SOS")
        err(lambda: xfer(env, a, sos, "5"), "currency_mismatch", 400)
        ps.close_account(env.member("cso"), b.pk)
        err(lambda: xfer(env, a, b, "5"), "account_not_active", 409)
        for key in ("manager", "accountant"):
            with pytest.raises(PermissionDenied):
                xfer(env, a, b, "5", key=key)

    def test_over_limit_goes_to_approval_then_posts(self, ready):
        env, _, a, b = ready
        dep(env, a, "20000")
        dep(env, a, "20000")
        t = xfer(env, a, b, "10000.01", key="cso")
        assert t.status == "pending_approval" and bal(b) == 0
        approvals.approve(env.member("manager"), Approval.objects.get(subject_id=t.pk).pk)
        assert bal(b) == D("10000.01")
        balanced(Transaction.objects.get(pk=t.pk).journal_entry)


@pytest.mark.django_db
class TestReversal:
    def test_reverse_deposit(self, ready):
        env, ts, a, _ = ready
        cash = till_cash(ts)
        t = dep(env, a, "200")
        r = transactions.reverse(env.member("teller"), t.pk, "typo")
        assert r.status == "reversed" and bal(a) == D("1000.00") and till_cash(ts) == cash
        rev = Transaction.objects.get(reversal_of=t)
        assert rev.type == "reversal" and rev.status == "posted" and rev.amount == D("200.00")
        assert rev.journal_entry.reversal_of_id == t.journal_entry_id
        balanced(rev.journal_entry)
        swapped = {
            (ln.gl_account.code, ln.debit, ln.credit) for ln in rev.journal_entry.lines.all()
        }
        assert swapped == {("1120", D("0"), D("200")), ("2110", D("200"), D("0"))}
        assert AuditLog.objects.filter(action="txn.reversed", entity_id=str(t.pk)).exists()
        err(lambda: transactions.reverse(env.member("teller"), t.pk), "already_reversed", 409)
        err(lambda: transactions.reverse(env.member("teller"), rev.pk), "not_reversible", 409)

    def test_reverse_withdrawal_and_transfer(self, ready):
        env, _, a, b = ready
        w = wd(env, a, "100")
        transactions.reverse(env.member("teller"), w.pk)
        assert bal(a) == D("1000.00")
        t = xfer(env, a, b, "50")
        transactions.reverse(env.member("teller"), t.pk)
        assert bal(a) == D("1000.00") and bal(b) == 0

    def test_only_creator_may_reverse(self, ready):
        env, _, a, _ = ready
        open_till(env, "teller2", code="T2")
        t = dep(env, a, "5")
        for key in ("teller2", "cso", "manager"):
            with pytest.raises((PermissionDenied, LedgerError)):
                transactions.reverse(env.member(key), t.pk)
        assert Transaction.objects.get(pk=t.pk).status == "posted"

    def test_other_business_day_refused(self, ready):
        env, _, a, _ = ready
        t = dep(env, a, "5")
        Transaction.objects.filter(pk=t.pk).update(business_date="2000-01-01")
        err(lambda: transactions.reverse(env.member("teller"), t.pk), "other_business_day", 409)

    def test_negative_balance_refused(self, ready):
        env, _, a, _ = ready
        t = dep(env, a, "500")
        wd(env, a, "1500")  # customer already took the money out
        err(
            lambda: transactions.reverse(env.member("teller"), t.pk),
            "reversal_negative_balance",
            409,
        )
        assert Transaction.objects.get(pk=t.pk).status == "posted"
        assert not Transaction.objects.filter(reversal_of=t).exists()

    def test_cash_reversal_needs_open_till(self, ready):
        env, ts, a, _ = ready
        t = dep(env, a, "5")
        TellerSession.objects.filter(pk=ts.pk).update(status=TellerSessionStatus.CLOSING)
        err(lambda: transactions.reverse(env.member("teller"), t.pk), "no_open_till", 409)

    def test_pending_cannot_be_reversed(self, ready):
        env, _, a, _ = ready
        t = dep(env, a, "30000")
        err(lambda: transactions.reverse(env.member("teller"), t.pk), "not_reversible", 409)


@pytest.mark.django_db
class TestVisibilityAndIsolation:
    def test_own_visibility_list(self, world):
        env = Env(world, default_visibility="own")
        open_till(env)
        open_till(env, "teller2", code="T2")
        a = mk_account(env)
        t1, t2 = dep(env, a, "10"), dep(env, a, "20", key="teller2")
        mine = {t.pk for t in transactions.list_transactions(env.member("teller"))}
        assert mine == {t1.pk}
        err(lambda: transactions.get_transaction(env.member("teller"), t2.pk), status=404)
        for key in ("manager", "accountant"):
            assert {t.pk for t in transactions.list_transactions(env.member(key))} == {t1.pk, t2.pk}
        for key in ("vault",):
            with pytest.raises(PermissionDenied):
                transactions.list_transactions(env.member(key))

    def test_filters(self, ready):
        env, _, a, b = ready
        xfer(env, a, b, "5")
        m = env.member("manager")
        assert transactions.list_transactions(m, type="transfer").count() == 1
        assert transactions.list_transactions(m, account_id=b.pk).count() == 0
        err(lambda: transactions.list_transactions(m, status="bogus"), status=400)

    def test_cross_bank_and_cross_session(self, ready, world):
        env, _, a, _ = ready
        other = Env(world, "z")
        open_till(other)
        oa = mk_account(other)
        ot = dep(other, oa, "10")
        # my teller cannot touch the other bank's account (not found), and vice versa
        err(lambda: dep(env, oa, "5"), status=404)
        err(lambda: xfer(env, a, oa, "5"), status=404)
        # my manager cannot read / reverse / decide the other bank's rows
        m = env.member("manager")
        assert list(transactions.list_transactions(m)) != []
        assert ot.pk not in {t.pk for t in transactions.list_transactions(m)}
        err(lambda: transactions.get_transaction(m, ot.pk), status=404)
        big = dep(other, oa, "30000")
        ap = Approval.objects.get(subject_id=big.pk)
        err(lambda: approvals.approve(m, ap.pk), status=404)
        err(lambda: approvals.reject(m, ap.pk, "x"), status=404)
        err(lambda: transactions.reverse(env.member("teller"), ot.pk), status=404)
        assert approvals.list_approvals(m) == []
        # HTTP: wrong session id is 403 for a non-member
        c = api(env.user("manager"))
        assert c.get(f"/api/s/{other.session.pk}/transactions").status_code == 403
        assert c.get(f"/api/s/{env.session.pk}/transactions/{ot.pk}").status_code == 404
        assert c.get(f"/api/s/{env.session.pk}/transactions/{ot.pk}/receipt.pdf").status_code == 404


@pytest.mark.django_db
class TestReceiptAndApi:
    def test_words(self):
        assert receipts.number_to_words(0) == "zero"
        assert receipts.number_to_words(21) == "twenty-one"
        assert receipts.number_to_words(1234567) == (
            "one million two hundred thirty-four thousand five hundred sixty-seven"
        )
        assert receipts.amount_in_words(D("105.05"), "USD") == (
            "One hundred five US Dollars and 05/100"
        )

    def test_pdf_for_posted_and_reversed_only(self, ready):
        env, _, a, _ = ready
        t = dep(env, a, "75")
        c = api(env.user("teller"))
        r = c.get(f"/api/s/{env.session.pk}/transactions/{t.pk}/receipt.pdf")
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        transactions.reverse(env.member("teller"), t.pk)
        assert c.get(f"/api/s/{env.session.pk}/transactions/{t.pk}/receipt.pdf").status_code == 200
        big = dep(env, a, "30000")
        r = c.get(f"/api/s/{env.session.pk}/transactions/{big.pk}/receipt.pdf")
        assert r.status_code == 409 and r.json()["code"] == "no_receipt"

    def test_http_flow(self, ready):
        env, _, a, b = ready
        base = f"/api/s/{env.session.pk}"
        teller, manager, cso = (api(env.user(k)) for k in ("teller", "manager", "cso"))
        dep(env, a, "10000")
        body = {"account_id": str(a.pk), "amount": "6000.00", "currency": "USD", **PARTY}
        r = j(teller, "post", f"{base}/transactions/withdrawal", body)
        assert r.status_code == 200 and r.json()["status"] == "pending_approval"
        tid, aid = r.json()["id"], r.json()["approval_id"]
        assert j(cso, "post", f"{base}/transactions/withdrawal", body).status_code == 403
        assert j(teller, "post", f"{base}/approvals/{aid}/approve").status_code == 403
        q = manager.get(f"{base}/approvals").json()
        assert [x["id"] for x in q] == [aid] and q[0]["transaction"]["ref_no"]
        r = j(manager, "post", f"{base}/approvals/{aid}/approve", {"note": "ok"})
        assert r.status_code == 200 and r.json()["status"] == "approved"
        assert teller.get(f"{base}/transactions/{tid}").json()["status"] == "posted"
        r = j(teller, "post", f"{base}/transactions/deposit", {**body, "amount": "10"})
        assert r.status_code == 200
        r = j(
            cso,
            "post",
            f"{base}/transactions/transfer",
            {
                "from_account_id": str(a.pk),
                "to_account_id": str(b.pk),
                "amount": "5",
                "currency": "USD",
            },
        )
        assert r.status_code == 200
        r = j(teller, "post", f"{base}/transactions/{r.json()['id']}/reverse")
        assert r.status_code == 403  # created by the cso, not this teller
        listing = manager.get(f"{base}/transactions").json()
        assert listing["count"] >= 4
        # instructors never post
        r = j(api(env.world["ia"]), "post", f"{base}/transactions/deposit", body)
        assert r.status_code == 403
        lab.archive_session(env.world["ia"], env.session.pk)
        assert j(teller, "post", f"{base}/transactions/deposit", body).status_code == 409
        assert teller.get(f"{base}/transactions").status_code == 200
