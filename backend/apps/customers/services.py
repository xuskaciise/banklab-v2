"""Customers (CIF): customers, the people behind them (parties), ID documents, next of kin.

Every function takes the acting `SessionMember` (student routes) or a staff `User`
(instructor read-only). Role permission, row visibility and the archived-session guard are
enforced here on the server; nothing is ever deleted and every write is audited.

Lock order: session -> customer row (or bank row for CIF numbering).
"""

import re
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Max, Q

from apps.accounts.models import User
from apps.audit import services as audit
from apps.banking.services import _lock_session, _require, _role_of
from apps.lab import services as lab
from apps.lab.models import Bank, Session, SessionMember
from apps.ledger.services import LedgerError
from apps.rbac import context as rbac_context
from apps.rbac import services as rbac

from .models import (
    Customer,
    CustomerParty,
    CustomerType,
    DocType,
    IdentityDocument,
    NextOfKin,
    Party,
    Relation,
    Sex,
)

PERM_VIEW = "customer.view"
PERM_CREATE = "customer.create"
PERM_UPDATE = "customer.update"

ALLOWED_RELATIONS = {
    CustomerType.INDIVIDUAL: {Relation.OWNER},
    CustomerType.JOINT: {Relation.JOINT_HOLDER},
    CustomerType.COMPANY: {Relation.SIGNATORY, Relation.DIRECTOR},
    CustomerType.NGO: {Relation.SIGNATORY, Relation.DIRECTOR},
}
ORGANISATIONS = {CustomerType.COMPANY, CustomerType.NGO}
PHONE_RE = re.compile(r"^[0-9+\-\s()]{5,30}$")

# Uploads: type is sniffed from the bytes, never taken from the client's name or header.
IMAGE_SIGNATURES = {b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}
PDF_SIGNATURE = b"%PDF-"
CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "pdf": "application/pdf"}


def content_type_of(name: str) -> str:
    return CONTENT_TYPES.get(name.rsplit(".", 1)[-1].lower(), "application/octet-stream")


def _bad(message: str, code: str = "invalid_customer") -> LedgerError:
    return LedgerError(code, message, status=400)


def _not_found(what: str = "Customer") -> LedgerError:
    return LedgerError("not_found", f"{what} not found", status=404)


# --------------------------------------------------------------------------- validation


def _text(value, what: str, max_len: int, *, required: bool = True) -> str:
    value = (value or "").strip()
    if required and not value:
        raise _bad(f"{what} is required")
    if len(value) > max_len:
        raise _bad(f"{what} is longer than {max_len} characters")
    return value


def _phone(value, what: str = "Phone") -> str:
    value = _text(value, what, 30, required=False)
    if value and not PHONE_RE.match(value):
        raise _bad(f"{what} is not a valid phone number")
    return value


def _email(value) -> str:
    value = _text(value, "Email", 254, required=False)
    if value:
        try:
            validate_email(value)
        except ValidationError:
            raise _bad("Email is not valid") from None
    return value


def _choice(value, enum, what: str):
    if value not in enum.values:
        raise _bad(f"{what} must be one of: {', '.join(enum.values)}")
    return value


def _clean_party(data: dict) -> dict:
    sex = data.get("sex") or ""
    if sex:
        _choice(sex, Sex, "Sex")
    dob = data.get("date_of_birth")
    if dob is not None and dob >= date.today():
        raise _bad("Date of birth must be in the past")
    return {
        "full_name": _text(data.get("full_name"), "Full name", 200),
        "sex": sex,
        "date_of_birth": dob,
        "phone": _phone(data.get("phone")),
    }


def _clean_document(data: dict) -> dict:
    issue, expiry = data.get("issue_date"), data.get("expiry_date")
    if issue is None or expiry is None:
        raise _bad("Issue date and expiry date are required")
    if expiry <= issue:
        raise _bad("Expiry date must be after the issue date")
    return {
        "type": _choice(data.get("type"), DocType, "Document type"),
        "number": _text(data.get("number"), "Document number", 60),
        "issue_date": issue,
        "expiry_date": expiry,
    }


