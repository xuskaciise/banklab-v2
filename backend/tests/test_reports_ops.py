# ruff: noqa: F811
"""1.12 Reports: teller cash, branch daily, transaction journal (+ shared PDF/XLSX rendering)."""

from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from apps.banking import transactions
from apps.banking.models import CashPosition, Transaction
from apps.lab.models import Bank
from apps.reports import pdf as report_pdf
from apps.reports.doc import Column, Report, Section
from tests.test_cash import add_person
from tests.test_customers import Env, _media  # noqa: F401
from tests.test_lab import _reset_rbac, api, world  # noqa: F401
from tests.test_transactions import dep, env, mk_account, open_till, wd, xfer  # noqa: F401

D = Decimal


@pytest.fixture
def ready(env):
    """Teller (T1, float 50,000 USD) posted a 1,000 deposit; teller2 (T2, 100 USD) one of 10."""
    ts = open_till(env)
    ts2 = open_till(env, "teller2", usd="100", code="T2")
    a = mk_account(env)
    b = mk_account(env)
    dep(env, a, "1000")
    dep(env, b, "10", key="teller2")
    return env, ts, ts2, a, b


def get(env, key, slug, ext="", **params):
    return api(env.user(key)).get(f"/api/s/{env.session.pk}/reports/{slug}{ext}", params)


def rows_of(body, title):
    return next(s for s in body["sections"] if s["title"].startswith(title))["rows"]


@pytest.mark.django_db
class TestTellerCash:
    def test_expected_matches_till(self, ready):
        env, ts, _, a, b = ready
        wd(env, a, "200")
        xfer(env, a, b, "50")
        r = get(env, "teller", "teller-cash", teller_session_id=str(ts.pk))
        assert r.status_code == 200, r.content
        body = r.json()
        moves = {x["item"]: x for x in rows_of(body, "Cash movements - USD")}
        assert moves["Cash deposit"]["count"] == 1 and moves["Cash deposit"]["cash_in"] == "1000.00"
        assert moves["Cash withdrawal"]["cash_out"] == "200.00"
        assert moves["Total"]["cash_in"] == "1000.00"
        pos = {x["item"]: x["amount"] for x in rows_of(body, "Cash position - USD")}
        on_hand = CashPosition.objects.get(holder_id=ts.pk, currency="USD").balance
        assert on_hand == D("50800.00")
        assert pos["Opening cash (float from vault)"] == "50000.00"
        assert pos["Expected closing cash"] == str(on_hand) == pos["Cash on hand now"]

    def test_own_only_and_permissions(self, ready):
        env, ts, ts2, _, _ = ready
        mine = {"teller_session_id": str(ts.pk)}
        assert get(env, "teller", "teller-cash", **mine).status_code == 200
        assert get(env, "teller2", "teller-cash", **mine).status_code == 404
        assert get(env, "manager", "teller-cash", **mine).status_code == 200
        assert get(env, "accountant", "teller-cash", **mine).status_code == 200
        assert get(env, "vault", "teller-cash", **mine).status_code == 403
        r = get(env, "manager", "teller-cash", teller_session_id=str(ts2.pk))
        assert r.status_code == 200

    def test_cross_bank_and_cross_session(self, world):
        env = Env(world, "a", structure="per_group", default_visibility="all")
        ts = open_till(env)
        bank2 = Bank.objects.get(session=env.session, group_no=2)
        mgr2 = add_person(world, env.session, bank2, "mgr2r", "manager")
        p = {"teller_session_id": str(ts.pk)}
        base = f"/api/s/{env.session.pk}/reports/teller-cash"
        assert api(mgr2[0]).get(base, p).status_code == 404
        other = Env(world, "q")
        assert api(other.user("manager")).get(base, p).status_code == 403

    def test_pdf_and_xlsx(self, ready):
        env, ts, *_ = ready
        p = {"teller_session_id": str(ts.pk)}
        assert get(env, "manager", "teller-cash", ".pdf", **p).content.startswith(b"%PDF")
        x = get(env, "manager", "teller-cash", ".xlsx", **p)
        ws = load_workbook(BytesIO(x.content)).active
        row = next(r for r in ws.iter_rows(values_only=True) if r[0] == "Expected closing cash")
        assert D(str(row[1])) == D("51000.00")


