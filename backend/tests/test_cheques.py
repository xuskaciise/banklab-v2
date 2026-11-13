# ruff: noqa: F811
"""1.10 Cheques: chequebook issue (series), pay once, stop payment, approval, reversal."""

from decimal import Decimal

import pytest
from django.db.models import Sum

from apps.audit.models import AuditLog
from apps.banking import approvals, cheques, receipts, transactions
from apps.banking.models import Approval, Cheque, Transaction
from apps.products.models import Account
from apps.rbac.services import PermissionDenied
from tests.test_customers import Env
from tests.test_lab import api, j, world  # noqa: F401
from tests.test_transactions import (  # noqa: F401
    PARTY,
    bal,
    balanced,
    dep,
    env,
    err,
    mk_account,
    open_till,
)

D = Decimal


@pytest.fixture
def ready(env):
    """Open till for `teller`; a funded current account (cheques allowed) and a savings one."""
    open_till(env)
    cur = mk_account(env, "CUR-USD")
    sav = mk_account(env, "SAV-USD")
    dep(env, cur, "20000")
    return env, cur, sav


def issue(env, acc, leaves=10, key="cso"):
    return cheques.issue_chequebook(env.member(key), acc.pk, leaves)


def cw(env, acc, no, amount="100", key="teller"):
    return transactions.cheque_withdraw(
        env.member(key),
        account_id=acc.pk,
        cheque_no=no,
        amount=D(amount),
        currency=acc.currency,
        **PARTY,
    )


def status(no, env):
    return Cheque.objects.get(bank=env.bank, number=no).status


def approval_of(t):
    return Approval.objects.get(subject_id=t.pk)


@pytest.mark.django_db
class TestIssue:
    def test_series_do_not_overlap(self, ready):
        env, cur, _ = ready
        other = mk_account(env, "CUR-USD")
        b1, b2, b3 = issue(env, cur, 10), issue(env, other, 25), issue(env, cur, 50, "manager")
        assert (b2.first_no, b3.first_no) == (b1.last_no + 1, b2.last_no + 1)
        assert b1.last_no - b1.first_no + 1 == 10 and b1.cheques.count() == 10
        assert b3.cheques.filter(status="issued").count() == 50
        assert AuditLog.objects.filter(action="chequebook.issued", entity_id=str(b1.pk)).exists()

    def test_rejections(self, ready):
        env, cur, sav = ready
        err(lambda: issue(env, sav), "cheques_not_allowed", 400)
        err(lambda: issue(env, cur, 7), "invalid_leaves", 400)
        for key in ("teller", "accountant", "vault"):
            with pytest.raises(PermissionDenied):
                issue(env, cur, key=key)

    def test_inactive_account(self, ready):
        env, cur, _ = ready
        Account.objects.filter(pk=cur.pk).update(status="closed")
        err(lambda: issue(env, cur), "account_not_active", 409)

    def test_cross_session_isolation(self, ready, world):
        env, cur, _ = ready
        book = issue(env, cur)
        env2 = Env(world, "x")
        acc2 = mk_account(env2, "CUR-USD")
        err(lambda: issue(env2, cur), "not_found", 404)  # other bank's account
        assert issue(env2, acc2).first_no == book.first_no  # independent series per bank
        cheque = book.cheques.first()
        err(lambda: cheques.stop_cheque(env2.member("cso"), cheque.pk, "x"), "not_found", 404)
        err(lambda: cheques.list_cheques(env2.member("cso"), cur.pk), "not_found", 404)
        err(lambda: cheques.list_chequebooks(env2.member("cso"), cur.pk), "not_found", 404)


