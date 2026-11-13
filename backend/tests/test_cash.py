# ruff: noqa: F811
"""1.5 Branch & Vault: opening capital (A1), cash holders in the ledger, link check,
dual-control vault transfers and the branch/till set-up."""

import threading
import uuid
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction

from apps.audit.models import AuditLog
from apps.banking import cash
from apps.banking import services as banking
from apps.banking.models import (
    Branch,
    BusinessDay,
    CashPosition,
    CashTransfer,
    Denomination,
    TellerSession,
    Till,
    TransferStatus,
    Vault,
)
from apps.lab import services as lab
from apps.lab.models import Bank, RoleAssignment, SessionMember
from apps.ledger import services as ledger
from apps.ledger.models import (
    GLAccount,
    GLBalance,
    JournalEntry,
    JournalLine,
    LedgerImmutableError,
)
from apps.ledger.services import LedgerError, LineSpec
from apps.rbac import services as rbac
from tests.test_lab import (  # noqa: F401  (fixtures)
    _reset_rbac,
    active_session,
    api,
    j,
    world,
)

D = Decimal
CAP_USD, CAP_SOS = D("1000000.00"), D("5000000000.00")


def acct(bank, tag):
    return GLAccount.objects.get(bank=bank, system_tag=tag)


def vault_of(bank):
    return Vault.objects.get(bank=bank)


def position(bank, holder_id, currency="USD"):
    return CashPosition.objects.get(bank=bank, holder_id=holder_id, currency=currency).balance


def gl_balance(bank, tag, currency="USD"):
    return GLBalance.objects.get(gl_account=acct(bank, tag), currency=currency).balance


@pytest.fixture
def teller_holders():
    """An OPEN teller session of the bank's teller (one per bank); returns its id."""
    made: dict[object, uuid.UUID] = {}

    def make(bank):
        if bank.pk in made:
            return made[bank.pk]
        assignment = RoleAssignment.objects.select_related("session_member").get(
            session_member__bank=bank, role="teller", active_to__isnull=True
        )
        branch = Branch.objects.filter(bank=bank).first()
        till = Till.objects.create(bank=bank, branch=branch, code="TT")
        day = BusinessDay.objects.get(bank=bank, status="open")
        ts = TellerSession.objects.create(
            bank=bank,
            till=till,
            teller_member=assignment.session_member,
            business_date=day.date,
            status="open",
        )
        cash.create_position_rows(bank, "teller_session", ts.pk)
        made[bank.pk] = ts.pk
        return ts.pk

    return make


def add_person(world, session, bank, username, role):
    user, _ = lab.add_student(world["ia"], world["ca"].pk, username, username.title(), "0611110000")
    user.must_change_password = False
    user.save(update_fields=["must_change_password"])
    (member,) = lab.add_members(world["ia"], session.pk, [user.pk], bank_id=bank.pk)
    lab.assign_role(world["ia"], session.pk, member.pk, role)
    return user, SessionMember.objects.get(pk=member.pk)


class Env:
    """One bank with a teller, a custodian, a manager and a cso."""

    def __init__(self, world, suffix="", **kw):
        self.world = world
        self.session = active_session(world, f"Cash{suffix}", **kw)
        self.bank = Bank.objects.filter(session=self.session).order_by("group_no").first()
        self.people = {}
        for role in ("teller", "vault_custodian", "manager", "cso"):
            self.people[role] = add_person(
                world, self.session, self.bank, f"{role[:4]}{suffix}{uuid.uuid4().hex[:4]}", role
            )
        self.vault = vault_of(self.bank)

    def user(self, role):
        return self.people[role][0]

    def member(self, role):
        return self.people[role][1]


@pytest.fixture
def env(world):
    return Env(world)


def request_transfer(env, teller_id, amount="100.00", currency="USD", role="teller"):
    return banking.request_vault_transfer(
        env.member(role),
        from_type="vault",
        from_id=env.vault.pk,
        to_type="teller_session",
        to_id=teller_id,
        currency=currency,
        amount=D(amount),
    )


def full_approval(env, transfer):
    banking.approve_custodian(env.member("vault_custodian"), transfer.pk)
    return banking.approve_manager(env.member("manager"), transfer.pk)


# ---------------------------------------------------------------------------- A1