@pytest.mark.django_db
class TestBranchDaily:
    def test_totals_and_positions(self, ready):
        env, ts, ts2, a, b = ready
        body = get(env, "manager", "branch-daily").json()
        by_type = rows_of(body, "Transactions by type")
        total = next(r for r in by_type if r["item"] == "Total posted" and r["currency"] == "USD")
        posted = Transaction.objects.filter(bank=env.bank, status="posted", type="cash_deposit")
        assert total["count"] == posted.count() == 2
        assert D(total["amount"]) == D("1010.00")
        tellers = rows_of(body, "Teller positions")
        t1 = next(r for r in tellers if r["till"] == "T1" and r["currency"] == "USD")
        assert t1["cash"] == "51000.00"
        vault = rows_of(body, "Vault position")
        assert {r["currency"] for r in vault} == {"USD", "SOS"}

    def test_own_only_has_no_vault_and_own_figures(self, ready):
        env, *_ = ready
        body = get(env, "teller2", "branch-daily").json()
        assert not any(s["title"].startswith("Vault") for s in body["sections"])
        total = next(
            r for r in rows_of(body, "Transactions by type") if r["item"] == "Total posted"
        )
        assert total["count"] == 1 and total["amount"] == "10.00"
        assert [r["till"] for r in rows_of(body, "Teller positions")] == ["T2", "T2"]

    def test_permissions_and_formats(self, ready):
        env, *_ = ready
        assert get(env, "vault", "branch-daily").status_code == 403
        assert get(env, "accountant", "branch-daily").status_code == 200
        assert get(env, "manager", "branch-daily", ".pdf").content.startswith(b"%PDF")
        x = get(env, "manager", "branch-daily", ".xlsx")
        assert load_workbook(BytesIO(x.content)).active.max_row > 5


@pytest.mark.django_db
class TestJournal:
    def test_own_only_visibility(self, ready):
        env, *_ = ready
        mine = rows_of(get(env, "teller", "transaction-journal").json(), "Transactions")
        assert [r["amount"] for r in mine if not r["style"]] == ["1000.00"]
        allr = rows_of(get(env, "manager", "transaction-journal").json(), "Transactions")
        assert sorted(r["amount"] for r in allr if not r["style"]) == ["10.00", "1000.00"]
        total = next(r for r in allr if r["style"] == "total")
        assert total["amount"] == "1010.00" and total["currency"] == "USD"

    def test_filters(self, ready):
        env, ts, ts2, a, b = ready
        t2 = env.member("teller2")
        body = get(env, "manager", "transaction-journal", teller_id=str(t2.pk)).json()
        assert [r["amount"] for r in rows_of(body, "Transactions") if not r["style"]] == ["10.00"]
        body = get(env, "manager", "transaction-journal", type="transfer").json()
        assert rows_of(body, "Transactions") == []
        assert get(env, "manager", "transaction-journal", type="bogus").status_code == 400
        assert get(env, "manager", "transaction-journal", status="bogus").status_code == 400
        assert (
            get(env, "manager", "transaction-journal", currency="SOS").json()["summary"][0]["value"]
            == "0"
        )
        # a teller cannot read another teller's rows by filtering on their id
        own = get(env, "teller", "transaction-journal", teller_id=str(t2.pk)).json()
        assert rows_of(own, "Transactions") == []

    def test_teller_id_cannot_cross_bank_or_user(self, ready, world):
        env, *_ = ready
        other = Env(world, "tb")
        foreign = str(other.member("teller").pk)
        body = get(env, "manager", "transaction-journal", teller_id=foreign).json()
        assert rows_of(body, "Transactions") == []
        mine = get(env, "teller2", "transaction-journal", teller_id=str(env.member("teller").pk))
        assert rows_of(mine.json(), "Transactions") == []

    def test_reversed_is_listed_and_not_totalled(self, ready):
        env, ts, _, a, _ = ready
        t = dep(env, a, "75")
        transactions.reverse(env.member("teller"), t.pk, "wrong amount")
        rows = rows_of(get(env, "manager", "transaction-journal").json(), "Transactions")
        statuses = [r["status"] for r in rows if not r["style"]]
        assert "Reversed" in statuses
        total = next(r for r in rows if r["style"] == "total")
        assert total["amount"] == "1010.00"

    def test_permissions_and_isolation(self, ready, world):
        env, *_ = ready
        assert get(env, "vault", "transaction-journal").status_code == 403
        other = Env(world, "w")
        r = api(other.user("manager")).get(f"/api/s/{env.session.pk}/reports/transaction-journal")
        assert r.status_code == 403
        base = f"/api/sessions/{env.session.pk}/banks/{env.bank.pk}/reports/transaction-journal"
        assert len(rows_of(api(world["ia"]).get(base).json(), "Transactions")) == 3
        assert api(world["ib"]).get(base).status_code in (403, 404)

    def test_pdf_and_xlsx(self, ready):
        env, *_ = ready
        pdf = get(env, "manager", "transaction-journal", ".pdf")
        assert pdf.content.startswith(b"%PDF") and pdf["Content-Disposition"].startswith("inline")
        x = get(env, "manager", "transaction-journal", ".xlsx")
        ws = load_workbook(BytesIO(x.content)).active
        total = next(r for r in ws.iter_rows(values_only=True) if "Total posted USD" in r)
        assert D(str(total[8])) == D("1010.00")


def test_pdf_repeats_header_over_many_pages():
    rows = [{"a": f"row {i}", "n": D(i)} for i in range(300)]
    report = Report(
        slug="x",
        title="Long",
        bank_name="Test Bank",
        period="p",
        sections=[Section("T", [Column("a", "A"), Column("n", "N", "money")], rows)],
    )
    data = report_pdf.render_report(report)
    assert data.startswith(b"%PDF")
    assert data.count(b"/Type /Page\n") > 3 or data.count(b"/Type /Page") > 4
