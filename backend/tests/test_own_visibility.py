# ruff: noqa: F811
"""1.15 Security: bank-wide views honour "own" visibility (exam answer-leak fix)."""

import pytest

from apps.ledger.models import GLAccount, JournalEntry
from tests.test_customers import Env, _media  # noqa: F401
from tests.test_exams import (  # noqa: F401
    BAL,
    deposit_own,
    mk_exam,
    open_till,
    start,
)
from tests.test_lab import _reset_rbac, api, world  # noqa: F401
from tests.test_transactions import dep, mk_account
from tests.test_transactions import open_till as _open_till


@pytest.fixture
def exam(world):
    env = Env(world, "x", kind="exam")
    open_till(env)
    open_till(env, key="teller2", code="T2")
    mk_exam(env, tasks=[BAL])
    start(env, "teller")
    start(env, "teller2")
    deposit_own(env, "teller")
    deposit_own(env, "teller2")
    return env


def get(env, key, path):
    return api(env.user(key)).get(f"/api/s/{env.session.pk}{path}")


@pytest.mark.django_db
class TestExamOwnVisibility:
    def test_accountant_cannot_read_students_journal(self, exam):
        assert JournalEntry.objects.filter(bank=exam.bank).count() >= 2
        r = get(exam, "accountant", "/journal")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_direct_entry_fetch_is_404(self, exam):
        any_entry = JournalEntry.objects.filter(bank=exam.bank).first()
        r = get(exam, "accountant", f"/journal/{any_entry.pk}")
        assert r.status_code == 404

    def test_gl_balances_hidden(self, exam):
        r = get(exam, "accountant", "/gl/accounts")
        assert r.status_code == 200
        assert all(
            b["balance"] == "0.00" or float(b["balance"]) == 0
            for row in r.json()
            for b in row["balances"]
        )

    def test_vault_and_eod_denied(self, exam):
        assert get(exam, "vault", "/vault").status_code == 403
        assert get(exam, "manager", "/eod").status_code == 403

    def test_bank_wide_gl_reports_denied(self, exam):
        for name in ("trial-balance", "balance-sheet", "income-statement"):
            assert get(exam, "accountant", f"/reports/{name}").status_code == 403, name
        cash = GLAccount.objects.get(bank=exam.bank, system_tag="CASH_VAULT")
        r = get(exam, "accountant", f"/reports/gl-ledger?gl_account_id={cash.pk}&currency=USD")
        assert r.status_code == 403

    def test_cash_transfers_only_own(self, exam):
        r = get(exam, "vault", "/cash-transfers")
        assert r.status_code == 200 and r.json() == []


@pytest.mark.django_db
class TestPracticeStillSeesAll:
    def test_accountant_sees_all_entries_and_balances(self, world):
        env = Env(world, "pr")
        _open_till(env)
        dep(env, mk_account(env), "10")
        r = get(env, "accountant", "/journal")
        assert r.status_code == 200 and r.json()["count"] >= 1
        gl = get(env, "accountant", "/gl/accounts").json()
        assert any(row["balances"] for row in gl)
        assert get(env, "vault", "/vault").status_code == 200
        assert get(env, "manager", "/eod").status_code == 200
        assert get(env, "accountant", "/reports/trial-balance").status_code == 200
