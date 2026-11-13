# ruff: noqa: F811, E741
import threading
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from apps.audit.models import AuditLog
from apps.banking import cash
from apps.banking.models import BusinessDay, Vault
from apps.lab import services as lab
from apps.lab.models import Bank, SessionMember, SessionTemplate
from apps.ledger import services as ledger
from apps.ledger.coa import DEFAULT_COA
from apps.ledger.models import (
    CoaTemplate,
    GLAccount,
    GLBalance,
    JournalEntry,
    JournalLine,
    LedgerImmutableError,
)
from apps.ledger.services import LedgerError
from tests.test_lab import (  # noqa: F401  (fixtures)
    _reset_rbac,
    api,
    world,
)
from tests.test_lab import (
    active_session as _active_session,
)
from tests.test_lab import (
    student_session as _student_session,
)

D = Decimal


def active_session(w, name="Lecture 1", **kw):
    """Ledger tests start from empty books: no opening capital (A1 is covered in test_cash)."""
    kw.setdefault("opening_capital_usd", D("0"))
    kw.setdefault("opening_capital_sos", D("0"))
    return _active_session(w, name, **kw)


def student_session(world, role=None, **kw):
    kw.setdefault("opening_capital_usd", D("0"))
    kw.setdefault("opening_capital_sos", D("0"))
    return _student_session(world, role, **kw)


def LineSpec(gl, **kw):  # noqa: N802  (drop-in for ledger.LineSpec that names the cash holder)
    if gl.system_tag == "CASH_VAULT" and "cash_holder_id" not in kw:
        kw["cash_holder_type"] = "vault"
        kw["cash_holder_id"] = Vault.objects.get(bank=gl.bank).pk
    elif gl.system_tag == "CASH_TELLER" and "cash_holder_id" not in kw:
        kw["cash_holder_type"] = "teller_session"
        kw["cash_holder_id"] = uuid.uuid5(gl.bank.pk, "teller")
    return ledger.LineSpec(gl, **kw)


@pytest.fixture(autouse=True)
def _fake_teller_holders(monkeypatch):
    """1.8 registers real teller sessions; here any id counts as an existing teller holder."""
    monkeypatch.setitem(cash._HOLDER_EXISTS, "teller_session", lambda bank, pk: True)


def run_threads(threads):
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "worker thread hung"


def acct(bank, tag):
    return GLAccount.objects.get(bank=bank, system_tag=tag)


def dr(bank, tag, amount):
    return LineSpec(acct(bank, tag), debit=D(amount))


def cr(bank, tag, amount):
    return LineSpec(acct(bank, tag), credit=D(amount))


def bank_of(session):
    return Bank.objects.get(session=session)


def post(bank, lines, currency="USD", **kw):
    kw.setdefault("source_type", "test")
    kw.setdefault("description", "t")
    return ledger.post_entry(bank, lines, currency=currency, **kw)


def fund_vault(bank, amount="100.00", currency="USD"):
    return post(
        bank,
        [dr(bank, "CASH_VAULT", amount), cr(bank, "CAPITAL", amount)],
        currency=currency,
    )


def bal(bank, tag, currency="USD"):
    return GLBalance.objects.get(gl_account=acct(bank, tag), currency=currency).balance


@pytest.fixture
def bank(world):  # noqa: F811
    return bank_of(active_session(world))