@pytest.mark.django_db
class TestStop:
    def test_stop(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        s = cheques.stop_cheque(env.member("manager"), c.pk, "lost")
        assert (s.status, s.stop_reason) == ("stopped", "lost") and s.stopped_at
        assert AuditLog.objects.filter(action="cheque.stopped", entity_id=str(c.pk)).exists()
        err(lambda: cheques.stop_cheque(env.member("cso"), c.pk, "again"), "cheque_not_issued")
        err(lambda: cw(env, cur, c.number), "cheque_stopped", 409)

    def test_reason_required_and_permission(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        err(lambda: cheques.stop_cheque(env.member("cso"), c.pk, "  "), status=400)
        with pytest.raises(PermissionDenied):
            cheques.stop_cheque(env.member("teller"), c.pk, "lost")
        assert status(c.number, env) == "issued"

    def test_paid_cannot_be_stopped(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        cw(env, cur, c.number)
        err(lambda: cheques.stop_cheque(env.member("cso"), c.pk, "late"), "cheque_not_issued", 409)


@pytest.mark.django_db
class TestWithdrawal:
    def test_pay_once(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        t = cw(env, cur, c.number, "250.00")
        assert t.type == "cheque_withdrawal" and t.status == "posted" and t.cheque_id == c.pk
        assert bal(cur) == D("19750.00")
        c.refresh_from_db()
        assert c.status == "paid" and c.transaction_id == t.pk
        balanced(t.journal_entry)
        codes = {ln.gl_account.code for ln in t.journal_entry.lines.select_related("gl_account")}
        assert codes == {"1120", "2120"}
        err(lambda: cw(env, cur, c.number), "cheque_already_paid", 409)
        assert bal(cur) == D("19750.00")

    def test_invalid_cheques(self, ready):
        env, cur, _ = ready
        other = mk_account(env, "CUR-USD")
        mine = issue(env, cur).cheques.first()
        theirs = issue(env, other).cheques.first()
        err(lambda: cw(env, cur, 999), "not_found", 404)
        err(lambda: cw(env, cur, theirs.number), "cheque_wrong_account", 400)
        err(lambda: cw(env, cur, None), "cheque_required", 400)
        err(lambda: cw(env, cur, mine.number, "0"), "invalid_amount")
        assert Transaction.objects.filter(type="cheque_withdrawal").count() == 0

    def test_permission_and_balance(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        for key in ("cso", "manager"):
            with pytest.raises(PermissionDenied):
                cw(env, cur, c.number, key=key)
        err(lambda: cw(env, cur, c.number, "20001"), "insufficient_balance", 409)
        assert status(c.number, env) == "issued"

    def test_cross_session_cheque_not_found(self, ready, world):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        env2 = Env(world, "y")
        open_till(env2)
        acc2 = mk_account(env2, "CUR-USD")
        dep(env2, acc2, "500")
        err(lambda: cw(env2, acc2, c.number), "not_found", 404)

    def test_over_limit_approve_pays(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        t = cw(env, cur, c.number, "6000")
        assert t.status == "pending_approval" and bal(cur) == D("20000.00")
        c.refresh_from_db()
        assert c.status == "issued" and c.transaction_id == t.pk  # reserved
        err(lambda: cw(env, cur, c.number), "cheque_already_paid", 409)
        err(lambda: cheques.stop_cheque(env.member("cso"), c.pk, "x"), "cheque_in_use", 409)
        approvals.approve(env.member("manager"), approval_of(t).pk)
        c.refresh_from_db()
        assert c.status == "paid" and bal(cur) == D("14000.00")
        balanced(Transaction.objects.get(pk=t.pk).journal_entry)

    def test_over_limit_reject_releases(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        t = cw(env, cur, c.number, "6000")
        approvals.reject(env.member("manager"), approval_of(t).pk, "no")
        c.refresh_from_db()
        assert c.status == "issued" and c.transaction_id is None and bal(cur) == D("20000.00")
        assert Transaction.objects.get(pk=t.pk).cheque_id == c.pk  # history kept
        assert cw(env, cur, c.number, "50").status == "posted"

    def test_reversal_reissues_cheque(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        t = cw(env, cur, c.number, "300")
        transactions.reverse(env.member("teller"), t.pk, "oops")
        c.refresh_from_db()
        assert c.status == "issued" and c.transaction_id is None and bal(cur) == D("20000.00")
        t2 = cw(env, cur, c.number, "300")
        c.refresh_from_db()
        assert c.status == "paid" and c.transaction_id == t2.pk
        live = Transaction.objects.filter(cheque=c, status__in=["posted", "pending_approval"])
        assert live.count() == 1
        agg = t2.journal_entry.lines.aggregate(d=Sum("debit"), c=Sum("credit"))
        assert agg["d"] == agg["c"]

    def test_receipt_renders(self, ready):
        env, cur, _ = ready
        c = issue(env, cur).cheques.first()
        t = transactions.get_transaction(env.member("manager"), cw(env, cur, c.number).pk)
        assert receipts.render_receipt(t).startswith(b"%PDF")


@pytest.mark.django_db
class TestApi:
    def test_flow(self, ready):
        env, cur, sav = ready
        base = f"/api/s/{env.session.pk}"
        cso, teller = api(env.user("cso")), api(env.user("teller"))
        r = j(cso, "post", f"{base}/accounts/{cur.pk}/chequebooks", {"leaves": 10})
        assert r.status_code == 200, r.content
        assert r.json()["last_no"] - r.json()["first_no"] == 9
        books = f"{base}/accounts/{sav.pk}/chequebooks"
        assert j(cso, "post", books, {"leaves": 10}).status_code == 400
        books = f"{base}/accounts/{cur.pk}/chequebooks"
        assert j(teller, "post", books, {"leaves": 10}).status_code == 403
        assert len(cso.get(books).json()) == 1
        lst = cso.get(f"{base}/accounts/{cur.pk}/cheques?status=issued").json()
        assert len(lst) == 10 and lst[0]["status"] == "issued"
        no = lst[0]["number"]
        body = {
            "account_id": str(cur.pk),
            "amount": "75.00",
            "currency": "USD",
            "cheque_no": no,
            **PARTY,
        }
        url = f"{base}/transactions/cheque-withdrawal"
        r = j(teller, "post", url, body)
        assert r.status_code == 200, r.content
        assert r.json()["cheque_no"] == no and r.json()["status"] == "posted"
        assert j(teller, "post", url, body).status_code == 409
        assert j(cso, "post", url, body).status_code == 403
        other = lst[1]["id"]
        assert j(cso, "post", f"{base}/cheques/{other}/stop", {"reason": ""}).status_code == 400
        r = j(cso, "post", f"{base}/cheques/{other}/stop", {"reason": "lost"})
        assert r.status_code == 200 and r.json()["status"] == "stopped"
        assert j(teller, "post", f"{base}/cheques/{other}/stop", {"reason": "x"}).status_code == 403
        assert cso.get(f"{base}/accounts/{cur.pk}").json()["product_allows_cheques"] is True