def _clean_kin(data: dict) -> dict:
    return {
        "name": _text(data.get("name"), "Next of kin name", 200),
        "phone": _phone(data.get("phone"), "Next of kin phone"),
        "relationship": _text(data.get("relationship"), "Relationship", 60),
    }


def _default_can_sign(relation: str, can_sign) -> bool:
    if relation in (Relation.OWNER, Relation.JOINT_HOLDER):
        return True
    if can_sign is None:
        return relation == Relation.SIGNATORY
    return bool(can_sign)


def _check_structure(ctype: str, reg_no: str, links: list[tuple[str, bool]]) -> None:
    """Customer-type rules over the full set of (relation, can_sign) pairs."""
    allowed = ALLOWED_RELATIONS[ctype]
    if any(r not in allowed for r, _ in links):
        raise _bad(
            f"A {ctype} customer only allows: {', '.join(sorted(allowed))}", "invalid_relation"
        )
    if ctype == CustomerType.INDIVIDUAL and len(links) != 1:
        raise _bad("An individual customer has exactly one owner", "invalid_parties")
    if ctype == CustomerType.JOINT and len(links) < 2:
        raise _bad("A joint customer needs at least two joint holders", "invalid_parties")
    if ctype in ORGANISATIONS:
        if not reg_no:
            raise _bad("Registration number is required", "reg_no_required")
        if not any(can_sign for _, can_sign in links):
            raise _bad("At least one signatory who can sign is required", "invalid_parties")


# --------------------------------------------------------------------------- access


def _audit(member, role, action, session, customer, *, before=None, after=None):
    audit.record(
        action,
        actor=member.user,
        actor_role=role,
        entity=("customer", customer.pk),
        before=before,
        after=after,
        session_id=session.pk,
        bank_id=customer.bank_id,
        institution_id=session.lab_class.institution_id,
    )


def _read_scope(member: SessionMember, code: str):
    """(session, role, scope) for a read; archived sessions stay readable."""
    if member.bank_id is None:
        raise rbac.PermissionDenied("Not allowed")
    session = Session.objects.select_related("lab_class").get(pk=member.session_id)
    role = _role_of(member)
    scope = rbac.permission_scope(role, code, session=session)
    if scope is None:
        raise rbac.PermissionDenied("Not allowed")
    visibility = rbac_context.effective_visibility(session, member, role)
    return session, role, "own" if "own" in (scope, visibility) else "all"


def _visible(member: SessionMember, scope: str):
    """Customers of the member's bank; "own" scope: own work + shared / own seed data."""
    qs = Customer.objects.filter(bank_id=member.bank_id)
    if scope == "own":
        qs = qs.filter(
            Q(created_by=member) | Q(seed_owner=member) | Q(is_seed=True, seed_owner__isnull=True)
        )
    return qs


def _filtered(qs, q=None, ctype=None):
    if ctype:
        qs = qs.filter(type=_choice(ctype, CustomerType, "Type"))
    q = (q or "").strip()
    if q:
        cond = Q(display_name__icontains=q) | Q(phone__icontains=q)
        if q.isdigit() and len(q) <= 9:
            cond |= Q(cif_no=int(q))
        qs = qs.filter(cond)
    return qs


def _detail_qs(qs):
    return qs.prefetch_related("links__party__documents", "links__party__next_of_kin")


def _write_ctx(member: SessionMember, code: str):
    """Inside the write transaction: locked session, role, permission, visible scope."""
    session = _lock_session(member)
    role = _role_of(member)
    _require(role, code, session)
    visibility = rbac_context.effective_visibility(session, member, role)
    scope = rbac.permission_scope(role, code, session=session)
    return session, role, "own" if "own" in (scope, visibility) else "all"