@pytest.mark.django_db
class TestChartOfAccounts:
    def test_bank_gets_coa_per_coa_md(self, bank):
        accounts = {a.code: a for a in GLAccount.objects.filter(bank=bank)}
        assert set(accounts) == {row[0] for row in DEFAULT_COA}
        assert len(accounts) == 29
        vault = accounts["1110"]
        assert (vault.system_tag, vault.postable, vault.is_active) == ("CASH_VAULT", True, True)
        assert vault.parent.code == "1100" and vault.parent.parent.code == "1000"
        assert accounts["1000"].postable is False
        assert accounts["2110"].system_tag == "DEP_SAVINGS" and accounts["2110"].is_active
        for code in ("1310", "2130", "2210", "2230", "4100", "5100", "1300", "2200"):
            assert accounts[code].is_active is False
        assert accounts["3200"].allow_negative is True
        assert sum(a.allow_negative for a in accounts.values()) == 1
        assert accounts["4900"].type == "income" and accounts["5900"].type == "expense"

    def test_zero_balances_for_postable_accounts(self, bank):
        postable = GLAccount.objects.filter(bank=bank, postable=True).count()
        rows = GLBalance.objects.filter(bank=bank)
        assert rows.count() == postable * 2
        assert {r.currency for r in rows} == {"USD", "SOS"}
        assert all(r.balance == D("0.00") for r in rows)

    def test_each_bank_has_its_own_copy(self, world):
        s = active_session(world, "Groups", structure="per_group")
        banks = list(Bank.objects.filter(session=s))
        assert len(banks) == 3
        ids = [set(GLAccount.objects.filter(bank=b).values_list("id", flat=True)) for b in banks]
        assert not (ids[0] & ids[1]) and len(ids[0]) == 29

    def test_default_template_seeded_and_helper(self, bank, world):
        inst = world["ia"].institution
        t = ledger.get_default_template(inst)
        assert t.lines.count() == 29
        assert CoaTemplate.objects.filter(institution=inst).count() == 1

    def test_session_template_coa_is_used(self, world):
        inst = world["ia"].institution
        custom = CoaTemplate.objects.create(institution=inst, name="Custom")
        custom.lines.create(
            code="1110", name="Vault X", type="asset", postable=True, system_tag="CASH_VAULT"
        )
        custom.lines.create(
            code="3100", name="Capital X", type="equity", postable=True, system_tag="CAPITAL"
        )
        tmpl = SessionTemplate.objects.create(
            institution=inst,
            lab_class=world["ca"],
            name="T",
            kind="practice",
            structure="single_bank",
            allowed_roles=[],
            default_visibility="all",
            created_by=world["ia"],
            coa_template=custom,
        )
        s = lab.create_session(world["ia"], world["ca"].pk, "Custom session")
        s.template = tmpl
        s.save()
        lab.open_session(world["ia"], s.pk)
        codes = set(GLAccount.objects.filter(bank=bank_of(s)).values_list("code", flat=True))
        assert codes == {"1110", "3100"}


