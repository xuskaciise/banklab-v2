"""Seed (or retire) an isolated load-test institution for the Locust run in backend/loadtest.

Everything goes through the real services (no balance is written directly): one instructor, one
class of N students, one per-group session with several banks, a role for every student, open
teller sessions funded from the vault, and a few KYC-complete customers with funded accounts.

Run it against a THROWAWAY database (e.g. DATABASE_URL pointing at `banklab_loadtest`):
financial records are append-only, so `--teardown` cannot delete them. It archives the load-test
session(s) (read-only from then on) and deactivates the load-test users instead.
"""

import csv
import os
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.accounts.models import Institution, PlatformRole, User
from apps.accounts.services import MIN_PASSWORD_LENGTH
from apps.banking import services as banking
from apps.banking import tellers, transactions
from apps.banking.models import Branch, CashTransfer
from apps.customers import services as customers
from apps.customers.models import CustomerParty, IdentityDocument
from apps.lab import services as lab
from apps.lab.models import Bank, Session, SessionMember, SessionStatus
from apps.products import services as products
from apps.products.models import Product

PREFIX = "LOADTEST"
INSTITUTION = f"{PREFIX} Institution"
INSTRUCTOR = "LTINSTR"
CAPITAL_USD = Decimal("50000000.00")
TELLER_FLOAT = Decimal("20000.00")
ACCOUNT_OPENING = Decimal("5000.00")
STAFF_ROLES = ["manager", "vault_custodian", "cso", "accountant"]
MIN_STUDENTS_PER_BANK = len(STAFF_ROLES) + 1
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF = b"%PDF-1.4 " + b"0" * 64


def student_id(n: int) -> str:
    return f"LT{n:04d}"


def _person(name: str, serial: str) -> dict:
    return {
        "full_name": name,
        "sex": "female",
        "date_of_birth": date(1990, 5, 5),
        "phone": "+252611111111",
        "relation": "owner",
        "identity_documents": [
            {
                "type": "national_id",
                "number": f"LT-{serial}",
                "issue_date": date(2020, 1, 1),
                "expiry_date": date(2035, 1, 1),
            }
        ],
        "next_of_kin": [{"name": "Kin Person", "phone": "0611222333", "relationship": "Father"}],
    }


def _complete_kyc(cso, customer) -> None:
    for link in CustomerParty.objects.filter(customer=customer, can_sign=True):
        pid = link.party_id
        for kind in ("photo", "signature"):
            customers.upload_party_file(
                cso, customer.pk, pid, kind, SimpleUploadedFile("a.png", PNG)
            )
        for d in IdentityDocument.objects.filter(party_id=pid):
            customers.upload_document_file(
                cso, customer.pk, pid, d.pk, SimpleUploadedFile("a.pdf", PDF)
            )