def _locked_customer(member, scope, customer_id) -> Customer:
    customer = (
        _visible(member, scope).select_for_update(of=("self",)).filter(pk=customer_id).first()
    )
    if customer is None:
        raise _not_found()
    return customer


def _link_or_404(customer: Customer, party_id) -> list[CustomerParty]:
    links = list(CustomerParty.objects.filter(customer=customer, party_id=party_id))
    if not links:
        raise _not_found("Party")
    return links


def _guard_shared(member, scope, session, role, customer, party_id) -> None:
    """A person shared by several customers: refuse the edit when any other linked customer
    is invisible to the caller; otherwise audit the change on each other customer too."""
    others = list(
        Customer.objects.filter(bank_id=member.bank_id, links__party_id=party_id)
        .exclude(pk=customer.pk)
        .distinct()
    )
    if not others:
        return
    visible = set(
        _visible(member, scope).filter(pk__in=[o.pk for o in others]).values_list("pk", flat=True)
    )
    if any(o.pk not in visible for o in others):
        raise LedgerError(
            "party_shared", "This person is also linked to a customer you cannot see", 409
        )
    for other in others:
        _audit(
            member,
            role,
            "customer.shared_party_changed",
            session,
            other,
            after={"party_id": str(party_id), "via_customer_id": str(customer.pk)},
        )


def _customer_dict(c: Customer) -> dict:
    return {
        "cif_no": c.cif_no,
        "type": c.type,
        "display_name": c.display_name,
        "phone": c.phone,
        "email": c.email,
        "address": c.address,
        "reg_no": c.reg_no,
    }


def _party_dict(p: Party) -> dict:
    return {
        "full_name": p.full_name,
        "sex": p.sex,
        "date_of_birth": p.date_of_birth.isoformat() if p.date_of_birth else None,
        "phone": p.phone,
        "has_photo": bool(p.photo),
        "has_signature": bool(p.signature),
    }


def _doc_dict(d: IdentityDocument) -> dict:
    return {
        "type": d.type,
        "number": d.number,
        "issue_date": d.issue_date.isoformat(),
        "expiry_date": d.expiry_date.isoformat(),
        "has_file": bool(d.file),
    }


def _kin_dict(k: NextOfKin) -> dict:
    return {"name": k.name, "phone": k.phone, "relationship": k.relationship}


# --------------------------------------------------------------------------- reads


def list_customers(member: SessionMember, *, q=None, type=None):
    _, _, scope = _read_scope(member, PERM_VIEW)
    return _detail_qs(_filtered(_visible(member, scope), q, type)).order_by("cif_no")


def get_customer(member: SessionMember, customer_id) -> Customer:
    _, _, scope = _read_scope(member, PERM_VIEW)
    customer = _detail_qs(_visible(member, scope)).filter(pk=customer_id).first()
    if customer is None:
        raise _not_found()
    return customer


def _staff_bank(actor: User, session_id, bank_id) -> Bank:
    session = lab.get_session(actor, session_id)
    bank = Bank.objects.filter(pk=bank_id, session=session).first()
    if bank is None:
        raise lab.NotFound("Bank not found in this session")
    return bank


def staff_list_customers(actor: User, session_id, bank_id, *, q=None, type=None):
    bank = _staff_bank(actor, session_id, bank_id)
    return _detail_qs(_filtered(Customer.objects.filter(bank=bank), q, type)).order_by("cif_no")


def staff_get_customer(actor: User, session_id, bank_id, customer_id) -> Customer:
    bank = _staff_bank(actor, session_id, bank_id)
    customer = _detail_qs(Customer.objects.filter(bank=bank)).filter(pk=customer_id).first()
    if customer is None:
        raise _not_found()
    return customer


def _reload(member, scope, customer_id) -> Customer:
    return _detail_qs(_visible(member, scope)).get(pk=customer_id)