@pytest.mark.django_db
class TestPosting:
    def test_balanced_posting_updates_balances_and_dr_equals_cr(self, bank):
        e = fund_vault(bank, "250.50")
        assert e.entry_no == 1 and e.currency == "USD"
        lines = list(e.lines.all())
        assert sum(l.debit for l in lines) == sum(l.credit for l in lines) == D("250.50")
        assert bal(bank, "CASH_VAULT") == D("250.50")
        assert bal(bank, "CAPITAL") == D("250.50")
        assert bal(bank, "CASH_VAULT", "SOS") == D("0.00")
        assert e.business_date == BusinessDay.objects.get(bank=bank, status="open").date

    def test_normal_sides(self, bank):
        fund_vault(bank, "100.00")
        post(bank, [dr(bank, "CASH_SHORT", "5"), cr(bank, "CASH_VAULT", "5")])
        assert bal(bank, "CASH_SHORT") == D("5.00")  # expense, debit-normal
        assert bal(bank, "CASH_VAULT") == D("95.00")

    def test_entry_numbers_sequential_per_bank(self, world):
        b1 = bank_of(active_session(world, "One"))
        s2 = active_session(world, "Two")
        b2 = bank_of(s2)
        assert [fund_vault(b1).entry_no, fund_vault(b1).entry_no, fund_vault(b2).entry_no] == [
            1,
            2,
            1,
        ]

    @pytest.mark.parametrize(
        ("mutator", "code"),
        [
            ("unbalanced", "unbalanced"),
            ("one_line", "too_few_lines"),
            ("zero", "invalid_line"),
            ("negative", "invalid_amount"),
            ("three_dec", "invalid_amount"),
            ("float", "invalid_amount"),
            ("both_sides", "invalid_line"),
            ("bad_currency", "invalid_currency"),
            ("mixed", "mixed_currency"),
        ],
    )
    def test_invalid_input_rejected(self, bank, mutator, code):
        v, c = acct(bank, "CASH_VAULT"), acct(bank, "CAPITAL")
        currency = "USD"
        lines = [LineSpec(v, debit=D("10")), LineSpec(c, credit=D("10"))]
        if mutator == "unbalanced":
            lines[1] = LineSpec(c, credit=D("9.99"))
        elif mutator == "one_line":
            lines = lines[:1]
        elif mutator == "zero":
            lines[0] = LineSpec(v, debit=D("0"))
        elif mutator == "negative":
            lines = [LineSpec(v, debit=D("-10")), LineSpec(c, credit=D("-10"))]
        elif mutator == "three_dec":
            lines = [LineSpec(v, debit=D("10.001")), LineSpec(c, credit=D("10.001"))]
        elif mutator == "float":
            lines = [LineSpec(v, debit=10.0), LineSpec(c, credit=10.0)]
        elif mutator == "both_sides":
            lines[0] = LineSpec(v, debit=D("10"), credit=D("10"))
        elif mutator == "bad_currency":
            currency = "EUR"
        elif mutator == "mixed":
            lines[1] = LineSpec(c, credit=D("10"), currency="SOS")
        with pytest.raises(LedgerError) as exc:
            ledger.post_entry(bank, lines, currency=currency, source_type="t", description="t")
        assert exc.value.code == code
        assert not JournalEntry.objects.filter(bank=bank).exists()
        assert bal(bank, "CASH_VAULT") == 0

    def test_non_postable_inactive_and_foreign_accounts_rejected(self, world, bank):
        header = GLAccount.objects.get(bank=bank, code="1100")
        inactive = acct(bank, "FIN_QARD")
        for bad in (header, inactive):
            with pytest.raises(LedgerError) as exc:
                post(bank, [LineSpec(bad, debit=D("1")), cr(bank, "CAPITAL", "1")])
            assert exc.value.code == "account_not_postable"
        other = bank_of(active_session(world, "Other"))
        with pytest.raises(LedgerError) as exc:
            post(
                bank, [LineSpec(acct(other, "CASH_VAULT"), debit=D("1")), cr(bank, "CAPITAL", "1")]
            )
        assert exc.value.code == "foreign_account"
        assert bal(other, "CASH_VAULT") == 0

    def test_closed_business_day_rejected(self, bank):
        BusinessDay.objects.filter(bank=bank).update(status="closed")
        with pytest.raises(LedgerError) as exc:
            fund_vault(bank)
        assert (exc.value.code, exc.value.status) == ("day_closed", 409)

    def test_wrong_business_date_rejected(self, bank):
        day = BusinessDay.objects.get(bank=bank, status="open")
        with pytest.raises(LedgerError) as exc:
            post(
                bank,
                [dr(bank, "CASH_VAULT", "1"), cr(bank, "CAPITAL", "1")],
                business_date=day.date + timedelta(days=1),
            )
        assert exc.value.code == "wrong_business_date"

    def test_archived_session_rejected(self, world):
        s = active_session(world)
        bank = bank_of(s)
        lab.archive_session(world["ia"], s.pk)
        with pytest.raises(LedgerError) as exc:
            fund_vault(bank)
        assert (exc.value.code, exc.value.status) == ("session_archived", 409)

    def test_negative_balance_rejected(self, bank):
        fund_vault(bank, "50")
        with pytest.raises(LedgerError) as exc:
            post(bank, [dr(bank, "CASH_TELLER", "60"), cr(bank, "CASH_VAULT", "60")])
        assert exc.value.code == "insufficient_cash"
        assert bal(bank, "CASH_VAULT") == D("50.00")
        assert bal(bank, "CASH_TELLER") == 0
        assert JournalEntry.objects.filter(bank=bank).count() == 1

    def test_gl_negative_guard_on_non_cash_account(self, bank):
        fund_vault(bank, "100")  # CAPITAL (credit-normal equity, no negatives) = 100
        with pytest.raises(LedgerError) as exc:
            post(bank, [dr(bank, "CAPITAL", "150"), cr(bank, "DEP_SAVINGS", "150")])
        assert exc.value.code == "insufficient_balance"
        assert bal(bank, "CAPITAL") == D("100.00") and bal(bank, "DEP_SAVINGS") == 0
        assert JournalEntry.objects.filter(bank=bank).count() == 1

    def test_allow_negative_account(self, bank):
        # Dr Retained Earnings (equity, credit-normal) drives it below zero: allowed.
        post(
            bank, [dr(bank, "RETAINED_EARNINGS", "10"), cr(bank, "CASH_VAULT", "10")]
        ) if False else None
        fund_vault(bank, "10")
        post(bank, [dr(bank, "RETAINED_EARNINGS", "10"), cr(bank, "CAPITAL", "10")])
        assert bal(bank, "RETAINED_EARNINGS") == D("-10.00")

    def test_currencies_are_independent(self, bank):
        fund_vault(bank, "10", "USD")
        fund_vault(bank, "5000", "SOS")
        assert bal(bank, "CASH_VAULT", "USD") == D("10.00")
        assert bal(bank, "CASH_VAULT", "SOS") == D("5000.00")
        with pytest.raises(LedgerError):
            post(
                bank,
                [dr(bank, "CASH_TELLER", "20"), cr(bank, "CASH_VAULT", "20")],
                currency="USD",
            )

    def test_gl_balance_equals_sum_of_lines(self, bank):
        fund_vault(bank, "100")
        fund_vault(bank, "7000", "SOS")
        e = post(bank, [dr(bank, "CASH_TELLER", "30"), cr(bank, "CASH_VAULT", "30")])
        ledger.reverse_entry(bank, e)
        post(bank, [dr(bank, "CASH_SHORT", "1.25"), cr(bank, "CASH_VAULT", "1.25")])
        assert ledger.balances_match_lines(bank)
        assert ledger.recompute_balances(bank)[("1110", "USD")] == D("98.75")

    def test_audit_row_written(self, world, bank):
        member = SessionMember.objects.get(session=bank.session, user=world["studs"][0])
        lab.assign_role(world["ia"], bank.session_id, member.pk, "manager")
        member.refresh_from_db()
        e = fund_vault_by(bank, member)
        row = AuditLog.objects.get(action="ledger.entry_posted", entity_id=str(e.pk))
        assert row.bank_id == bank.pk and row.session_id == bank.session_id
        assert row.actor_id == world["studs"][0].pk and row.actor_role == "manager"
        assert row.after["total"] == "100.00"
        assert e.posted_by_id == member.pk

    def test_system_posting_has_audit_without_actor(self, bank):
        e = fund_vault(bank)
        row = AuditLog.objects.get(action="ledger.entry_posted", entity_id=str(e.pk))
        assert row.actor_id is None and row.institution_id is not None

    def test_actor_must_belong_to_bank_and_have_role(self, world):
        s, member = student_session(world, "manager")
        bank = bank_of(s)
        s2 = active_session(world, "Other")
        stranger = SessionMember.objects.get(session=s2, user=world["studs"][0])
        lab.assign_role(world["ia"], s2.pk, stranger.pk, "manager")
        with pytest.raises(LedgerError) as exc:
            fund_vault_by(bank, stranger)
        assert exc.value.code == "actor_not_in_bank"
        roleless = SessionMember.objects.get(session=s, user=world["studs"][1])
        roleless.bank = bank
        roleless.save()
        with pytest.raises(LedgerError) as exc:
            fund_vault_by(bank, roleless)
        assert exc.value.code == "actor_no_role"
        assert not JournalEntry.objects.filter(bank=bank).exists()
        fund_vault_by(bank, member)


