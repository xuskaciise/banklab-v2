# ruff: noqa: F811
"""1.6 Customers (CIF): types and their rules, ID documents, permissions, own-visibility,
bank/session isolation, archived read-only, CIF numbering, files and audit.

Customers move no money, so there is no journal entry to balance (Dr = Cr) here."""

import uuid
from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command  # noqa: F401
from django.db import connection

from apps.audit.models import AuditLog
from apps.customers import services as cs
from apps.customers.models import Customer, CustomerParty, IdentityDocument, Party
from apps.lab import services as lab
from apps.lab.models import Bank, SessionMember
from apps.ledger.models import JournalEntry
from apps.ledger.services import LedgerError
from apps.rbac import services as rbac
from tests.test_cash import add_person
from tests.test_lab import (  # noqa: F401  (fixtures)
    _reset_rbac,
    active_session,
    api,
    j,
    world,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
PDF = b"%PDF-1.4 " + b"0" * 64


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def doc(number="N123", issue=date(2020, 1, 1), expiry=date(2030, 1, 1), type="national_id"):
    return {"type": type, "number": number, "issue_date": issue, "expiry_date": expiry}


def person(name="Amina Ali", relation="owner", **kw):
    return {
        "full_name": name,
        "sex": "female",
        "date_of_birth": date(1990, 5, 5),
        "phone": "+252611111111",
        "relation": relation,
        "identity_documents": [doc(number=f"ID-{uuid.uuid4().hex[:6]}")],
        "next_of_kin": [{"name": "Ali Hassan", "phone": "0611222333", "relationship": "Father"}],
        **kw,
    }


def individual(**kw):
    return {"type": "individual", "parties": [person()], **kw}


def joint(**kw):
    parties = [person("A One", "joint_holder"), person("B Two", "joint_holder")]
    return {"type": "joint", "display_name": "A & B", "parties": parties, **kw}


def company(**kw):
    parties = [person("Dir One", "director"), person("Sig Two", "signatory")]
    return {
        "type": "company",
        "display_name": "Acme Ltd",
        "reg_no": "REG-1",
        "parties": parties,
        **kw,
    }


def ngo(**kw):
    return {**company(**kw), "type": "ngo", "display_name": "Helpers", "reg_no": "NGO-9"}


class Env:
    def __init__(self, world, suffix="", **kw):
        self.world = world
        self.session = active_session(world, f"Cust{suffix}", **kw)
        self.bank = Bank.objects.filter(session=self.session).order_by("group_no").first()
        self.people = {}
        for key, role in (
            ("teller", "teller"),
            ("teller2", "teller"),
            ("cso", "cso"),
            ("cso2", "cso"),
            ("manager", "manager"),
            ("accountant", "accountant"),
            ("vault", "vault_custodian"),
        ):
            self.people[key] = add_person(
                world, self.session, self.bank, f"{key[:5]}{suffix}{uuid.uuid4().hex[:4]}", role
            )

    def user(self, key):
        return self.people[key][0]

    def member(self, key):
        return self.people[key][1]

    def url(self, path=""):
        return f"/api/s/{self.session.pk}/customers{path}"


@pytest.fixture
def env(world):
    return Env(world)


def make(env, key="cso", data=None):
    return cs.create_customer(env.member(key), **(data or individual()))


def cust_json(client, env, data=None):
    r = j(client, "post", env.url(), _jsonable(data or individual()))
    assert r.status_code == 200, r.content
    return r.json()


def _jsonable(data):
    import json

    return json.loads(json.dumps(data, default=lambda o: o.isoformat()))


# ---------------------------------------------------------------------------- types


@pytest.mark.django_db
class TestTypes:
    def test_individual(self, env):
        c = make(env)
        assert (c.cif_no, c.type, c.display_name) == (1, "individual", "Amina Ali")
        (link,) = c.links.all()
        assert (link.relation, link.can_sign) == ("owner", True)
        assert link.party.documents.count() == 1 and link.party.next_of_kin.count() == 1
        assert c.created_by_id == env.member("cso").pk and not c.is_seed

    def test_joint(self, env):
        c = make(env, data=joint())
        assert sorted(link.relation for link in c.links.all()) == ["joint_holder"] * 2

    def test_company_and_ngo(self, env):
        c = make(env, data=company())
        assert c.reg_no == "REG-1"
        assert {(link.relation, link.can_sign) for link in c.links.all()} == {
            ("director", False),
            ("signatory", True),
        }
        n = make(env, "manager", ngo())
        assert n.type == "ngo" and n.cif_no == 2

    @pytest.mark.parametrize(
        "data,code",
        [
            ({"type": "individual", "parties": []}, "invalid_parties"),
            ({"type": "individual", "parties": [person(), person("X")]}, "invalid_parties"),
            ({"type": "individual", "parties": [person(relation="signatory")]}, "invalid_relation"),
            (
                {
                    "type": "joint",
                    "display_name": "J",
                    "parties": [person(relation="joint_holder")],
                },
                "invalid_parties",
            ),
            (
                {"type": "joint", "display_name": "J", "parties": [person(), person("Y")]},
                "invalid_relation",
            ),
            (
                {"type": "company", "display_name": "C", "parties": [person(relation="signatory")]},
                "reg_no_required",
            ),
            (
                {
                    "type": "ngo",
                    "display_name": "C",
                    "reg_no": "R",
                    "parties": [person(relation="director")],
                },
                "invalid_parties",
            ),
            (
                {
                    "type": "company",
                    "display_name": "C",
                    "reg_no": "R",
                    "parties": [person(relation="owner")],
                },
                "invalid_relation",
            ),
            ({"type": "bogus", "parties": [person()]}, "invalid_customer"),
            ({"type": "individual", "reg_no": "R", "parties": [person()]}, "invalid_customer"),
            (
                {
                    "type": "joint",
                    "parties": [person("A", "joint_holder"), person("B", "joint_holder")],
                },
                "invalid_customer",
            ),
        ],
    )
    def test_rule_violations(self, env, data, code):
        with pytest.raises(LedgerError) as e:
            make(env, data=data)
        assert e.value.code == code and e.value.status == 400
        assert Customer.objects.count() == 0 and Party.objects.count() == 0

    def test_document_rules(self, env):
        no_doc = person(identity_documents=[])
        with pytest.raises(LedgerError) as e:
            make(env, data={"type": "individual", "parties": [no_doc]})
        assert e.value.code == "document_required"
        for issue, expiry in (
            (date(2025, 1, 1), date(2025, 1, 1)),
            (date(2025, 1, 2), date(2024, 1, 1)),
        ):
            bad = person(identity_documents=[doc(issue=issue, expiry=expiry)])
            with pytest.raises(LedgerError, match="Expiry date"):
                make(env, data={"type": "individual", "parties": [bad]})

    def test_invalid_fields(self, env):
        for patch in ({"phone": "abc"}, {"email": "nope"}, {"address": "x" * 301}):
            with pytest.raises(LedgerError):
                make(env, data=individual(**patch))
        with pytest.raises(LedgerError, match="past"):
            make(
                env,
                data={"type": "individual", "parties": [person(date_of_birth=date(2999, 1, 1))]},
            )

    def test_failed_create_rolls_back_everything(self, env):
        bad = person(
            "Second",
            "joint_holder",
            identity_documents=[doc(issue=date(2025, 1, 1), expiry=date(2024, 1, 1))],
        )
        with pytest.raises(LedgerError):
            make(
                env,
                data={
                    "type": "joint",
                    "display_name": "J",
                    "parties": [person("A", "joint_holder"), bad],
                },
            )
        assert not Customer.objects.exists() and not Party.objects.exists()
        assert not IdentityDocument.objects.exists()


# ---------------------------------------------------------------------------- updates


@pytest.mark.django_db
class TestUpdates:
    def test_update_customer_audited_before_after(self, env):
        c = make(env)
        cs.update_customer(env.member("manager"), c.pk, phone="0612345678", address="Hodan")
        row = AuditLog.objects.get(action="customer.updated", entity_id=str(c.pk))
        assert row.before["phone"] == "" and row.after["phone"] == "0612345678"
        assert row.bank_id == env.bank.pk and row.session_id == env.session.pk
        assert AuditLog.objects.filter(action="customer.created", entity_id=str(c.pk)).exists()

    def test_company_reg_no_cannot_be_blanked(self, env):
        c = make(env, data=company())
        with pytest.raises(LedgerError) as e:
            cs.update_customer(env.member("cso"), c.pk, reg_no="")
        assert e.value.code == "reg_no_required"
        cs.update_customer(env.member("cso"), c.pk, reg_no="REG-2")

    def test_add_party_rules(self, env):
        ind = make(env)
        with pytest.raises(LedgerError):
            cs.add_party(env.member("cso"), ind.pk, **person("Second"))
        jc = make(env, data=joint())
        out = cs.add_party(env.member("cso"), jc.pk, **person("C Three", "joint_holder"))
        assert out.links.count() == 3
        with pytest.raises(LedgerError) as e:
            cs.add_party(env.member("cso"), jc.pk, **person("D", "signatory"))
        assert e.value.code == "invalid_relation"
        with pytest.raises(LedgerError) as e:
            cs.add_party(
                env.member("cso"), jc.pk, **person("E", "joint_holder", identity_documents=[])
            )
        assert e.value.code == "document_required"

    def test_existing_party_link_and_duplicate(self, env):
        co = make(env, data=company())
        party = co.links.get(relation="director").party
        cs.add_party(env.member("cso"), co.pk, relation="signatory", party_id=party.pk)
        with pytest.raises(LedgerError) as e:
            cs.add_party(env.member("cso"), co.pk, relation="signatory", party_id=party.pk)
        assert e.value.status == 409

    def test_can_sign_toggle_keeps_one_signatory(self, env):
        co = make(env, data=company())
        sig = co.links.get(relation="signatory").party
        with pytest.raises(LedgerError) as e:
            cs.update_party(env.member("cso"), co.pk, sig.pk, can_sign=False)
        assert e.value.code == "invalid_parties"
        dire = co.links.get(relation="director").party
        cs.update_party(env.member("cso"), co.pk, dire.pk, can_sign=True, phone="0611000111")
        cs.update_party(env.member("cso"), co.pk, sig.pk, can_sign=False)
        assert Party.objects.get(pk=dire.pk).phone == "0611000111"

    def test_party_update_audited(self, env):
        c = make(env)
        pid = c.links.get().party_id
        cs.update_party(env.member("cso"), c.pk, pid, full_name="Amina Y. Ali")
        row = AuditLog.objects.get(action="customer.party_updated")
        assert row.before["full_name"] == "Amina Ali" and row.after["full_name"] == "Amina Y. Ali"

    def test_documents_and_kin(self, env):
        c = make(env)
        pid = c.links.get().party_id
        out = cs.add_document(env.member("cso"), c.pk, pid, **doc("P1", type="passport"))
        assert out.links.get().party.documents.count() == 2
        d = IdentityDocument.objects.get(number="P1")
        cs.update_document(env.member("cso"), c.pk, pid, d.pk, expiry_date=date(2040, 1, 1))
        with pytest.raises(LedgerError, match="Expiry date"):
            cs.update_document(env.member("cso"), c.pk, pid, d.pk, expiry_date=date(2000, 1, 1))
        cs.add_next_of_kin(
            env.member("cso"), c.pk, pid, name="Mum", phone="", relationship="Mother"
        )
        kin = c.links.get().party.next_of_kin.get(name="Mum")
        cs.update_next_of_kin(env.member("cso"), c.pk, pid, kin.pk, phone="0611999888")
        actions = set(AuditLog.objects.values_list("action", flat=True))
        assert {
            "customer.document_added",
            "customer.document_updated",
            "customer.next_of_kin_added",
            "customer.next_of_kin_updated",
        } <= actions
        with pytest.raises(LedgerError) as e:  # a document of another party
            cs.update_document(env.member("cso"), c.pk, uuid.uuid4(), d.pk, number="X")
        assert e.value.status == 404

    def test_no_delete(self, env):
        c = make(env)
        with pytest.raises(NotImplementedError):
            c.delete()
        with pytest.raises(NotImplementedError):
            Customer.objects.all().delete()
        r = api(env.user("manager")).delete(env.url(f"/{c.pk}"))
        assert r.status_code == 405

    def test_no_ledger_entries(self, env):
        make(env)
        assert not JournalEntry.objects.filter(source_type__startswith="customer").exists()


# ---------------------------------------------------------------------------- permissions


@pytest.mark.django_db
class TestPermissions:
    def test_matrix(self, env):
        c = make(env, "cso")
        # create / update: cso, manager only
        for key in ("teller", "accountant", "vault"):
            with pytest.raises(rbac.PermissionDenied):
                make(env, key)
            with pytest.raises(rbac.PermissionDenied):
                cs.update_customer(env.member(key), c.pk, phone="0611111111")
        make(env, "manager")
        # view: all but vault custodian
        for key in ("teller", "cso", "manager", "accountant"):
            assert cs.list_customers(env.member(key)).exists() or key == "teller"
        with pytest.raises(rbac.PermissionDenied):
            cs.list_customers(env.member("vault"))
        with pytest.raises(rbac.PermissionDenied):
            cs.get_customer(env.member("vault"), c.pk)

    def test_api_permissions(self, env):
        c = cust_json(api(env.user("cso")), env)
        for key, code in (("teller", 403), ("accountant", 403), ("vault", 403)):
            assert (
                j(api(env.user(key)), "post", env.url(), _jsonable(individual())).status_code
                == code
            )
        assert (
            j(
                api(env.user("teller")), "patch", env.url(f"/{c['id']}"), {"phone": "0611111111"}
            ).status_code
            == 403
        )
        assert api(env.user("vault")).get(env.url()).status_code == 403
        assert api(env.user("accountant")).get(env.url()).status_code == 200
        assert api(env.world["studs"][2]).get(env.url()).status_code == 403  # unplaced/no role

    def test_override_revokes(self, env):
        make(env)
        lab.set_permission_override(
            env.world["ia"], env.session.pk, "cso", "customer.create", False
        )
        with pytest.raises(rbac.PermissionDenied):
            make(env)

    def test_api_flow_and_shapes(self, env):
        client = api(env.user("cso"))
        c = cust_json(client, env, ngo())
        assert c["cif_no"] == 1 and c["type"] == "ngo" and len(c["parties"]) == 2
        p = c["parties"][0]
        assert p["identity_documents"][0]["has_file"] is False and p["has_photo"] is False
        assert p["next_of_kin"][0]["relationship"] == "Father"
        r = j(client, "patch", env.url(f"/{c['id']}"), {"phone": "0611000000"})
        assert r.status_code == 200 and r.json()["phone"] == "0611000000"
        r = j(client, "post", env.url(f"/{c['id']}/parties"), _jsonable(person("New", "signatory")))
        assert r.status_code == 200 and len(r.json()["parties"]) == 3
        r = j(
            client,
            "post",
            env.url(f"/{c['id']}/parties/{p['party_id']}/documents"),
            _jsonable(doc("Z9", type="passport")),
        )
        assert r.status_code == 200
        bad = _jsonable(doc("Z9", issue=date(2030, 1, 1), expiry=date(2020, 1, 1)))
        assert (
            j(
                client, "post", env.url(f"/{c['id']}/parties/{p['party_id']}/documents"), bad
            ).status_code
            == 400
        )
        r = j(
            client,
            "post",
            env.url(f"/{c['id']}/parties/{p['party_id']}/next-of-kin"),
            {"name": "K", "relationship": "Uncle"},
        )
        assert r.status_code == 200
        r = j(
            client, "patch", env.url(f"/{c['id']}/parties/{p['party_id']}"), {"phone": "0699999999"}
        )
        assert r.status_code == 200
        r = client.get(env.url(f"?q={c['cif_no']}&type=ngo"))
        assert r.json()["count"] == 1 and r.json()["items"][0]["id"] == c["id"]
        assert client.get(env.url("?q=zzz")).json()["count"] == 0
        assert client.get(env.url("?type=bogus")).status_code == 400


# ---------------------------------------------------------------------------- visibility


@pytest.mark.django_db
class TestVisibility:
    def test_own_mode(self, world):
        env = Env(world, default_visibility="own")
        mine = make(env, "cso")
        theirs = make(env, "cso2")
        shared = Customer.objects.create(
            bank=env.bank, cif_no=90, type="individual", display_name="Seed Shared", is_seed=True
        )
        own_seed = Customer.objects.create(
            bank=env.bank,
            cif_no=91,
            type="individual",
            display_name="Seed Mine",
            is_seed=True,
            seed_owner=env.member("cso"),
        )
        other_seed = Customer.objects.create(
            bank=env.bank,
            cif_no=92,
            type="individual",
            display_name="Seed Other",
            is_seed=True,
            seed_owner=env.member("cso2"),
        )
        seen = {c.pk for c in cs.list_customers(env.member("cso"))}
        assert seen == {mine.pk, shared.pk, own_seed.pk}
        assert {c.pk for c in cs.list_customers(env.member("cso2"))} == {
            theirs.pk,
            shared.pk,
            other_seed.pk,
        }
        for hidden in (theirs, other_seed):
            with pytest.raises(LedgerError) as e:
                cs.get_customer(env.member("cso"), hidden.pk)
            assert e.value.status == 404
            with pytest.raises(LedgerError) as e:
                cs.update_customer(env.member("cso"), hidden.pk, phone="0611111111")
            assert e.value.status == 404
        # teller (own) sees only shared seed; whole-bank roles see everything
        assert {c.pk for c in cs.list_customers(env.member("teller"))} == {shared.pk}
        for key in ("manager", "accountant"):
            assert cs.list_customers(env.member(key)).count() == 5
        assert api(env.user("cso")).get(env.url(f"/{theirs.pk}")).status_code == 404
        assert api(env.user("manager")).get(env.url(f"/{theirs.pk}")).status_code == 200

    def test_session_default_all(self, world):
        env = Env(world, default_visibility="all")
        a, b = make(env, "cso"), make(env, "cso2")
        assert {c.pk for c in cs.list_customers(env.member("teller"))} == {a.pk, b.pk}

    def test_member_override_own(self, world):
        env = Env(world, default_visibility="all")
        a, b = make(env, "cso"), make(env, "cso2")
        lab.set_visibility_override(world["ia"], env.session.pk, env.member("cso").pk, "own")
        member = SessionMember.objects.get(pk=env.member("cso").pk)
        assert {c.pk for c in cs.list_customers(member)} == {a.pk}
        assert b.pk

    def test_exam_forces_own(self, world):
        env = Env(world, kind="exam", default_visibility="all")
        mine = make(env, "cso")
        make(env, "cso2")
        assert {c.pk for c in cs.list_customers(env.member("cso"))} == {mine.pk}
        assert cs.list_customers(env.member("manager")).count() == 0  # exams force own for all

    def test_instructor_reads_all_own_classes_only(self, world):
        env = Env(world, default_visibility="own")
        c = make(env, "cso")
        make(env, "cso2")
        base = f"/api/sessions/{env.session.pk}/banks/{env.bank.pk}/customers"
        ia = api(world["ia"])
        assert ia.get(base).json()["count"] == 2
        assert ia.get(f"{base}/{c.pk}").status_code == 200
        ib = api(world["ib"])
        assert ib.get(base).status_code == 404
        assert ib.get(f"{base}/{c.pk}").status_code == 404
        assert api(env.user("cso")).get(base).status_code == 403


# ---------------------------------------------------------------------------- isolation


@pytest.mark.django_db
class TestIsolation:
    def test_cross_bank_and_cross_session(self, world):
        env = Env(world, "a", structure="per_group", default_visibility="all")
        bank2 = Bank.objects.get(session=env.session, group_no=2)
        cso2 = add_person(world, env.session, bank2, "cso2b", "cso")
        c1 = make(env, "cso")
        other_session = Env(world, "z", default_visibility="all")
        c3 = make(other_session, "cso")
        # bank 2 staff: list is empty, detail/update/add/party/file of bank 1 -> 404
        client = api(cso2[0])
        sid = env.session.pk
        assert client.get(f"/api/s/{sid}/customers").json()["count"] == 0
        pid = c1.links.get().party_id
        for method, path, body in (
            ("get", f"/{c1.pk}", None),
            ("patch", f"/{c1.pk}", {"phone": "0611111111"}),
            ("post", f"/{c1.pk}/parties", _jsonable(person("X", "owner"))),
            ("patch", f"/{c1.pk}/parties/{pid}", {"phone": "0611111111"}),
            ("post", f"/{c1.pk}/parties/{pid}/documents", _jsonable(doc())),
            ("get", f"/{c1.pk}/parties/{pid}/photo", None),
        ):
            r = (
                client.get(f"/api/s/{sid}/customers{path}")
                if method == "get"
                else j(client, method, f"/api/s/{sid}/customers{path}", body)
            )
            assert r.status_code == 404, (method, path)
        # another session's customer is not reachable through this session either
        assert client.get(f"/api/s/{sid}/customers/{c3.pk}").status_code == 404
        assert api(cso2[0]).get(f"/api/s/{other_session.session.pk}/customers").status_code == 403
        # service level: foreign party cannot be linked
        with pytest.raises(LedgerError) as e:
            cs.add_party(
                cso2[1],
                make(Env.__new__(Env) if False else env, "cso").pk,
                relation="owner",
                party_id=pid,
            )
        assert e.value.status in (400, 404)
        # an existing party of ANOTHER bank cannot be attached
        foreign_c = cs.create_customer(cso2[1], **joint())
        with pytest.raises(LedgerError) as e:
            cs.add_party(cso2[1], foreign_c.pk, relation="joint_holder", party_id=pid)
        assert e.value.status == 404

    def test_cif_sequence_per_bank(self, world):
        env = Env(world, structure="per_group")
        bank2 = Bank.objects.get(session=env.session, group_no=2)
        cso2 = add_person(world, env.session, bank2, "cso2c", "cso")
        assert [make(env).cif_no for _ in range(3)] == [1, 2, 3]
        assert cs.create_customer(cso2[1], **individual()).cif_no == 1
        assert make(env).cif_no == 4
        with pytest.raises(Exception):  # noqa: B017
            from django.db import IntegrityError, transaction

            with transaction.atomic():
                Customer.objects.create(
                    bank=env.bank, cif_no=1, type="individual", display_name="dup"
                )
        assert IntegrityError  # unique (bank, cif_no) is enforced by the database


# ---------------------------------------------------------------------------- archived


@pytest.mark.django_db
class TestArchived:
    def test_read_only(self, env):
        c = make(env)
        pid = c.links.get().party_id
        lab.archive_session(env.world["ia"], env.session.pk)
        m = env.member("cso")
        with pytest.raises(LedgerError) as e:
            make(env)
        assert e.value.code == "session_archived"
        with pytest.raises(LedgerError):
            cs.update_customer(m, c.pk, phone="0611111111")
        with pytest.raises(LedgerError):
            cs.add_document(m, c.pk, pid, **doc())
        client = api(env.user("cso"))
        assert j(client, "post", env.url(), _jsonable(individual())).status_code == 409
        assert j(client, "patch", env.url(f"/{c.pk}"), {"phone": "0611111111"}).status_code == 409
        # reads stay available
        assert client.get(env.url()).json()["count"] == 1
        assert client.get(env.url(f"/{c.pk}")).status_code == 200
        assert Customer.objects.get(pk=c.pk).phone == ""


# ---------------------------------------------------------------------------- files


@pytest.mark.django_db
class TestFiles:
    def setup_customer(self, env):
        c = make(env, "cso")
        return c, c.links.get().party_id

    def test_photo_signature_document_roundtrip(self, env):
        c, pid = self.setup_customer(env)
        client = api(env.user("cso"))
        base = env.url(f"/{c.pk}/parties/{pid}")
        r = client.post(
            f"{base}/photo", {"file": SimpleUploadedFile("evil.php", PNG, "text/plain")}
        )
        assert r.status_code == 200 and r.json()["parties"][0]["has_photo"] is True
        r = client.post(f"{base}/signature", {"file": SimpleUploadedFile("s.jpg", JPG)})
        assert r.json()["parties"][0]["has_signature"] is True
        did = IdentityDocument.objects.get(party_id=pid).pk
        r = client.post(
            f"{base}/documents/{did}/file", {"file": SimpleUploadedFile("scan.pdf", PDF)}
        )
        assert r.status_code == 200 and r.json()["parties"][0]["identity_documents"][0]["has_file"]
        got = api(env.user("manager")).get(f"{base}/photo")
        assert got.status_code == 200 and got["Content-Type"] == "image/png"
        assert b"".join(got.streaming_content) == PNG
        assert got["X-Content-Type-Options"] == "nosniff"
        pdf = api(env.user("accountant")).get(f"{base}/documents/{did}/file")
        assert pdf["Content-Type"] == "application/pdf"
        assert AuditLog.objects.filter(action="customer.party_photo_uploaded").exists()

    def test_validation(self, env, settings):
        c, pid = self.setup_customer(env)
        client = api(env.user("cso"))
        base = env.url(f"/{c.pk}/parties/{pid}")
        r = client.post(f"{base}/photo", {"file": SimpleUploadedFile("a.png", b"GIF89a....")})
        assert r.status_code == 415
        r = client.post(f"{base}/photo", {"file": SimpleUploadedFile("a.pdf", PDF)})
        assert r.status_code == 415  # a PDF is not a photo
        settings.MAX_UPLOAD_BYTES = 10
        r = client.post(f"{base}/photo", {"file": SimpleUploadedFile("a.png", PNG)})
        assert r.status_code == 413
        assert (
            client.post(f"{base}/passport", {"file": SimpleUploadedFile("a.png", PNG)}).status_code
            == 404
        )
        assert Party.objects.get(pk=pid).photo.name == ""

    def test_permissions_and_visibility(self, world):
        env = Env(world, default_visibility="own")
        c = make(env, "cso")
        pid = c.links.get().party_id
        base = env.url(f"/{c.pk}/parties/{pid}")
        png = lambda: {"file": SimpleUploadedFile("a.png", PNG)}  # noqa: E731
        assert api(env.user("teller")).post(f"{base}/photo", png()).status_code == 403
        assert api(env.user("cso2")).post(f"{base}/photo", png()).status_code == 404
        assert api(env.user("cso")).post(f"{base}/photo", png()).status_code == 200
        assert api(env.user("cso2")).get(f"{base}/photo").status_code == 404  # not their customer
        assert api(env.user("teller")).get(f"{base}/photo").status_code == 404
        assert api(env.user("vault")).get(f"{base}/photo").status_code == 403
        assert api(env.user("manager")).get(f"{base}/photo").status_code == 200
        assert api(env.user("manager")).get(f"{base}/signature").status_code == 404  # none yet

    def test_archived_upload_refused(self, env):
        c, pid = self.setup_customer(env)
        lab.archive_session(env.world["ia"], env.session.pk)
        r = api(env.user("cso")).post(
            env.url(f"/{c.pk}/parties/{pid}/photo"), {"file": SimpleUploadedFile("a.png", PNG)}
        )
        assert r.status_code == 409


# ---------------------------------------------------------------------------- concurrency


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
class TestConcurrency:
    def test_parallel_creates_get_distinct_cif_numbers(self, world):
        import threading

        env = Env(world)
        results, errors = [], []

        def run():
            try:
                results.append(make(env, "cso").cif_no)
            except Exception as exc:  # pragma: no cover - surfaced below
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=run) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not errors, errors
        assert sorted(results) == [1, 2, 3, 4, 5]
        assert CustomerParty.objects.count() == 5
        assert SessionMember.objects.filter(pk=env.member("cso").pk).exists()