# --------------------------------------------------------------------------- writes


def _next_cif_no(bank_id) -> int:
    """Sequential per bank; the bank row lock serialises concurrent creates."""
    Bank.objects.select_for_update(of=("self",)).get(pk=bank_id)
    current = Customer.objects.filter(bank_id=bank_id).aggregate(m=Max("cif_no"))["m"]
    return (current or 0) + 1


def _create_party_rows(bank_id, data: dict, clean: dict) -> Party:
    docs = data.get("identity_documents") or []
    if not docs:
        raise _bad("Every person needs at least one identity document", "document_required")
    cleaned_docs = [_clean_document(d) for d in docs]
    cleaned_kin = [_clean_kin(k) for k in data.get("next_of_kin") or []]
    party = Party.objects.create(bank_id=bank_id, **clean)
    for doc in cleaned_docs:
        IdentityDocument.objects.create(bank_id=bank_id, party=party, **doc)
    for kin in cleaned_kin:
        NextOfKin.objects.create(bank_id=bank_id, party=party, **kin)
    return party


def create_customer(
    member: SessionMember,
    *,
    type,
    display_name="",
    phone="",
    email="",
    address="",
    reg_no="",
    parties,
) -> Customer:
    """Create a customer with its people, ID documents and next of kin in one transaction."""
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_CREATE)
        ctype = _choice(type, CustomerType, "Type")
        reg_no = _text(reg_no, "Registration number", 60, required=False)
        if reg_no and ctype not in ORGANISATIONS:
            raise _bad("Registration number only applies to companies and NGOs")
        cleaned = []
        for data in parties:
            relation = _choice(data.get("relation"), Relation, "Relation")
            can_sign = _default_can_sign(relation, data.get("can_sign"))
            cleaned.append((data, relation, can_sign, _clean_party(data)))
        _check_structure(ctype, reg_no, [(r, s) for _, r, s, _ in cleaned])
        name = _text(display_name, "Display name", 200, required=False)
        if not name and ctype == CustomerType.INDIVIDUAL:
            name = cleaned[0][3]["full_name"]
        if not name:
            raise _bad("Display name is required")
        bank_id = member.bank_id
        customer = Customer.objects.create(
            bank_id=bank_id,
            cif_no=_next_cif_no(bank_id),
            type=ctype,
            display_name=name,
            phone=_phone(phone),
            email=_email(email),
            address=_text(address, "Address", 300, required=False),
            reg_no=reg_no,
            created_by=member,
        )
        for data, relation, can_sign, clean in cleaned:
            party = _create_party_rows(bank_id, data, clean)
            CustomerParty.objects.create(
                bank_id=bank_id,
                customer=customer,
                party=party,
                relation=relation,
                can_sign=can_sign,
            )
        _audit(
            member,
            role,
            "customer.created",
            session,
            customer,
            after={**_customer_dict(customer), "parties": len(cleaned)},
        )
        return _reload(member, scope, customer.pk)


def update_customer(member: SessionMember, customer_id, **fields) -> Customer:
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        before = _customer_dict(customer)
        if "display_name" in fields:
            customer.display_name = _text(fields["display_name"], "Display name", 200)
        if "phone" in fields:
            customer.phone = _phone(fields["phone"])
        if "email" in fields:
            customer.email = _email(fields["email"])
        if "address" in fields:
            customer.address = _text(fields["address"], "Address", 300, required=False)
        if "reg_no" in fields:
            reg_no = _text(fields["reg_no"], "Registration number", 60, required=False)
            if customer.type in ORGANISATIONS and not reg_no:
                raise _bad("Registration number is required", "reg_no_required")
            if customer.type not in ORGANISATIONS and reg_no:
                raise _bad("Registration number only applies to companies and NGOs")
            customer.reg_no = reg_no
        customer.save()
        _audit(
            member,
            role,
            "customer.updated",
            session,
            customer,
            before=before,
            after=_customer_dict(customer),
        )
        return _reload(member, scope, customer.pk)