def fund_vault_by(bank, member):
    return post(
        bank,
        [dr(bank, "CASH_VAULT", "100"), cr(bank, "CAPITAL", "100")],
        actor_member=member,
    )


@pytest.mark.django_db
class TestReversal:
    def test_reversal_swaps_lines_and_restores_balances(self, bank):
        fund_vault(bank, "100")
        e = post(bank, [dr(bank, "CASH_TELLER", "40"), cr(bank, "CASH_VAULT", "40")])
        r = ledger.reverse_entry(bank, e)
        assert r.reversal_of_id == e.pk and r.source_type == "reversal" and r.entry_no == 3
        orig = [(l.gl_account_id, l.debit, l.credit) for l in e.lines.all()]
        rev = [(l.gl_account_id, l.credit, l.debit) for l in r.lines.all()]
        assert orig == rev
        assert bal(bank, "CASH_VAULT") == D("100.00") and bal(bank, "CASH_TELLER") == 0
        assert sum(l.debit for l in r.lines.all()) == sum(l.credit for l in r.lines.all())
        assert AuditLog.objects.filter(action="ledger.entry_reversed").count() == 1

    def test_double_reversal_and_reversing_a_reversal_rejected(self, bank):
        e = fund_vault(bank, "100")
        r = ledger.reverse_entry(bank, e)
        with pytest.raises(LedgerError) as exc:
            ledger.reverse_entry(bank, e)
        assert exc.value.code == "already_reversed"
        with pytest.raises(LedgerError) as exc:
            ledger.reverse_entry(bank, r)
        assert exc.value.code == "is_reversal"

    def test_reversal_that_goes_negative_rejected(self, bank):
        a = fund_vault(bank, "100")
        post(bank, [dr(bank, "CASH_TELLER", "100"), cr(bank, "CASH_VAULT", "100")])
        with pytest.raises(LedgerError) as exc:
            ledger.reverse_entry(bank, a)
        assert exc.value.code == "insufficient_cash"
        assert bal(bank, "CASH_VAULT") == 0 and bal(bank, "CAPITAL") == D("100.00")
        assert JournalEntry.objects.filter(bank=bank).count() == 2

    def test_reversal_on_later_business_day_rejected(self, bank):
        e = fund_vault(bank, "100")
        day = BusinessDay.objects.get(bank=bank, status="open")
        day.status = "closed"
        day.save()
        BusinessDay.objects.create(bank=bank, date=day.date + timedelta(days=1))
        with pytest.raises(LedgerError) as exc:
            ledger.reverse_entry(bank, e)
        assert exc.value.code == "other_business_day"

    def test_reversal_in_archived_session_rejected(self, world):
        s = active_session(world)
        bank = bank_of(s)
        e = fund_vault(bank)
        lab.archive_session(world["ia"], s.pk)
        with pytest.raises(LedgerError) as exc:
            ledger.reverse_entry(bank, e)
        assert exc.value.code == "session_archived"


