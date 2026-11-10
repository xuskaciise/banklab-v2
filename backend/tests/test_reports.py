# ruff: noqa: F811
"""1.12 Reports: Trial Balance, Balance Sheet, Income Statement, account statement, GL ledger."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from apps.banking.models import Vault
from apps.lab import services as lab
from apps.lab.models import Bank
from apps.ledger import services as ledger
from apps.ledger.models import GLAccount
from tests.test_cash import add_person
from tests.test_customers import Env, _media  # noqa: F401
from tests.test_lab import _reset_rbac, api, world  # noqa: F401
from tests.test_transactions import dep, env, mk_account, open_till, wd  # noqa: F401

D = Decimal


@pytest.fixture
def ready(env):
    ts = open_till(env)
    a = mk_account(env)
    dep(env, a, "1000")
    return env, ts, a


def url(env, slug, ext=""):
    return f"/api/s/{env.session.pk}/reports/{slug}{ext}"


def get(env, key, slug, ext="", **params):
    return api(env.user(key)).get(url(env, slug, ext), params)


def section(body, prefix):
    return next(s for s in body["sections"] if s["title"].startswith(prefix))


def summary(body):
    return {s["label"]: s["value"] for s in body["summary"]}


def gl(env, tag):
    return GLAccount.objects.get(bank=env.bank, system_tag=tag)


def post_pl(env, income="100.00", expense="30.00"):
    """Income 4xxx (Dr vault / Cr income) and expense 5xxx (Dr expense / Cr vault), USD."""
    vault = Vault.objects.get(bank=env.bank)
    inc = gl(env, "CASH_OVER")
    exp = gl(env, "CASH_SHORT")
    held = {"cash_holder_type": "vault", "cash_holder_id": vault.pk}
    cash = gl(env, "CASH_VAULT")
    ledger.post_entry(
        env.bank,
        [
            ledger.LineSpec(cash, debit=D(income), **held),
            ledger.LineSpec(inc, credit=D(income)),
        ],
        currency="USD",
        source_type="test",
        description="income",
    )
    ledger.post_entry(
        env.bank,
        [
            ledger.LineSpec(exp, debit=D(expense)),
            ledger.LineSpec(cash, credit=D(expense), **held),
        ],
        currency="USD",
        source_type="test",
        description="expense",
    )


@pytest.mark.django_db
class TestFinancial:
    def test_trial_balance_balanced(self, ready):
        env, _, _ = ready
        post_pl(env)
        r = get(env, "accountant", "trial-balance")
        assert r.status_code == 200, r.content
        body = r.json()
        for cur in ("USD", "SOS"):
            total = section(body, f"Trial Balance - {cur}")["rows"][-1]
            assert total["style"] == "total" and total["debit"] == total["credit"]
        usd = section(body, "Trial Balance - USD")
        assert usd["rows"][-1]["debit"] != "0.00"
        assert summary(body)["USD difference"] == "0.00"
        codes = {row["code"] for row in usd["rows"][:-1]}
        assert codes == set(
            GLAccount.objects.filter(bank=env.bank, postable=True).values_list("code", flat=True)
        )

    def test_trial_balance_as_of_and_currency(self, ready):
        env, _, _ = ready
        day = env.bank.business_days.get().date
        before = get(env, "manager", "trial-balance", as_of=str(day - timedelta(days=1))).json()
        assert section(before, "Trial Balance - USD")["rows"][-1]["debit"] == "0.00"
        one = get(env, "manager", "trial-balance", currency="USD").json()
        assert [s["currency"] for s in one["sections"]] == ["USD"]
        assert get(env, "manager", "trial-balance", currency="EUR").status_code == 400

    def test_balance_sheet_equation_and_period_result(self, ready):
        env, _, _ = ready
        post_pl(env, "100.00", "30.00")
        body = get(env, "accountant", "balance-sheet").json()
        usd = section(body, "Balance Sheet - USD")["rows"]
        by_name = {r["name"]: r["amount"] for r in usd}
        assert by_name["Current period result (Income - Expenses)"] == "70.00"
        assert by_name["Total assets"] == by_name["Total liabilities + equity + result"]
        s = summary(body)
        assert s["USD difference"] == "0.00" and s["SOS difference"] == "0.00"

    def test_income_statement_net(self, ready):
        env, _, _ = ready
        post_pl(env, "100.00", "30.00")
        body = get(env, "accountant", "income-statement").json()
        usd = {r["name"]: r["amount"] for r in section(body, "Income Statement - USD")["rows"]}
        assert usd["Total income"] == "100.00" and usd["Total expenses"] == "30.00"
        assert usd["Net income"] == "70.00"
        assert summary(body)["SOS net income"] == "0.00"
        day = env.bank.business_days.get().date
        later = get(
            env, "accountant", "income-statement", date_from=str(day + timedelta(days=1)),
            date_to=str(day + timedelta(days=2)),
        ).json()
        assert summary(later)["USD net income"] == "0.00"
        bad = get(env, "accountant", "income-statement", date_from="2030-02-01", date_to="2030-01-01")
        assert bad.status_code == 400

    def test_permissions(self, ready):
        env, _, _ = ready
        for key in ("teller", "cso", "vault"):
            for slug in ("trial-balance", "balance-sheet", "income-statement"):
                assert get(env, key, slug).status_code == 403, (key, slug)
        assert get(env, "manager", "trial-balance").status_code == 200
        assert get(env, "cso", "gl-ledger", gl_account_id=str(gl(env, "CASH_VAULT").pk), currency="USD").status_code == 403

    def test_isolation(self, ready, world):
        env, _, _ = ready
        other = Env(world, "z")
        assert api(other.user("accountant")).get(url(env, "trial-balance")).status_code == 403

    def test_instructor_staff_routes(self, ready, world):
        env, _, _ = ready
        base = f"/api/sessions/{env.session.pk}/banks/{env.bank.pk}/reports/trial-balance"
        assert api(world["ia"]).get(base).status_code == 200
        assert api(world["ib"]).get(base).status_code in (403, 404)
        assert api(env.user("accountant")).get(base).status_code in (403, 404)
        pdf = api(world["ia"]).get(base + ".pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    def test_archived_session_stays_readable(self, ready, world):
        env, _, _ = ready
        lab.archive_session(world["ia"], env.session.pk)
        assert get(env, "accountant", "trial-balance").status_code == 200

    def test_pdf_and_xlsx(self, ready):
        env, _, _ = ready
        post_pl(env)
        pdf = get(env, "accountant", "trial-balance", ".pdf")
        assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
        assert pdf["Content-Disposition"].startswith("inline")
        for slug in ("balance-sheet", "income-statement"):
            assert get(env, "manager", slug, ".pdf").content.startswith(b"%PDF")
        x = get(env, "accountant", "trial-balance", ".xlsx")
        assert x["Content-Disposition"].startswith("attachment")
        ws = load_workbook(BytesIO(x.content)).active
        totals = [row for row in ws.iter_rows(values_only=True) if row[1] == "Total"]
        assert len(totals) == 2 and all(t[2] == t[3] for t in totals)
        assert any(t[2] and t[2] > 0 for t in totals)
        assert ws.freeze_panes is not None
        header = next(r for r in ws.iter_rows() if r[0].value == "Code")
        assert header[0].font.bold
        money_cell = next(
            c for r in ws.iter_rows() for c in r if c.value is not None and c.column == 3
            and isinstance(c.value, (int, float, Decimal)) and c.row > header[0].row
        )
        assert money_cell.number_format == "#,##0.00"


@pytest.mark.django_db
class TestStatement:
    def test_opening_plus_lines_equals_closing(self, ready):
        env, _, a = ready
        dep(env, a, "250.50")
        wd(env, a, "100")
        day = env.bank.business_days.get().date
        body = get(env, "cso", "account-statement", account_id=str(a.pk),
                   date_from=str(day), date_to=str(day)).json()
        sec = body["sections"][0]
        rows = sec["rows"]
        assert rows[0]["description"] == "Opening balance" and rows[0]["balance"] == "0.00"
        lines = rows[1:-1]
        assert len(lines) == 3
        credits = sum(D(r["credit"]) for r in lines if r["credit"])
        debits = sum(D(r["debit"]) for r in lines if r["debit"])
        closing = rows[-1]
        assert D(rows[0]["balance"]) + credits - debits == D(closing["balance"]) == D("1150.50")
        assert D(closing["credit"]) == credits and D(closing["debit"]) == debits
        assert lines[-1]["balance"] == "1150.50"
        assert lines[0]["ref"].startswith("B00-")
        assert summary(body)["Closing balance"] == "1150.50"

    def test_opening_balance_carries_forward(self, ready):
        env, _, a = ready
        day = env.bank.business_days.get().date
        nxt = day + timedelta(days=1)
        body = get(env, "cso", "account-statement", account_id=str(a.pk),
                   date_from=str(nxt), date_to=str(nxt)).json()
        s = summary(body)
        assert s["Opening balance"] == s["Closing balance"] == "1000.00"
        assert len(body["sections"][0]["rows"]) == 2

    def test_permission_and_visibility(self, ready):
        env, _, a = ready
        assert get(env, "vault", "account-statement", account_id=str(a.pk)).status_code == 403
        assert get(env, "manager", "account-statement", account_id=str(a.pk)).status_code == 200
        assert get(env, "cso", "account-statement").status_code == 422

    def test_cross_bank_and_cross_session(self, world):
        env = Env(world, "a", structure="per_group", default_visibility="all")
        a = mk_account(env)
        bank2 = Bank.objects.get(session=env.session, group_no=2)
        acc2 = add_person(world, env.session, bank2, "acc2r", "accountant")
        client = api(acc2[0])
        base = f"/api/s/{env.session.pk}/reports"
        assert client.get(f"{base}/account-statement", {"account_id": str(a.pk)}).status_code == 404
        gl_id = GLAccount.objects.filter(bank=env.bank, postable=True).first().pk
        r = client.get(f"{base}/gl-ledger", {"gl_account_id": str(gl_id), "currency": "USD"})
        assert r.status_code == 404
        other = Env(world, "y")
        r = api(other.user("manager")).get(url(env, "account-statement"), {"account_id": str(a.pk)})
        assert r.status_code == 403

    def test_pdf_and_xlsx(self, ready):
        env, _, a = ready
        p = {"account_id": str(a.pk)}
        assert get(env, "cso", "account-statement", ".pdf", **p).content.startswith(b"%PDF")
        x = get(env, "cso", "account-statement", ".xlsx", **p)
        ws = load_workbook(BytesIO(x.content)).active
        closing = [r for r in ws.iter_rows(values_only=True) if "Closing balance" in r][-1]
        assert D(str(closing[5])) == D("1000.00")


@pytest.mark.django_db
class TestGlLedger:
    def test_running_balance_matches_gl_balance(self, ready):
        env, _, a = ready
        dep(env, a, "50")
        acc = gl(env, "DEP_SAVINGS")
        body = get(env, "accountant", "gl-ledger", gl_account_id=str(acc.pk), currency="USD").json()
        rows = body["sections"][0]["rows"]
        assert rows[0]["balance"] == "0.00"
        assert rows[-1]["balance"] == "1050.00"
        assert len(rows) == 4  # opening, 2 lines, closing
        from apps.ledger.models import GLBalance

        assert GLBalance.objects.get(gl_account=acc, currency="USD").balance == D("1050.00")

    def test_header_account_includes_children_and_validation(self, ready):
        env, _, _ = ready
        parent = GLAccount.objects.filter(bank=env.bank, postable=False, children__isnull=False)
        parent = parent.filter(type="liability").first()
        r = get(env, "accountant", "gl-ledger", gl_account_id=str(parent.pk), currency="USD")
        assert r.status_code == 200
        assert get(env, "accountant", "gl-ledger", gl_account_id=str(parent.pk),
                   currency="XXX").status_code == 400
        assert get(env, "accountant", "gl-ledger", ".xlsx", gl_account_id=str(parent.pk),
                   currency="USD").status_code == 200
        assert get(env, "accountant", "gl-ledger", ".pdf", gl_account_id=str(parent.pk),
                   currency="USD").content.startswith(b"%PDF")


@pytest.mark.django_db
def test_statement_own_only_is_strict_404(world):
    env = Env(world, "o", default_visibility="own")
    a = mk_account(env, key="cso")  # created by cso, not a seed account
    p = {"account_id": str(a.pk)}
    assert get(env, "cso", "account-statement", **p).status_code == 200
    assert get(env, "cso2", "account-statement", **p).status_code == 404
    assert get(env, "manager", "account-statement", **p).status_code == 200


def test_xlsx_neutralises_formulas():
    from apps.reports.doc import Column, Report, Section
    from apps.reports.xlsx import render_xlsx

    evil = ["=1+1", "+SUM(A1)", "-2+3", "@cmd", "\tx", "plain"]
    report = Report(
        slug="x", title="T", bank_name="B",
        sections=[Section("S", [Column("a", "A")], [{"a": v} for v in evil])],
    )
    ws = load_workbook(BytesIO(render_xlsx(report))).active
    vals = [r[0] for r in ws.iter_rows(values_only=True) if r[0] and r[0] in {"'" + e for e in evil[:5]} | {"plain"}]
    assert vals == ["'" + e for e in evil[:5]] + ["plain"]
    assert all(c.data_type != "f" for row in ws.iter_rows() for c in row)