def add_party(
    member: SessionMember,
    customer_id,
    *,
    relation,
    can_sign=None,
    party_id=None,
    **party_data,
) -> Customer:
    """Link a new person (with ID documents) or an existing person of this bank."""
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        relation = _choice(relation, Relation, "Relation")
        can_sign = _default_can_sign(relation, can_sign)
        if customer.type == CustomerType.INDIVIDUAL:
            raise _bad("An individual customer has exactly one owner", "invalid_parties")
        existing = list(customer.links.values_list("relation", "can_sign"))
        _check_structure(customer.type, customer.reg_no, existing + [(relation, can_sign)])
        if party_id is not None:
            party = (
                Party.objects.filter(
                    pk=party_id,
                    bank_id=member.bank_id,
                    links__customer__in=_visible(member, scope),
                )
                .distinct()
                .first()
            )
            if party is None:
                raise _not_found("Party")
            if CustomerParty.objects.filter(
                customer=customer, party=party, relation=relation
            ).exists():
                raise LedgerError("duplicate_party", "Person already has this relation", 409)
        else:
            party = _create_party_rows(member.bank_id, party_data, _clean_party(party_data))
        CustomerParty.objects.create(
            bank_id=member.bank_id,
            customer=customer,
            party=party,
            relation=relation,
            can_sign=can_sign,
        )
        _audit(
            member,
            role,
            "customer.party_added",
            session,
            customer,
            after={"party_id": str(party.pk), "relation": relation, "can_sign": can_sign},
        )
        return _reload(member, scope, customer.pk)


def update_party(member: SessionMember, customer_id, party_id, **fields) -> Customer:
    """Update the person's details and/or the can_sign flag on this customer's link."""
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        links = _link_or_404(customer, party_id)
        _guard_shared(member, scope, session, role, customer, party_id)
        party = Party.objects.select_for_update(of=("self",)).get(pk=party_id)
        before = {**_party_dict(party), "can_sign": [link.can_sign for link in links]}
        merged = {
            "full_name": party.full_name,
            "sex": party.sex,
            "date_of_birth": party.date_of_birth,
            "phone": party.phone,
            **{k: v for k, v in fields.items() if k != "can_sign"},
        }
        for key, value in _clean_party(merged).items():
            setattr(party, key, value)
        party.save()
        if fields.get("can_sign") is not None:
            wanted = bool(fields["can_sign"])
            for link in links:
                if link.relation not in (Relation.OWNER, Relation.JOINT_HOLDER):
                    link.can_sign = wanted
            others = customer.links.exclude(party_id=party_id).values_list("relation", "can_sign")
            _check_structure(
                customer.type,
                customer.reg_no,
                list(others) + [(link.relation, link.can_sign) for link in links],
            )
            for link in links:
                link.save(update_fields=["can_sign", "updated_at"])
        _audit(
            member,
            role,
            "customer.party_updated",
            session,
            customer,
            before={"party_id": str(party_id), **before},
            after={
                "party_id": str(party_id),
                **_party_dict(party),
                "can_sign": [link.can_sign for link in links],
            },
        )
        return _reload(member, scope, customer.pk)


def add_document(member: SessionMember, customer_id, party_id, **data) -> Customer:
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        _link_or_404(customer, party_id)
        _guard_shared(member, scope, session, role, customer, party_id)
        doc = IdentityDocument.objects.create(
            bank_id=member.bank_id, party_id=party_id, **_clean_document(data)
        )
        _audit(
            member,
            role,
            "customer.document_added",
            session,
            customer,
            after={"party_id": str(party_id), "document_id": str(doc.pk), **_doc_dict(doc)},
        )
        return _reload(member, scope, customer.pk)