@pytest.mark.django_db
class TestDbProtection:
    def test_model_and_queryset_guards(self, bank):
        e = fund_vault(bank)
        with pytest.raises(LedgerImmutableError):
            e.description = "x"
            e.save()
        with pytest.raises(LedgerImmutableError):
            e.delete()
        with pytest.raises(LedgerImmutableError):
            JournalLine.objects.all().update(debit=1)
        with pytest.raises(LedgerImmutableError):
            JournalEntry.objects.all().delete()

    @pytest.mark.parametrize("table", ["ledger_journalentry", "ledger_journalline"])
    @pytest.mark.parametrize("sql", ["UPDATE {t} SET currency = 'SOS'", "DELETE FROM {t}"])
    def test_raw_update_delete_blocked_by_trigger(self, bank, table, sql):
        fund_vault(bank)
        with pytest.raises(DatabaseError, match="immutable"):
            with transaction.atomic(), connection.cursor() as cur:
                cur.execute(sql.format(t=table))
        assert JournalEntry.objects.filter(bank=bank).count() == 1

    def test_deferred_balance_trigger_catches_raw_unbalanced_insert(self, bank):
        with pytest.raises(DatabaseError, match="not balanced|at least two"):
            with transaction.atomic():
                entry = JournalEntry.objects.create(
                    bank=bank,
                    entry_no=1,
                    business_date="2026-01-01",
                    currency="USD",
                    source_type="raw",
                )
                JournalLine.objects.create(
                    entry=entry,
                    gl_account=acct(bank, "CASH_VAULT"),
                    currency="USD",
                    debit=D("5"),
                    credit=D("0"),
                )
                with connection.cursor() as cur:
                    cur.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_line_check_constraint(self, bank):
        e = fund_vault(bank)
        for debit, credit in ((0, 0), (1, 1), (-1, 0)):
            with pytest.raises(DatabaseError), transaction.atomic():
                JournalLine.objects.create(
                    entry=e,
                    gl_account=acct(bank, "CASH_VAULT"),
                    currency="USD",
                    debit=D(debit),
                    credit=D(credit),
                )

    def test_entry_no_unique_and_single_reversal(self, bank):
        e = fund_vault(bank)
        with pytest.raises(DatabaseError), transaction.atomic():
            JournalEntry.objects.create(
                bank=bank,
                entry_no=1,
                business_date=e.business_date,
                currency="USD",
                source_type="x",
            )
        ledger.reverse_entry(bank, e)
        with pytest.raises(DatabaseError), transaction.atomic():
            JournalEntry.objects.create(
                bank=bank,
                entry_no=99,
                business_date=e.business_date,
                currency="USD",
                source_type="x",
                reversal_of=e,
            )