class Command(BaseCommand):
    help = "Create (or --teardown) an isolated LOADTEST institution with N role-assigned students."

    def add_arguments(self, parser):
        parser.add_argument("--students", type=int, default=200)
        parser.add_argument("--banks", type=int, default=4, help="banks (groups) in the session")
        parser.add_argument("--customers", type=int, default=10, help="customers per bank")
        parser.add_argument("--password", default="", help="default: env LOADTEST_PASSWORD")
        parser.add_argument("--csv", default="loadtest/students.csv", help="output id list")
        parser.add_argument("--teardown", action="store_true")

    def handle(self, *args, **o):
        db_name = connection.settings_dict.get("NAME") or ""
        if "loadtest" not in db_name and not settings.DEBUG:
            # Ledger rows can never be deleted: never seed 200 shared-password users into a real DB.
            raise CommandError(
                "Refusing to run: the database name must contain 'loadtest' (or DJANGO_DEBUG=true)."
            )
        if o["teardown"]:
            return self.teardown()
        password = o["password"] or os.environ.get("LOADTEST_PASSWORD", "")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise CommandError(
                f"Give --password or env LOADTEST_PASSWORD (min {MIN_PASSWORD_LENGTH} chars)"
            )
        n, banks = o["students"], o["banks"]
        if banks < 1 or n < banks * MIN_STUDENTS_PER_BANK:
            raise CommandError(f"Need at least {MIN_STUDENTS_PER_BANK} students per bank")
        if Institution.objects.filter(name=INSTITUTION).exists():
            raise CommandError(
                "Load-test data already exists in this database; use a fresh throwaway "
                "database (financial records cannot be deleted)"
            )
        with transaction.atomic():
            rows = self.seed(n, banks, o["customers"], password)
        path = Path(o["csv"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["student_id", "role", "bank", "kind"])
            w.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Seeded {n} students in {banks} banks -> {path}"))

    # ------------------------------------------------------------------ seed
    def seed(self, n, banks, per_bank_customers, password) -> list[list[str]]:
        hashed = make_password(password)  # one hash for every load-test student
        inst = Institution.objects.create(name=INSTITUTION)
        instructor = User.objects.create_user(
            INSTRUCTOR,
            password=password,
            full_name=f"{PREFIX} Instructor",
            phone="0611000000",
            platform_role=PlatformRole.INSTRUCTOR,
            institution=inst,
            must_change_password=False,
        )
        lab_class = lab.create_class(instructor, f"{PREFIX} class", PREFIX)
        users = []
        for i in range(1, n + 1):
            user, _ = lab.add_student(
                instructor, lab_class.pk, student_id(i), f"{PREFIX} Student {i}", f"06119{i:05d}"
            )
            users.append(user)
        User.objects.filter(pk__in=[u.pk for u in users]).update(
            password=hashed, must_change_password=False
        )
        session = lab.create_session(
            instructor,
            lab_class.pk,
            f"{PREFIX} session",
            structure="per_group",
            # Whole-bank visibility so every teller can transact on the shared seed accounts.
            default_visibility="all",
            opening_capital_usd=CAPITAL_USD,
        )
        session = lab.open_session(instructor, session.pk, banks)
        rows = [[INSTRUCTOR, "instructor", "", "staff"]]
        for idx, bank in enumerate(Bank.objects.filter(session=session).order_by("group_no")):
            chunk = users[idx::banks]  # round-robin keeps bank sizes even
            members = lab.add_members(
                instructor, session.pk, [u.pk for u in chunk], bank_id=bank.pk
            )
            by_role: dict[str, list[SessionMember]] = {}
            for j, m in enumerate(members):
                role = STAFF_ROLES[j] if j < len(STAFF_ROLES) else "teller"
                lab.assign_role(instructor, session.pk, m.pk, role)
                by_role.setdefault(role, []).append(SessionMember.objects.get(pk=m.pk))
                rows.append([m.user.username, role, bank.name, "student"])
            self.provision_bank(instructor, session, bank, by_role, per_bank_customers)
        return rows

    def provision_bank(self, instructor, session, bank, by_role, per_bank_customers) -> None:
        manager = by_role["manager"][0]
        custodian = by_role["vault_custodian"][0]
        cso = by_role["cso"][0]
        bank_tellers = by_role["teller"]
        branch = Branch.objects.filter(bank=bank).first()
        floats = [{"currency": "USD", "amount": TELLER_FLOAT}]
        for k, teller in enumerate(bank_tellers, start=1):
            till = banking.create_till(instructor, session.pk, bank.pk, branch.pk, code=f"T{k}")
            ts = tellers.request_open(teller, till.pk, floats)
            for t in CashTransfer.objects.filter(bank=bank, to_id=ts.pk):
                banking.approve_custodian(custodian, t.pk)
                banking.approve_manager(manager, t.pk)
            tellers.approve_open(manager, ts.pk)
        product = Product.objects.get(bank=bank, code="SAV-USD")
        for c in range(per_bank_customers):
            name = f"{PREFIX} Customer {bank.group_no}-{c + 1}"
            customer = customers.create_customer(
                cso,
                type="individual",
                address="Hodan",
                parties=[_person(name, uuid.uuid4().hex[:8])],
            )
            _complete_kyc(cso, customer)
            account = products.open_account(cso, customer_id=customer.pk, product_id=product.pk)
            transactions.deposit(
                bank_tellers[c % len(bank_tellers)],
                account_id=account.pk,
                amount=ACCOUNT_OPENING,
                currency=account.currency,
                party_name="Seed Depositor",
                party_id_no="SEED-1",
                party_phone="+252611000111",
            )

    # -------------------------------------------------------------- teardown
    def teardown(self):
        inst = Institution.objects.filter(name=INSTITUTION).first()
        if inst is None:
            self.stdout.write("No load-test data found")
            return
        instructor = User.objects.filter(institution=inst, username=INSTRUCTOR).first()
        archived = 0
        with transaction.atomic():
            for s in Session.objects.filter(
                lab_class__institution=inst, name__startswith=PREFIX, status=SessionStatus.ACTIVE
            ):
                lab.archive_session(instructor, s.pk)
                archived += 1
            deactivated = User.objects.filter(institution=inst).update(is_active=False)
        self.stdout.write(
            f"Archived {archived} session(s), deactivated {deactivated} user(s). "
            "Ledger rows are append-only and stay; use a throwaway database for load tests."
        )