def _locked_document(customer, party_id, doc_id) -> IdentityDocument:
    _link_or_404(customer, party_id)
    doc = (
        IdentityDocument.objects.select_for_update(of=("self",))
        .filter(pk=doc_id, party_id=party_id)
        .first()
    )
    if doc is None:
        raise _not_found("Document")
    return doc


def update_document(member: SessionMember, customer_id, party_id, doc_id, **fields) -> Customer:
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        doc = _locked_document(customer, party_id, doc_id)
        _guard_shared(member, scope, session, role, customer, party_id)
        before = _doc_dict(doc)
        merged = {
            "type": doc.type,
            "number": doc.number,
            "issue_date": doc.issue_date,
            "expiry_date": doc.expiry_date,
            **fields,
        }
        for key, value in _clean_document(merged).items():
            setattr(doc, key, value)
        doc.save()
        _audit(
            member,
            role,
            "customer.document_updated",
            session,
            customer,
            before={"document_id": str(doc.pk), **before},
            after={"document_id": str(doc.pk), **_doc_dict(doc)},
        )
        return _reload(member, scope, customer.pk)


def add_next_of_kin(member: SessionMember, customer_id, party_id, **data) -> Customer:
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        _link_or_404(customer, party_id)
        _guard_shared(member, scope, session, role, customer, party_id)
        kin = NextOfKin.objects.create(
            bank_id=member.bank_id, party_id=party_id, **_clean_kin(data)
        )
        _audit(
            member,
            role,
            "customer.next_of_kin_added",
            session,
            customer,
            after={"party_id": str(party_id), "kin_id": str(kin.pk), **_kin_dict(kin)},
        )
        return _reload(member, scope, customer.pk)


def update_next_of_kin(member: SessionMember, customer_id, party_id, kin_id, **fields) -> Customer:
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        _link_or_404(customer, party_id)
        _guard_shared(member, scope, session, role, customer, party_id)
        kin = (
            NextOfKin.objects.select_for_update(of=("self",))
            .filter(pk=kin_id, party_id=party_id)
            .first()
        )
        if kin is None:
            raise _not_found("Next of kin")
        before = _kin_dict(kin)
        for key, value in _clean_kin({**before, **fields}).items():
            setattr(kin, key, value)
        kin.save()
        _audit(
            member,
            role,
            "customer.next_of_kin_updated",
            session,
            customer,
            before={"kin_id": str(kin.pk), **before},
            after={"kin_id": str(kin.pk), **_kin_dict(kin)},
        )
        return _reload(member, scope, customer.pk)


# --------------------------------------------------------------------------- files


def _sniff(upload, *, allow_pdf: bool) -> str:
    if upload.size > settings.MAX_UPLOAD_BYTES:
        raise LedgerError("file_too_large", "File is larger than 2 MB", status=413)
    head = upload.read(16)
    upload.seek(0)
    for signature, ext in IMAGE_SIGNATURES.items():
        if head.startswith(signature):
            return ext
    if allow_pdf and head.startswith(PDF_SIGNATURE):
        return "pdf"
    allowed = "JPEG, PNG or PDF" if allow_pdf else "JPEG or PNG"
    raise LedgerError("invalid_file_type", f"File must be {allowed}", status=415)


def _upload_party_file(member, customer_id, party_id, kind, upload, saved) -> Customer:
    """Store a party's photo or signature (JPEG/PNG, max 2 MB). Old files stay on disk."""
    if kind not in ("photo", "signature"):
        raise _not_found("File")
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        _link_or_404(customer, party_id)
        _guard_shared(member, scope, session, role, customer, party_id)
        ext = _sniff(upload, allow_pdf=False)
        party = Party.objects.select_for_update(of=("self",)).get(pk=party_id)
        getattr(party, kind).save(f"{kind}.{ext}", upload, save=False)
        saved.append(getattr(party, kind).name)
        party.save(update_fields=[kind, "updated_at"])
        _audit(
            member,
            role,
            f"customer.party_{kind}_uploaded",
            session,
            customer,
            after={"party_id": str(party_id), "size": upload.size, "type": ext},
        )
        return _reload(member, scope, customer.pk)