@pytest.mark.django_db(transaction=True)
def test_concurrent_postings_are_consistent(world):
    bank = bank_of(active_session(world))
    workers, per_worker = 6, 4
    errors = []

    def run():
        try:
            for _ in range(per_worker):
                fund_vault(bank, "100.00")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(workers)]
    run_threads(threads)
    assert not errors
    total = workers * per_worker
    assert bal(bank, "CASH_VAULT") == D("100.00") * total
    nos = sorted(JournalEntry.objects.filter(bank=bank).values_list("entry_no", flat=True))
    assert nos == list(range(1, total + 1))
    assert ledger.balances_match_lines(bank)


@pytest.mark.django_db(transaction=True)
def test_concurrent_withdrawals_never_go_negative(world):
    bank = bank_of(active_session(world))
    fund_vault(bank, "100.00")
    results = []
    errors = []

    def run():
        try:
            post(bank, [dr(bank, "CASH_TELLER", "30"), cr(bank, "CASH_VAULT", "30")])
            results.append("ok")
        except LedgerError as exc:
            results.append(exc.code)
        except Exception as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(6)]
    run_threads(threads)
    assert not errors
    assert results.count("ok") == 3
    assert results.count("insufficient_cash") == 3
    assert bal(bank, "CASH_VAULT") == D("10.00")
    assert ledger.balances_match_lines(bank)


@pytest.mark.django_db(transaction=True)
def test_deferred_trigger_fires_on_commit(bank):
    with pytest.raises(DatabaseError, match="not balanced|at least two"):
        with transaction.atomic():
            entry = JournalEntry.objects.create(
                bank=bank,
                entry_no=1,
                business_date="2026-01-01",
                currency="USD",
                source_type="raw",
            )
            JournalLine.objects.create(
                entry=entry,
                gl_account=acct(bank, "CASH_VAULT"),
                currency="USD",
                debit=D("5"),
                credit=D("0"),
            )
    assert not JournalEntry.objects.filter(bank=bank).exists()