@pytest.mark.django_db
class TestOpeningCapital:
    def test_a1_posted_balanced_and_positions_equal_gl(self, env):
        bank = env.bank
        assert Branch.objects.filter(bank=bank).count() == 1
        branch = Branch.objects.get(bank=bank)
        assert (branch.code, branch.name) == ("001", "Main Branch")
        for cur, amount in (("USD", CAP_USD), ("SOS", CAP_SOS)):
            entry = JournalEntry.objects.get(bank=bank, source_type="opening_capital", currency=cur)
            lines = list(entry.lines.select_related("gl_account"))
            assert sum(line.debit for line in lines) == sum(line.credit for line in lines) == amount
            dr = next(line for line in lines if line.debit)
            assert dr.gl_account.code == "1110" and dr.cash_holder_type == "vault"
            assert dr.cash_holder_id == env.vault.pk
            assert next(line for line in lines if line.credit).gl_account.code == "3100"
            assert entry.posted_by_id is None and entry.posted_by_user_id is None
            assert position(bank, env.vault.pk, cur) == amount
            assert gl_balance(bank, "CASH_VAULT", cur) == amount
            assert gl_balance(bank, "CAPITAL", cur) == amount
        assert all(r["ok"] for r in ledger.cash_reconciliation(bank))
        assert ledger.cash_matches_lines(bank)
        assert AuditLog.objects.filter(bank_id=bank.pk, action="ledger.entry_posted").count() == 2

    def test_capital_from_session_settings(self, world):
        s = active_session(world, opening_capital_usd=D("250.50"), opening_capital_sos=D("0"))
        bank = Bank.objects.get(session=s)
        assert position(bank, vault_of(bank).pk, "USD") == D("250.50")
        assert position(bank, vault_of(bank).pk, "SOS") == 0
        assert JournalEntry.objects.filter(bank=bank, currency="SOS").count() == 0
        assert s.opening_capital_usd == D("250.50")

    def test_template_capital_copied_and_validated(self, world):
        t = lab.create_template(
            world["ia"],
            name="T",
            kind="practice",
            structure="single_bank",
            allowed_roles=["teller"],
            default_visibility="own",
            class_id=world["ca"].pk,
            opening_capital_usd=D("10.00"),
            opening_capital_sos=D("20.00"),
        )
        s = lab.create_session(world["ia"], world["ca"].pk, "FromT", template_id=t.pk)
        assert (s.opening_capital_usd, s.opening_capital_sos) == (D("10.00"), D("20.00"))
        for bad in (D("-1"), D("1.005"), "abc"):
            with pytest.raises(lab.ValidationFailed):
                lab.create_session(world["ia"], world["ca"].pk, "Bad", opening_capital_usd=bad)

    def test_capital_via_api(self, world):
        client = api(world["ia"])
        r = j(
            client,
            "post",
            "/api/sessions",
            {"class_id": str(world["ca"].pk), "name": "Api", "opening_capital_usd": "5.00"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["opening_capital_usd"] == "5.00"
        assert body["opening_capital_sos"] == "5000000000.00"
        bad = j(
            client,
            "post",
            "/api/sessions",
            {"class_id": str(world["ca"].pk), "name": "x", "opening_capital_usd": "-3"},
        )
        assert bad.status_code == 400

    def test_per_group_banks_each_get_branch_vault_capital(self, world):
        s = active_session(world, "Groups", structure="per_group")
        banks = list(Bank.objects.filter(session=s))
        assert len(banks) == 3
        for bank in banks:
            assert position(bank, vault_of(bank).pk) == CAP_USD
        assert len({vault_of(b).pk for b in banks}) == 3


# ---------------------------------------------------------------------------- ledger link


@pytest.mark.django_db
class TestCashHolders:
    def spec(self, bank, tag, holder=None, **kw):
        return LineSpec(acct(bank, tag), cash_holder_id=holder, **kw)

    def post(self, bank, lines, currency="USD"):
        return ledger.post_entry(
            bank, lines, currency=currency, source_type="test", description="t"
        )

    def test_cash_line_without_holder_rejected(self, env):
        bank = env.bank
        with pytest.raises(LedgerError) as e:
            self.post(
                bank,
                [
                    self.spec(bank, "CASH_VAULT", debit=D("1")),
                    self.spec(bank, "CAPITAL", credit=D("1")),
                ],
            )
        assert e.value.code == "cash_holder_required"

    def test_wrong_holder_type_unknown_and_foreign_holder_rejected(self, env, world):
        bank = env.bank
        other = Env(world, "x").bank
        for holder_type, holder in (
            ("teller_session", env.vault.pk),
            ("vault", uuid.uuid4()),
            ("vault", vault_of(other).pk),
        ):
            with pytest.raises(LedgerError) as e:
                self.post(
                    bank,
                    [
                        self.spec(
                            bank, "CASH_VAULT", holder, debit=D("1"), cash_holder_type=holder_type
                        ),
                        self.spec(bank, "CAPITAL", credit=D("1")),
                    ],
                )
            assert e.value.code in ("cash_holder_required", "unknown_cash_holder")

    def test_holder_on_non_cash_account_rejected(self, env):
        bank = env.bank
        with pytest.raises(LedgerError) as e:
            self.post(
                bank,
                [
                    self.spec(
                        bank, "CASH_VAULT", env.vault.pk, debit=D("1"), cash_holder_type="vault"
                    ),
                    self.spec(
                        bank, "CAPITAL", env.vault.pk, credit=D("1"), cash_holder_type="vault"
                    ),
                ],
            )
        assert e.value.code == "unexpected_cash_holder"

    def test_vault_never_negative(self, env):
        bank = env.bank
        with pytest.raises(LedgerError) as e:
            self.post(
                bank,
                [
                    self.spec(bank, "CAPITAL", debit=D("1")),
                    self.spec(
                        bank,
                        "CASH_VAULT",
                        env.vault.pk,
                        credit=CAP_USD + D("0.01"),
                        cash_holder_type="vault",
                    ),
                ],
            )
        assert e.value.code in ("insufficient_cash", "unbalanced")
        with pytest.raises(LedgerError) as e:
            self.post(
                bank,
                [
                    self.spec(bank, "CAPITAL", debit=CAP_USD + D("1")),
                    self.spec(
                        bank,
                        "CASH_VAULT",
                        env.vault.pk,
                        credit=CAP_USD + D("1"),
                        cash_holder_type="vault",
                    ),
                ],
            )
        assert e.value.code == "insufficient_cash"
        assert position(bank, env.vault.pk) == CAP_USD
        assert gl_balance(bank, "CASH_VAULT") == CAP_USD
        with pytest.raises(DatabaseError), transaction.atomic():
            CashPosition.objects.filter(bank=bank, currency="USD").update(balance=D("-1"))

    def test_reversal_restores_positions(self, env):
        bank = env.bank
        entry = self.post(
            bank,
            [
                self.spec(
                    bank, "CASH_VAULT", env.vault.pk, credit=D("40.00"), cash_holder_type="vault"
                ),
                self.spec(bank, "CAPITAL", debit=D("40.00")),
            ],
        )
        assert position(bank, env.vault.pk) == CAP_USD - D("40.00")
        ledger.reverse_entry(bank, entry)
        assert position(bank, env.vault.pk) == CAP_USD
        assert gl_balance(bank, "CASH_VAULT") == CAP_USD
        assert all(r["ok"] for r in ledger.cash_reconciliation(bank))
        assert ledger.cash_matches_lines(bank)

    def test_reversal_cannot_drive_cash_negative(self, env):
        bank = env.bank
        a1 = JournalEntry.objects.get(bank=bank, source_type="opening_capital", currency="USD")
        self.post(
            bank,
            [
                self.spec(
                    bank, "CASH_VAULT", env.vault.pk, credit=D("5.00"), cash_holder_type="vault"
                ),
                self.spec(bank, "CAPITAL", debit=D("5.00")),
            ],
        )
        with pytest.raises(LedgerError):
            ledger.reverse_entry(bank, a1)  # would take 1,000,000 out of a vault holding less
        assert position(bank, env.vault.pk) == CAP_USD - D("5.00")

    def test_link_check_detects_mismatch(self, env):
        bank = env.bank
        assert all(r["ok"] for r in ledger.cash_reconciliation(bank))
        CashPosition.objects.filter(bank=bank, currency="USD").update(balance=CAP_USD + 1)
        rows = {r["currency"]: r for r in ledger.cash_reconciliation(bank)}
        assert rows["USD"]["ok"] is False and rows["SOS"]["ok"] is True
        assert rows["USD"]["vault_total"] == CAP_USD + 1 and rows["USD"]["gl_vault"] == CAP_USD
        assert ledger.cash_matches_lines(bank) is False

    def test_journal_line_holder_immutable(self, env):
        line = JournalLine.objects.filter(
            entry__bank=env.bank, cash_holder_id__isnull=False
        ).first()
        line.cash_holder_id = uuid.uuid4()
        with pytest.raises(LedgerImmutableError):
            line.save()


# ---------------------------------------------------------------------------- dual control


@pytest.mark.django_db
class TestDualControl:
    def test_happy_path_posts_b1_and_b2(self, env, teller_holders):
        bank, teller = env.bank, teller_holders(env.bank)
        t = request_transfer(env, teller, "250.00")
        assert t.status == TransferStatus.PENDING
        assert position(bank, env.vault.pk) == CAP_USD  # nothing moved yet
        t1 = banking.approve_custodian(env.member("vault_custodian"), t.pk)
        assert t1.status == TransferStatus.CUSTODIAN_APPROVED
        assert position(bank, env.vault.pk) == CAP_USD
        t2 = banking.approve_manager(env.member("manager"), t.pk)
        assert t2.status == TransferStatus.POSTED and t2.journal_entry_id is not None
        entry = t2.journal_entry
        lines = list(entry.lines.select_related("gl_account"))
        assert sum(x.debit for x in lines) == sum(x.credit for x in lines) == D("250.00")
        assert {(x.gl_account.code, x.debit > 0) for x in lines} == {
            ("1120", True),
            ("1110", False),
        }
        assert position(bank, env.vault.pk) == CAP_USD - D("250.00")
        assert position(bank, teller) == D("250.00")
        assert gl_balance(bank, "CASH_VAULT") == CAP_USD - D("250.00")
        assert gl_balance(bank, "CASH_TELLER") == D("250.00")
        assert all(r["ok"] for r in ledger.cash_reconciliation(bank))
        assert ledger.cash_matches_lines(bank)
        actions = set(AuditLog.objects.filter(entity_id=str(t.pk)).values_list("action", flat=True))
        assert {
            "cash.transfer_requested",
            "cash.transfer_custodian_approved",
            "cash.transfer_posted",
        } <= actions

        # B2: teller -> vault, requested by the teller
        back = banking.request_vault_transfer(
            env.member("teller"),
            from_type="teller_session",
            from_id=teller,
            to_type="vault",
            to_id=env.vault.pk,
            currency="USD",
            amount=D("100.00"),
        )
        full_approval(env, back)
        assert position(bank, teller) == D("150.00")
        assert position(bank, env.vault.pk) == CAP_USD - D("150.00")
        assert ledger.cash_matches_lines(bank)

    def test_requester_cannot_approve_own_request(self, env, teller_holders):
        t = request_transfer(env, teller_holders(env.bank))
        # the requester (a teller) is later given the custodian role: still the maker
        lab.assign_role(self_ia(env), env.session.pk, env.member("teller").pk, "vault_custodian")
        with pytest.raises(rbac.PermissionDenied):
            banking.approve_custodian(env.member("teller"), t.pk)
        t.refresh_from_db()
        assert t.status == TransferStatus.PENDING

    def test_same_person_cannot_give_both_approvals(self, env, teller_holders):
        bank = env.bank
        t = request_transfer(env, teller_holders(bank))
        banking.approve_custodian(env.member("vault_custodian"), t.pk)
        # the custodian is re-assigned to manager and tries the second approval
        lab.assign_role(self_ia(env), env.session.pk, env.member("vault_custodian").pk, "manager")
        with pytest.raises(rbac.PermissionDenied):
            banking.approve_manager(env.member("vault_custodian"), t.pk)
        t.refresh_from_db()
        assert t.status == TransferStatus.CUSTODIAN_APPROVED
        assert position(bank, env.vault.pk) == CAP_USD

    def test_manager_before_custodian_rejected(self, env, teller_holders):
        t = request_transfer(env, teller_holders(env.bank))
        with pytest.raises(LedgerError) as e:
            banking.approve_manager(env.member("manager"), t.pk)
        assert e.value.code == "custodian_approval_required" and e.value.status == 409

    def test_wrong_role_rejected(self, env, teller_holders):
        bank, teller = env.bank, teller_holders(env.bank)
        t = request_transfer(env, teller)
        for role in ("teller", "cso", "manager"):
            with pytest.raises(rbac.PermissionDenied):
                banking.approve_custodian(env.member(role), t.pk)
        banking.approve_custodian(env.member("vault_custodian"), t.pk)
        for role in ("teller", "cso", "vault_custodian"):
            with pytest.raises(rbac.PermissionDenied):
                banking.approve_manager(env.member(role), t.pk)
        # request permissions: cso / custodian cannot request; teller cannot do vault -> teller
        for role in ("cso", "vault_custodian"):
            with pytest.raises(rbac.PermissionDenied):
                request_transfer(env, teller, role=role)
        with pytest.raises(rbac.PermissionDenied):  # only tellers may return cash to the vault
            banking.request_vault_transfer(
                env.member("manager"),
                from_type="teller_session",
                from_id=teller,
                to_type="vault",
                to_id=env.vault.pk,
                currency="USD",
                amount=D("1"),
            )
        assert position(bank, env.vault.pk) == CAP_USD

    def test_rejected_transfer_posts_nothing(self, env, teller_holders):
        bank = env.bank
        t = request_transfer(env, teller_holders(bank))
        banking.approve_custodian(env.member("vault_custodian"), t.pk)
        entries = JournalEntry.objects.filter(bank=bank).count()
        with pytest.raises(LedgerError) as e:
            banking.reject_transfer(env.member("manager"), t.pk, "  ")
        assert e.value.code == "reason_required"
        r = banking.reject_transfer(env.member("manager"), t.pk, "Count first")
        assert r.status == TransferStatus.REJECTED and r.reason == "Count first"
        assert JournalEntry.objects.filter(bank=bank).count() == entries
        assert position(bank, env.vault.pk) == CAP_USD
        for fn in (banking.approve_custodian, banking.approve_manager):
            with pytest.raises(LedgerError) as e:
                fn(
                    env.member("vault_custodian" if fn is banking.approve_custodian else "manager"),
                    t.pk,
                )
            assert e.value.code == "invalid_status"
        assert AuditLog.objects.filter(action="cash.transfer_rejected").count() == 1
        # the requester cannot reject their own request, the teller cannot reject at all
        t2 = request_transfer(env, teller_holders(bank), role="manager")
        with pytest.raises(rbac.PermissionDenied):
            banking.reject_transfer(env.member("teller"), t2.pk, "no")
        # the requester cancels instead (see test_requester_can_cancel)
        c = banking.reject_transfer(env.member("manager"), t2.pk, "")
        assert c.status == TransferStatus.CANCELLED

    def test_requester_can_cancel(self, env, teller_holders):
        bank = env.bank
        entries = JournalEntry.objects.filter(bank=bank).count()
        t = request_transfer(env, teller_holders(bank))
        c = banking.reject_transfer(env.member("teller"), t.pk, "changed my mind")
        assert c.status == TransferStatus.CANCELLED and c.rejected_by_id == env.member("teller").pk
        assert AuditLog.objects.filter(action="cash.transfer_cancelled").count() == 1
        t2 = request_transfer(env, teller_holders(bank))
        banking.approve_custodian(env.member("vault_custodian"), t2.pk)
        assert banking.reject_transfer(env.member("teller"), t2.pk, "").status == "cancelled"
        with pytest.raises(LedgerError):  # already closed
            banking.reject_transfer(env.member("teller"), t2.pk, "again")
        with pytest.raises(LedgerError):
            banking.approve_manager(env.member("manager"), t2.pk)
        # someone else's request cannot be cancelled by an unrelated role
        t3 = request_transfer(env, teller_holders(bank))
        with pytest.raises(rbac.PermissionDenied):
            banking.reject_transfer(env.member("cso"), t3.pk, "x")
        assert JournalEntry.objects.filter(bank=bank).count() == entries
        assert position(bank, env.vault.pk) == CAP_USD

    def test_posted_transfer_cannot_be_approved_or_rejected_again(self, env, teller_holders):
        t = request_transfer(env, teller_holders(env.bank))
        full_approval(env, t)
        with pytest.raises(LedgerError):
            banking.approve_manager(env.member("manager"), t.pk)
        with pytest.raises(LedgerError):
            banking.reject_transfer(env.member("manager"), t.pk, "late")
        assert JournalEntry.objects.filter(bank=env.bank, source_type="cash_transfer").count() == 1

    def test_validation_rules(self, env, teller_holders):
        teller = teller_holders(env.bank)
        cases = [
            ({"amount": D("0")}, "invalid_amount"),
            ({"amount": D("-5")}, "invalid_amount"),
            ({"amount": D("1.001")}, "invalid_amount"),
            ({"amount": CAP_USD + D("0.01")}, "insufficient_cash"),
            ({"currency": "EUR"}, "invalid_currency"),
            ({"to_id": uuid.uuid4()}, "unknown_cash_holder"),
            ({"to_type": "vault", "to_id": env.vault.pk}, "invalid_holder_type"),
        ]
        for override, code in cases:
            args = dict(
                from_type="vault",
                from_id=env.vault.pk,
                to_type="teller_session",
                to_id=teller,
                currency="USD",
                amount=D("10.00"),
            )
            args.update(override)
            with pytest.raises(LedgerError) as e:
                banking.request_vault_transfer(env.member("manager"), **args)
            assert e.value.code == code, override
        # teller -> teller is not supported yet (needs 1.8)
        with pytest.raises(rbac.PermissionDenied):
            banking.request_vault_transfer(
                env.member("manager"),
                from_type="teller_session",
                from_id=teller,
                to_type="teller_session",
                to_id=teller,
                currency="USD",
                amount=D("1"),
            )
        assert not CashTransfer.objects.exists()

    def test_unknown_teller_session_rejected(self, env):
        with pytest.raises(LedgerError) as e:  # teller without a session
            request_transfer(env, uuid.uuid4())
        assert e.value.code == "no_open_till"
        with pytest.raises(LedgerError) as e:  # manager naming a session that does not exist
            request_transfer(env, uuid.uuid4(), role="manager")
        assert e.value.code == "unknown_cash_holder"

    def test_post_rechecks_balance(self, env, teller_holders):
        bank = env.bank
        t = request_transfer(env, teller_holders(bank), "900000.00")
        banking.approve_custodian(env.member("vault_custodian"), t.pk)
        # the vault is drained after the request
        ledger.post_entry(
            bank,
            [
                LineSpec(acct(bank, "CAPITAL"), debit=D("500000.00")),
                LineSpec(
                    acct(bank, "CASH_VAULT"),
                    credit=D("500000.00"),
                    cash_holder_type="vault",
                    cash_holder_id=env.vault.pk,
                ),
            ],
            currency="USD",
            source_type="test",
            description="drain",
        )
        with pytest.raises(LedgerError) as e:
            banking.approve_manager(env.member("manager"), t.pk)
        assert e.value.code == "insufficient_cash"
        t.refresh_from_db()
        assert t.status == TransferStatus.CUSTODIAN_APPROVED and t.journal_entry_id is None

    def test_closed_business_day_blocks(self, env, teller_holders):
        t = request_transfer(env, teller_holders(env.bank))
        BusinessDay.objects.filter(bank=env.bank).update(status="closed")
        with pytest.raises(LedgerError) as e:
            request_transfer(env, teller_holders(env.bank))
        assert e.value.code == "day_closed"
        banking.approve_custodian(env.member("vault_custodian"), t.pk)
        with pytest.raises(LedgerError) as e:
            banking.approve_manager(env.member("manager"), t.pk)
        assert e.value.code == "day_closed"

    def test_archived_session_read_only(self, env, teller_holders, world):
        t = request_transfer(env, teller_holders(env.bank))
        lab.archive_session(world["ia"], env.session.pk)
        with pytest.raises(LedgerError) as e:
            request_transfer(env, teller_holders(env.bank))
        assert e.value.code == "session_archived"
        with pytest.raises(LedgerError):
            banking.approve_custodian(env.member("vault_custodian"), t.pk)
        client = api(env.user("manager"))
        assert client.get(f"/api/s/{env.session.pk}/vault").status_code == 200
        r = j(
            client, "post", f"/api/s/{env.session.pk}/cash-transfers/{t.pk}/reject", {"reason": "x"}
        )
        assert r.status_code == 409

    def test_transfers_cannot_be_deleted(self, env, teller_holders):
        t = request_transfer(env, teller_holders(env.bank))
        with pytest.raises(NotImplementedError):
            t.delete()
        with pytest.raises(NotImplementedError):
            CashTransfer.objects.all().delete()
        with pytest.raises(NotImplementedError):
            CashPosition.objects.all().delete()
        with pytest.raises(NotImplementedError):
            Till.objects.all().delete()
        with pytest.raises(NotImplementedError):
            Branch.objects.get(bank=env.bank).delete()


def self_ia(env):
    return env.world["ia"]


# ---------------------------------------------------------------------------- API


@pytest.mark.django_db
class TestCashApi:
    def url(self, env, path=""):
        return f"/api/s/{env.session.pk}/{path}"

    def test_full_flow_over_api(self, env, teller_holders):
        teller = teller_holders(env.bank)
        body = {
            "from_type": "vault",
            "from_id": str(env.vault.pk),
            "to_type": "teller_session",
            "to_id": str(teller),
            "currency": "USD",
            "amount": "75.50",
        }
        r = j(api(env.user("teller")), "post", self.url(env, "cash-transfers"), body)
        assert r.status_code == 200, r.content
        t = r.json()
        assert t["status"] == "pending" and t["amount"] == "75.50"
        assert t["amount_in_words"] == "Seventy-five US Dollars and 50/100"
        tid = t["id"]
        # manager before custodian
        r = j(
            api(env.user("manager")), "post", self.url(env, f"cash-transfers/{tid}/approve-manager")
        )
        assert r.status_code == 409 and r.json()["code"] == "custodian_approval_required"
        r = j(
            api(env.user("vault_custodian")),
            "post",
            self.url(env, f"cash-transfers/{tid}/approve-custodian"),
        )
        assert r.status_code == 200 and r.json()["status"] == "custodian_approved"
        assert r.json()["approved_by_1_name"]
        r = j(
            api(env.user("manager")), "post", self.url(env, f"cash-transfers/{tid}/approve-manager")
        )
        assert r.status_code == 200 and r.json()["status"] == "posted"
        assert r.json()["journal_entry_id"]
        listing = api(env.user("vault_custodian")).get(self.url(env, "cash-transfers")).json()
        assert [x["id"] for x in listing] == [tid]
        assert listing[0]["from_label"].startswith("Vault · ") and listing[0][
            "to_label"
        ].startswith("Till ")
        v = api(env.user("vault_custodian")).get(self.url(env, "vault")).json()
        usd = next(p for p in v["branches"][0]["positions"] if p["currency"] == "USD")
        assert D(usd["balance"]) == CAP_USD - D("75.50")
        assert all(row["ok"] for row in v["reconciliation"])

    def test_permissions_on_vault_and_transfers(self, env, teller_holders):
        for role, code in (
            ("teller", 403),
            ("cso", 403),
            ("manager", 200),
            ("vault_custodian", 200),
        ):
            client = api(env.user(role))
            assert client.get(self.url(env, "vault")).status_code == code
            assert client.get(self.url(env, "cash-transfers")).status_code == code
        t = request_transfer(env, teller_holders(env.bank))
        for role in ("teller", "cso", "manager"):
            r = j(
                api(env.user(role)),
                "post",
                self.url(env, f"cash-transfers/{t.pk}/approve-custodian"),
            )
            assert r.status_code == 403
        r = j(
            api(env.user("cso")),
            "post",
            self.url(env, f"cash-transfers/{t.pk}/reject"),
            {"reason": "no"},
        )
        assert r.status_code == 403
        r = j(
            api(env.user("teller")),
            "post",
            self.url(env, f"cash-transfers/{t.pk}/reject"),
            {"reason": ""},
        )  # the requester may cancel
        assert r.status_code == 200 and r.json()["status"] == "cancelled"
        r = j(
            api(env.user("cso")),
            "post",
            self.url(env, "cash-transfers"),
            {
                "from_type": "vault",
                "from_id": str(env.vault.pk),
                "to_type": "teller_session",
                "to_id": str(uuid.uuid4()),
                "currency": "USD",
                "amount": "1.00",
            },
        )
        assert r.status_code == 403
        assert api(env.world["ia"]).get(self.url(env, "vault")).status_code == 403

    def test_cross_session_and_cross_bank_isolation(self, world, teller_holders):
        env_a = Env(world, "a", structure="per_group")
        bank1 = env_a.bank
        bank2 = Bank.objects.filter(session=env_a.session, group_no=2).get()
        cust2 = add_person(world, env_a.session, bank2, "cust2", "vault_custodian")
        mgr2 = add_person(world, env_a.session, bank2, "mgr2", "manager")
        t = request_transfer(env_a, teller_holders(bank1))
        sid = env_a.session.pk

        # bank 2 staff see nothing of bank 1, and cannot act on its transfer
        c2 = api(cust2[0])
        assert c2.get(f"/api/s/{sid}/cash-transfers").json() == []
        v2 = c2.get(f"/api/s/{sid}/vault").json()
        assert [b["vault_id"] for b in v2["branches"]] == [str(vault_of(bank2).pk)]
        r = j(c2, "post", f"/api/s/{sid}/cash-transfers/{t.pk}/approve-custodian")
        assert r.status_code == 404
        with pytest.raises(LedgerError) as e:
            banking.approve_custodian(cust2[1], t.pk)
        assert e.value.status == 404
        assert (
            j(
                api(mgr2[0]), "post", f"/api/s/{sid}/cash-transfers/{t.pk}/reject", {"reason": "x"}
            ).status_code
            == 404
        )
        # bank 2 cannot request from bank 1's vault
        with pytest.raises(LedgerError) as e:
            banking.request_vault_transfer(
                mgr2[1],
                from_type="vault",
                from_id=vault_of(bank1).pk,
                to_type="teller_session",
                to_id=teller_holders(bank1),
                currency="USD",
                amount=D("1"),
            )
        assert e.value.code == "unknown_cash_holder"
        # another session: its manager is not a member here
        env_b = Env(world, "b")
        other = api(env_b.user("manager"))
        assert other.get(f"/api/s/{sid}/vault").status_code == 403
        assert other.get(f"/api/s/{sid}/cash-transfers").status_code == 403
        assert (
            j(other, "post", f"/api/s/{sid}/cash-transfers/{t.pk}/approve-manager").status_code
            == 403
        )
        assert (
            api(env_b.user("manager")).get(f"/api/s/{env_b.session.pk}/cash-transfers").json() == []
        )

    def test_denominations(self, env):
        rows = api(env.user("teller")).get("/api/denominations").json()
        usd = [r["value"] for r in rows if r["currency"] == "USD"]
        assert usd == ["100.00", "50.00", "20.00", "10.00", "5.00", "2.00", "1.00"]
        assert Denomination.objects.filter(currency="SOS").count() >= 4


# ---------------------------------------------------------------------------- branches & tills


@pytest.mark.django_db
class TestBranchesAndTills:
    def base(self, env):
        return f"/api/sessions/{env.session.pk}/banks/{env.bank.pk}/branches"

    def test_instructor_crud_and_vault_creation(self, env):
        client = api(env.world["ia"])
        r = j(client, "post", self.base(env), {"code": "002", "name": "Hargeisa", "address": "x"})
        assert r.status_code == 200, r.content
        branch = r.json()
        assert branch["code"] == "002" and branch["vault_id"]
        vault = Vault.objects.get(pk=branch["vault_id"])
        assert vault.bank_id == env.bank.pk
        assert sorted(
            CashPosition.objects.filter(holder_id=vault.pk).values_list("currency", "balance")
        ) == [("SOS", 0), ("USD", 0)]
        assert [b["code"] for b in client.get(self.base(env)).json()] == ["001", "002"]
        r = j(client, "patch", f"{self.base(env)}/{branch['id']}", {"name": "Hargeisa 2"})
        assert r.status_code == 200 and r.json()["name"] == "Hargeisa 2"
        assert r.json()["address"] == "x"
        dup = j(client, "post", self.base(env), {"code": "002", "name": "Dup"})
        assert dup.status_code == 409
        assert j(client, "post", self.base(env), {"code": " ", "name": "x"}).status_code == 400
        assert AuditLog.objects.filter(action="banking.branch_created").count() >= 1
        assert AuditLog.objects.filter(action="banking.branch_updated").count() == 1
        # new vault is part of the cash link check
        assert all(r["ok"] for r in ledger.cash_reconciliation(env.bank))

    def test_tills(self, env):
        client = api(env.world["ia"])
        branch = Branch.objects.get(bank=env.bank)
        url = f"{self.base(env)}/{branch.pk}/tills"
        assert j(client, "post", url, {"code": "T1"}).status_code == 200
        assert j(client, "post", url, {"code": "T1"}).status_code == 409
        assert [t["code"] for t in client.get(url).json()] == ["T1"]
        assert Till.objects.get(bank=env.bank).branch_id == branch.pk
        missing = f"{self.base(env)}/{uuid.uuid4()}/tills"
        assert j(client, "post", missing, {"code": "T9"}).status_code == 404

    def test_permissions_and_isolation(self, env, world):
        branch = Branch.objects.get(bank=env.bank)
        # students and other instructors are refused
        for user, code in ((env.user("manager"), 403), (world["ib"], 404)):
            c = api(user)
            assert c.get(self.base(env)).status_code == code
            assert j(c, "post", self.base(env), {"code": "9", "name": "n"}).status_code == code
            assert j(c, "patch", f"{self.base(env)}/{branch.pk}", {"name": "n"}).status_code == code
            assert (
                j(c, "post", f"{self.base(env)}/{branch.pk}/tills", {"code": "t"}).status_code
                == code
            )
        # a bank of another session / a branch of another bank is never reachable
        other = Env(world, "o")
        client = api(world["ia"])
        wrong_bank = f"/api/sessions/{env.session.pk}/banks/{other.bank.pk}/branches"
        assert client.get(wrong_bank).status_code == 404
        other_branch = Branch.objects.get(bank=other.bank)
        r = j(client, "patch", f"{self.base(env)}/{other_branch.pk}", {"name": "hack"})
        assert r.status_code == 404
        r = j(client, "post", f"{self.base(env)}/{other_branch.pk}/tills", {"code": "t"})
        assert r.status_code == 404
        other_branch.refresh_from_db()
        assert other_branch.name == "Main Branch"

    def test_archived_session_read_only(self, env, world):
        client = api(world["ia"])
        lab.archive_session(world["ia"], env.session.pk)
        assert client.get(self.base(env)).status_code == 200
        assert j(client, "post", self.base(env), {"code": "003", "name": "n"}).status_code == 409
        branch = Branch.objects.get(bank=env.bank)
        assert (
            j(client, "post", f"{self.base(env)}/{branch.pk}/tills", {"code": "t"}).status_code
            == 409
        )
        assert j(client, "patch", f"{self.base(env)}/{branch.pk}", {"name": "n"}).status_code == 409


# ---------------------------------------------------------------------------- backfill


@pytest.mark.django_db
class TestBackfill:
    def legacy_bank(self, session, group_no):
        bank = Bank.objects.create(session=session, name=f"Legacy {group_no}", group_no=group_no)
        BusinessDay.objects.create(bank=bank, date=BusinessDay.objects.first().date)
        ledger.provision_bank_coa(bank)
        return bank

    def test_backfill_is_idempotent(self, world):
        s = active_session(world)
        bank = self.legacy_bank(s, 77)
        assert not Branch.objects.filter(bank=bank).exists()
        call_command("backfill_bank_vaults")
        call_command("backfill_bank_vaults")
        assert Branch.objects.filter(bank=bank).count() == 1
        assert Vault.objects.filter(bank=bank).count() == 1
        assert JournalEntry.objects.filter(bank=bank, source_type="opening_capital").count() == 2
        assert position(bank, vault_of(bank).pk) == CAP_USD
        assert all(r["ok"] for r in ledger.cash_reconciliation(bank))
        # banks that already have a branch are untouched
        main = Bank.objects.get(session=s, group_no=None)
        assert JournalEntry.objects.filter(bank=main, source_type="opening_capital").count() == 2

    def test_archived_sessions_are_skipped(self, world):
        s = active_session(world)
        bank = self.legacy_bank(s, 78)
        lab.archive_session(world["ia"], s.pk)
        call_command("backfill_bank_vaults")
        assert not Branch.objects.filter(bank=bank).exists()
        assert not JournalEntry.objects.filter(bank=bank).exists()


# ---------------------------------------------------------------------------- concurrency


def run_threads(fns):
    results, errors = [], []

    def wrap(fn):
        def run():
            try:
                results.append(fn())
            except (LedgerError, rbac.PermissionDenied) as exc:
                results.append(getattr(exc, "code", "denied"))
            except Exception as exc:  # pragma: no cover - surfaced by the assert below
                errors.append(exc)
            finally:
                connection.close()

        return run

    threads = [threading.Thread(target=wrap(fn)) for fn in fns]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not any(t.is_alive() for t in threads), "worker thread hung"
    assert not errors, errors
    return results


# serialized_rollback restores the migration-seeded permissions after the table flush
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
class TestConcurrency:
    def test_two_manager_approvals_post_once(self, world, teller_holders):
        env = Env(world)
        t = request_transfer(env, teller_holders(env.bank), "100.00")
        banking.approve_custodian(env.member("vault_custodian"), t.pk)
        results = run_threads(
            [lambda: banking.approve_manager(env.member("manager"), t.pk).status] * 2
        )
        assert sorted(results) == ["invalid_status", "posted"]
        assert JournalEntry.objects.filter(bank=env.bank, source_type="cash_transfer").count() == 1
        assert position(env.bank, env.vault.pk) == CAP_USD - D("100.00")
        assert ledger.cash_matches_lines(env.bank)

    def test_two_transfers_draining_one_vault(self, world, teller_holders):
        env = Env(world)
        teller = teller_holders(env.bank)
        ts = [request_transfer(env, teller, "600000.00") for _ in range(2)]
        for t in ts:
            banking.approve_custodian(env.member("vault_custodian"), t.pk)
        results = run_threads(
            [lambda t=t: banking.approve_manager(env.member("manager"), t.pk).status for t in ts]
        )
        assert sorted(results) == ["insufficient_cash", "posted"]
        assert position(env.bank, env.vault.pk) == CAP_USD - D("600000.00")
        assert position(env.bank, teller) == D("600000.00")
        assert all(r["ok"] for r in ledger.cash_reconciliation(env.bank))
        assert ledger.cash_matches_lines(env.bank)