def _upload_document_file(member, customer_id, party_id, doc_id, upload, saved) -> Customer:
    with transaction.atomic():
        session, role, scope = _write_ctx(member, PERM_UPDATE)
        customer = _locked_customer(member, scope, customer_id)
        doc = _locked_document(customer, party_id, doc_id)
        _guard_shared(member, scope, session, role, customer, party_id)
        ext = _sniff(upload, allow_pdf=True)
        doc.file.save(f"document.{ext}", upload, save=False)
        saved.append(doc.file.name)
        doc.save(update_fields=["file", "updated_at"])
        _audit(
            member,
            role,
            "customer.document_file_uploaded",
            session,
            customer,
            after={"document_id": str(doc.pk), "size": upload.size, "type": ext},
        )
        return _reload(member, scope, customer.pk)


def open_file(member: SessionMember, customer_id, party_id, kind, doc_id=None):
    """FieldFile for a photo, signature or ID document the caller may see (else 404)."""
    _, _, scope = _read_scope(member, PERM_VIEW)
    customer = _visible(member, scope).filter(pk=customer_id).first()
    if customer is None:
        raise _not_found()
    _link_or_404(customer, party_id)
    if kind == "document":
        doc = IdentityDocument.objects.filter(pk=doc_id, party_id=party_id).first()
        field = doc.file if doc else None
    elif kind in ("photo", "signature"):
        field = getattr(Party.objects.get(pk=party_id), kind)
    else:
        field = None
    if not field:
        raise _not_found("File")
    return field


def _remove_saved(saved: list[str]) -> None:
    for name in saved:
        default_storage.delete(name)


def upload_party_file(member: SessionMember, customer_id, party_id, kind, upload) -> Customer:
    """Store a party's photo or signature (JPEG/PNG, max 2 MB). A rollback removes the new
    file; replaced files stay on disk."""
    saved: list[str] = []
    try:
        return _upload_party_file(member, customer_id, party_id, kind, upload, saved)
    except BaseException:
        _remove_saved(saved)
        raise


def upload_document_file(member, customer_id, party_id, doc_id, upload) -> Customer:
    saved: list[str] = []
    try:
        return _upload_document_file(member, customer_id, party_id, doc_id, upload, saved)
    except BaseException:
        _remove_saved(saved)
        raise


def kyc_missing(customer: Customer) -> list[dict]:
    """KYC gaps as {code, party_id|None, label}; empty list = complete.

    Uses prefetched links/parties/documents/next_of_kin when available (no N+1 on lists).
    """
    missing: list[dict] = []

    def add(code, party, label):
        missing.append({"code": code, "party_id": party.pk if party else None, "label": label})

    if not (customer.address or "").strip():
        add("address_missing", None, "Customer address")
    links = list(customer.links.all())
    signers = {}
    for link in links:
        if link.can_sign:
            signers.setdefault(link.party_id, link.party)
    for party in signers.values():
        if not party.photo:
            add("photo_missing", party, f"Photo of {party.full_name}")
        if not party.signature:
            add("signature_missing", party, f"Signature of {party.full_name}")
        if not any(d.file for d in party.documents.all()):
            add("id_scan_missing", party, f"ID document scan of {party.full_name}")
    if customer.type in (CustomerType.INDIVIDUAL, CustomerType.JOINT):
        seen = set()
        for link in links:
            if (
                link.relation in (Relation.OWNER, Relation.JOINT_HOLDER)
                and link.party_id not in seen
            ):
                seen.add(link.party_id)
                if not link.party.next_of_kin.all():
                    add("next_of_kin_missing", link.party, f"Next of kin of {link.party.full_name}")
    return missing