@pytest.mark.django_db
class TestApi:
    def _manager(self, world):
        s, member = student_session(world, "manager")
        bank = bank_of(s)
        fund_vault(bank, "100")
        return s, bank, api(world["studs"][0])

    def test_accounts_requires_permission(self, world):
        s, _ = student_session(world, "teller")
        assert api(world["studs"][0]).get(f"/api/s/{s.pk}/gl/accounts").status_code == 403
        assert api(world["studs"][0]).get(f"/api/s/{s.pk}/journal").status_code == 403

    def test_accounts_tree_with_balances(self, world):
        s, bank, c = self._manager(world)
        r = c.get(f"/api/s/{s.pk}/gl/accounts")
        assert r.status_code == 200
        rows = {a["code"]: a for a in r.json()}
        assert len(rows) == 29
        vault = rows["1110"]["balances"]
        assert {b["currency"]: b["balance"] for b in vault} == {"SOS": "0.00", "USD": "100.00"}
        assert rows["1100"]["balances"] == [] and rows["1110"]["parent_id"] == rows["1100"]["id"]

    def test_journal_list_filters_and_detail(self, world):
        s, bank, c = self._manager(world)
        fund_vault(bank, "5000", "SOS")
        r = c.get(f"/api/s/{s.pk}/journal")
        body = r.json()
        assert body["count"] == 2
        assert [e["entry_no"] for e in body["items"]] == [2, 1]
        usd = c.get(f"/api/s/{s.pk}/journal?currency=USD").json()
        assert usd["count"] == 1 and usd["items"][0]["currency"] == "USD"
        day = body["items"][0]["business_date"]
        assert c.get(f"/api/s/{s.pk}/journal?date_from={day}&date_to={day}").json()["count"] == 2
        assert c.get(f"/api/s/{s.pk}/journal?date_from=2999-01-01").json()["count"] == 0
        detail = c.get(f"/api/s/{s.pk}/journal/{usd['items'][0]['id']}")
        assert detail.status_code == 200
        lines = detail.json()["lines"]
        assert {(l["gl_code"], l["debit"], l["credit"]) for l in lines} == {
            ("1110", "100.00", "0.00"),
            ("3100", "0.00", "100.00"),
        }

    def test_cross_bank_and_cross_session_isolation(self, world):
        s, bank, c = self._manager(world)
        other = bank_of(active_session(world, "Other"))
        foreign = fund_vault(other, "9")
        assert c.get(f"/api/s/{s.pk}/journal/{foreign.pk}").status_code == 404
        listed = c.get(f"/api/s/{s.pk}/journal").json()["items"]
        assert all(e["id"] != str(foreign.pk) for e in listed)
        # another session the student is not a member of
        s3 = lab.create_session(world["ib"], world["cb"].pk, "B session")
        assert c.get(f"/api/s/{s3.pk}/gl/accounts").status_code == 403

    def test_own_bank_only_with_groups(self, world):
        s = active_session(world, "Groups", structure="per_group")
        banks = list(Bank.objects.filter(session=s))
        member = SessionMember.objects.get(session=s, user=world["studs"][0])
        lab.move_member(world["ia"], s.pk, member.pk, banks[0].pk)
        lab.assign_role(world["ia"], s.pk, member.pk, "accountant")
        fund_vault(banks[1], "77")
        c = api(world["studs"][0])
        rows = {a["code"]: a for a in c.get(f"/api/s/{s.pk}/gl/accounts").json()}
        assert {b["balance"] for b in rows["1110"]["balances"]} == {"0.00"}
        assert c.get(f"/api/s/{s.pk}/journal").json()["count"] == 0

    def test_staff_routes_and_scoping(self, world):
        s = active_session(world)
        bank = bank_of(s)
        e = fund_vault(bank, "12")
        c = api(world["ia"])
        base = f"/api/sessions/{s.pk}/banks/{bank.pk}"
        r = c.get(f"{base}/gl/accounts")
        assert r.status_code == 200 and len(r.json()) == 29
        assert c.get(f"{base}/journal").json()["count"] == 1
        assert c.get(f"{base}/journal/{e.pk}").status_code == 200
        # other instructor and students are refused
        assert api(world["ib"]).get(f"{base}/gl/accounts").status_code == 404
        assert api(world["studs"][0]).get(f"{base}/gl/accounts").status_code == 403
        # bank of another session is not reachable through this session
        other = bank_of(active_session(world, "Other"))
        assert c.get(f"/api/sessions/{s.pk}/banks/{other.pk}/gl/accounts").status_code == 404

    def test_unauthenticated(self, world):
        from django.test import Client

        s = active_session(world)
        assert Client().get(f"/api/s/{s.pk}/gl/accounts").status_code in (401, 403)


def _raw_entry(bank, lines, currency="USD"):
    """Insert an entry and lines via the ORM and force the deferred triggers to run."""
    entry = JournalEntry.objects.create(
        bank=bank, entry_no=1, business_date="2026-01-01", currency=currency, source_type="raw"
    )
    for acc, line_currency, debit, credit in lines:
        JournalLine.objects.create(
            entry=entry, gl_account=acc, currency=line_currency, debit=D(debit), credit=D(credit)
        )
    with connection.cursor() as cur:
        cur.execute("SET CONSTRAINTS ALL IMMEDIATE")