# ---------------------------------------------------------------------------- review fixes


def share_party(env, owner_key, other_key):
    """Customer A (owner_key) and B (other_key, company) share one person."""
    a = make(env, owner_key, company())
    b = make(env, other_key, company())
    party = b.links.get(relation="signatory").party
    CustomerParty.objects.create(
        bank=env.bank, customer=a, party=party, relation="director", can_sign=False
    )
    return a, b, party


@pytest.mark.django_db
class TestSharedParties:
    def test_cannot_attach_party_of_invisible_customer(self, world):
        env = Env(world, default_visibility="own")
        b = make(env, "cso2", company())
        foreign = b.links.get(relation="signatory").party
        a = make(env, "cso", company())
        with pytest.raises(LedgerError) as e:
            cs.add_party(env.member("cso"), a.pk, relation="director", party_id=foreign.pk)
        assert e.value.status == 404
        assert a.links.count() == 2

    def test_edit_blocked_when_party_shared_with_invisible_customer(self, world):
        env = Env(world, default_visibility="own")
        a, _, party = share_party(env, "cso", "cso2")
        m = env.member("cso")
        calls = (
            lambda: cs.update_party(m, a.pk, party.pk, phone="0611000111"),
            lambda: cs.add_document(m, a.pk, party.pk, **doc("S1")),
            lambda: cs.add_next_of_kin(m, a.pk, party.pk, name="K", relationship="Aunt"),
            lambda: cs.upload_party_file(
                m, a.pk, party.pk, "photo", SimpleUploadedFile("a.png", PNG)
            ),
        )
        for call in calls:
            with pytest.raises(LedgerError) as e:
                call()
            assert e.value.code == "party_shared" and e.value.status == 409
        assert Party.objects.get(pk=party.pk).phone != "0611000111"

    def test_edit_allowed_when_all_visible_and_audited_on_each(self, world):
        env = Env(world, default_visibility="all")
        a, b, party = share_party(env, "cso", "cso2")
        cs.update_party(env.member("cso"), a.pk, party.pk, phone="0611000111")
        rows = AuditLog.objects.filter(action="customer.shared_party_changed")
        assert [r.entity_id for r in rows] == [str(b.pk)]

    def test_failed_upload_leaves_no_orphan_file(self, env, settings, monkeypatch):
        c = make(env, "cso")
        pid = c.links.get().party_id
        monkeypatch.setattr(cs, "_reload", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
        with pytest.raises(RuntimeError):
            cs.upload_party_file(
                env.member("cso"), c.pk, pid, "photo", SimpleUploadedFile("a.png", PNG)
            )
        assert not [p for p in settings.MEDIA_ROOT.rglob("*") if p.is_file()]
        assert Party.objects.get(pk=pid).photo.name == ""