@pytest.mark.django_db
class TestRawTriggerGaps:
    def test_line_currency_must_match_entry(self, bank):
        v, c = acct(bank, "CASH_VAULT"), acct(bank, "CAPITAL")
        with pytest.raises(DatabaseError, match="different currency"), transaction.atomic():
            _raw_entry(bank, [(v, "SOS", "5", "0"), (c, "SOS", "0", "5")], currency="USD")

    def test_line_account_must_belong_to_entry_bank(self, world, bank):
        other = bank_of(active_session(world, "Other"))
        v, c = acct(other, "CASH_VAULT"), acct(other, "CAPITAL")
        with pytest.raises(DatabaseError, match="another bank"), transaction.atomic():
            _raw_entry(bank, [(v, "USD", "5", "0"), (c, "USD", "0", "5")])

    def test_entry_needs_two_lines(self, bank):
        with pytest.raises(DatabaseError, match="at least two"), transaction.atomic():
            _raw_entry(bank, [])

    def test_valid_raw_entry_passes(self, bank):
        v, c = acct(bank, "CASH_VAULT"), acct(bank, "CAPITAL")
        _raw_entry(bank, [(v, "USD", "5", "0"), (c, "USD", "0", "5")])


@pytest.mark.django_db
class TestGuards:
    def test_text_lengths_are_domain_errors(self, bank):
        lines = [dr(bank, "CASH_VAULT", "1"), cr(bank, "CAPITAL", "1")]
        with pytest.raises(LedgerError) as exc:
            post(bank, lines, description="x" * 301)
        assert exc.value.code == "text_too_long"
        with pytest.raises(LedgerError) as exc:
            post(bank, lines, source_type="y" * 41)
        assert exc.value.code == "text_too_long"
        e = fund_vault(bank)
        with pytest.raises(LedgerError) as exc:
            ledger.reverse_entry(bank, e, description="x" * 301)
        assert exc.value.code == "text_too_long"

    def test_reverse_entry_of_other_bank_rejected(self, world, bank):
        other = bank_of(active_session(world, "Other"))
        foreign = fund_vault(other, "10")
        with pytest.raises(LedgerError) as exc:
            ledger.reverse_entry(bank, foreign)
        assert exc.value.code == "foreign_entry"
        assert bal(other, "CASH_VAULT") == D("10.00")

    def test_stale_entry_object_is_rechecked(self, bank):
        e = fund_vault(bank, "10")
        stale = JournalEntry.objects.get(pk=e.pk)
        ledger.reverse_entry(bank, e)
        with pytest.raises(LedgerError) as exc:
            ledger.reverse_entry(bank, stale)
        assert exc.value.code == "already_reversed"


@pytest.mark.django_db(transaction=True)
def test_concurrent_double_reversal(world):
    bank = bank_of(active_session(world))
    e = fund_vault(bank, "100.00")
    results = []
    errors = []

    def run():
        try:
            ledger.reverse_entry(bank, JournalEntry.objects.get(pk=e.pk))
            results.append("ok")
        except LedgerError as exc:
            results.append(exc.code)
        except Exception as exc:
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=run) for _ in range(2)]
    run_threads(threads)
    assert not errors
    assert sorted(results) == ["already_reversed", "ok"]
    assert bal(bank, "CASH_VAULT") == 0
    assert JournalEntry.objects.filter(bank=bank).count() == 2


@pytest.mark.django_db(transaction=True)
def test_concurrent_posts_in_two_banks_of_one_session(world):
    s = active_session(world, "Groups", structure="per_group")
    banks = list(Bank.objects.filter(session=s)[:2])
    errors = []

    def run(b):
        try:
            for _ in range(5):
                fund_vault(b, "10.00")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(b,)) for b in banks for _ in range(2)]
    run_threads(threads)
    assert not errors
    for b in banks:
        assert bal(b, "CASH_VAULT") == D("100.00")
        assert ledger.balances_match_lines(b)
