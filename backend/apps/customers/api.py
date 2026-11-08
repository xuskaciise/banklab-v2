"""Customers (CIF) API.

Student routes (`/s/{session_id}/customers...`) need a bank role holding `customer.view`
(reads) or `customer.create` / `customer.update` (writes); the service re-checks role,
visibility and the archived guard. Staff routes (instructor/admin) are read-only.

Files (photo, signature, ID scans) are never served statically: they are streamed by the
`.../photo`, `.../signature` and `.../documents/{id}/file` GET routes after the same
bank/visibility check as the customer itself.
"""

from datetime import date, datetime
from uuid import UUID

from django.http import FileResponse
from ninja import File, Query, Router, Schema, UploadedFile
from ninja.pagination import PageNumberPagination, paginate

from apps.rbac.context import require_bank_permission

from . import services

router = Router(tags=["customers"])
student_router = Router(tags=["customers-student"])


class CustomerPagination(PageNumberPagination):
    page_size = 25


# ----------------------------------------------------------------------- schemas


class DocumentIn(Schema):
    type: str
    number: str
    issue_date: date
    expiry_date: date


class DocumentUpdateIn(Schema):
    type: str | None = None
    number: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None


class KinIn(Schema):
    name: str
    phone: str = ""
    relationship: str


class KinUpdateIn(Schema):
    name: str | None = None
    phone: str | None = None
    relationship: str | None = None


class PartyIn(Schema):
    full_name: str
    sex: str = ""
    date_of_birth: date | None = None
    phone: str = ""
    relation: str
    can_sign: bool | None = None
    identity_documents: list[DocumentIn] = []
    next_of_kin: list[KinIn] = []


class AddPartyIn(Schema):
    """A new person (full_name + identity_documents) or an existing one (party_id)."""

    relation: str
    can_sign: bool | None = None
    party_id: UUID | None = None
    full_name: str = ""
    sex: str = ""
    date_of_birth: date | None = None
    phone: str = ""
    identity_documents: list[DocumentIn] = []
    next_of_kin: list[KinIn] = []


class PartyUpdateIn(Schema):
    full_name: str | None = None
    sex: str | None = None
    date_of_birth: date | None = None
    phone: str | None = None
    can_sign: bool | None = None


class CustomerIn(Schema):
    type: str
    display_name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    reg_no: str = ""
    parties: list[PartyIn]


class CustomerUpdateIn(Schema):
    display_name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    reg_no: str | None = None


class CustomerFilters(Schema):
    q: str | None = None
    type: str | None = None


class DocumentOut(Schema):
    id: UUID
    type: str
    number: str
    issue_date: date
    expiry_date: date
    has_file: bool

    @staticmethod
    def resolve_has_file(obj):
        return bool(obj.file)


class KinOut(Schema):
    id: UUID
    name: str
    phone: str
    relationship: str


class PartyLinkOut(Schema):
    party_id: UUID
    relation: str
    can_sign: bool
    full_name: str
    sex: str
    date_of_birth: date | None
    phone: str
    has_photo: bool
    has_signature: bool
    identity_documents: list[DocumentOut]
    next_of_kin: list[KinOut]

    @staticmethod
    def resolve_full_name(obj):
        return obj.party.full_name

    @staticmethod
    def resolve_sex(obj):
        return obj.party.sex

    @staticmethod
    def resolve_date_of_birth(obj):
        return obj.party.date_of_birth

    @staticmethod
    def resolve_phone(obj):
        return obj.party.phone

    @staticmethod
    def resolve_has_photo(obj):
        return bool(obj.party.photo)

    @staticmethod
    def resolve_has_signature(obj):
        return bool(obj.party.signature)

    @staticmethod
    def resolve_identity_documents(obj):
        return list(obj.party.documents.all())

    @staticmethod
    def resolve_next_of_kin(obj):
        return list(obj.party.next_of_kin.all())


class CustomerOut(Schema):
    id: UUID
    bank_id: UUID
    cif_no: int
    type: str
    display_name: str
    phone: str
    email: str
    address: str
    reg_no: str
    is_seed: bool
    created_by_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    kyc_complete: bool

    @staticmethod
    def resolve_kyc_complete(obj):
        return not services.kyc_missing(obj)


class KycItemOut(Schema):
    code: str
    party_id: UUID | None = None
    label: str


class CustomerDetailOut(CustomerOut):
    parties: list[PartyLinkOut]
    kyc_missing: list[KycItemOut]

    @staticmethod
    def resolve_kyc_missing(obj):
        return services.kyc_missing(obj)

    @staticmethod
    def resolve_parties(obj):
        return list(obj.links.all())


# ----------------------------------------------------------------------- student routes

_C = "/s/{session_id}/customers"


@student_router.get(_C, response=list[CustomerOut], operation_id="customers_list")
@require_bank_permission("customer.view")
@paginate(CustomerPagination)
def customers_list(request, session_id: UUID, filters: Query[CustomerFilters]):
    return services.list_customers(request.session_member, q=filters.q, type=filters.type)


@student_router.get(_C + "/{customer_id}", response=CustomerDetailOut, operation_id="customers_get")
@require_bank_permission("customer.view")
def customers_get(request, session_id: UUID, customer_id: UUID):
    return services.get_customer(request.session_member, customer_id)


@student_router.post(_C, response=CustomerDetailOut, operation_id="customers_create")
@require_bank_permission("customer.create")
def customers_create(request, session_id: UUID, payload: CustomerIn):
    return services.create_customer(request.session_member, **payload.dict())


@student_router.patch(
    _C + "/{customer_id}", response=CustomerDetailOut, operation_id="customers_update"
)
@require_bank_permission("customer.update")
def customers_update(request, session_id: UUID, customer_id: UUID, payload: CustomerUpdateIn):
    return services.update_customer(
        request.session_member, customer_id, **payload.dict(exclude_unset=True)
    )


@student_router.post(
    _C + "/{customer_id}/parties", response=CustomerDetailOut, operation_id="customers_party_add"
)
@require_bank_permission("customer.update")
def party_add(request, session_id: UUID, customer_id: UUID, payload: AddPartyIn):
    return services.add_party(request.session_member, customer_id, **payload.dict())


@student_router.patch(
    _C + "/{customer_id}/parties/{party_id}",
    response=CustomerDetailOut,
    operation_id="customers_party_update",
)
@require_bank_permission("customer.update")
def party_update(
    request, session_id: UUID, customer_id: UUID, party_id: UUID, payload: PartyUpdateIn
):
    return services.update_party(
        request.session_member, customer_id, party_id, **payload.dict(exclude_unset=True)
    )


@student_router.post(
    _C + "/{customer_id}/parties/{party_id}/documents",
    response=CustomerDetailOut,
    operation_id="customers_document_add",
)
@require_bank_permission("customer.update")
def document_add(request, session_id: UUID, customer_id: UUID, party_id: UUID, payload: DocumentIn):
    return services.add_document(request.session_member, customer_id, party_id, **payload.dict())


@student_router.patch(
    _C + "/{customer_id}/parties/{party_id}/documents/{doc_id}",
    response=CustomerDetailOut,
    operation_id="customers_document_update",
)
@require_bank_permission("customer.update")
def document_update(
    request,
    session_id: UUID,
    customer_id: UUID,
    party_id: UUID,
    doc_id: UUID,
    payload: DocumentUpdateIn,
):
    return services.update_document(
        request.session_member,
        customer_id,
        party_id,
        doc_id,
        **payload.dict(exclude_unset=True),
    )


@student_router.post(
    _C + "/{customer_id}/parties/{party_id}/next-of-kin",
    response=CustomerDetailOut,
    operation_id="customers_kin_add",
)
@require_bank_permission("customer.update")
def kin_add(request, session_id: UUID, customer_id: UUID, party_id: UUID, payload: KinIn):
    return services.add_next_of_kin(request.session_member, customer_id, party_id, **payload.dict())


@student_router.patch(
    _C + "/{customer_id}/parties/{party_id}/next-of-kin/{kin_id}",
    response=CustomerDetailOut,
    operation_id="customers_kin_update",
)
@require_bank_permission("customer.update")
def kin_update(
    request, session_id: UUID, customer_id: UUID, party_id: UUID, kin_id: UUID, payload: KinUpdateIn
):
    return services.update_next_of_kin(
        request.session_member,
        customer_id,
        party_id,
        kin_id,
        **payload.dict(exclude_unset=True),
    )


# --- files (multipart upload, authenticated download)


def _stream(field):
    response = FileResponse(field.open("rb"), content_type=services.content_type_of(field.name))
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    response["Content-Security-Policy"] = "sandbox"
    return response


@student_router.post(
    _C + "/{customer_id}/parties/{party_id}/{kind}",
    response=CustomerDetailOut,
    operation_id="customers_party_file_upload",
)
@require_bank_permission("customer.update")
def party_file_upload(
    request,
    session_id: UUID,
    customer_id: UUID,
    party_id: UUID,
    kind: str,
    file: File[UploadedFile],
):
    """kind = `photo` or `signature` (JPEG/PNG, max 2 MB)."""
    return services.upload_party_file(request.session_member, customer_id, party_id, kind, file)


@student_router.get(
    _C + "/{customer_id}/parties/{party_id}/{kind}",
    response={200: None},
    operation_id="customers_party_file_get",
)
@require_bank_permission("customer.view")
def party_file_get(request, session_id: UUID, customer_id: UUID, party_id: UUID, kind: str):
    return _stream(services.open_file(request.session_member, customer_id, party_id, kind))


@student_router.post(
    _C + "/{customer_id}/parties/{party_id}/documents/{doc_id}/file",
    response=CustomerDetailOut,
    operation_id="customers_document_file_upload",
)
@require_bank_permission("customer.update")
def document_file_upload(
    request,
    session_id: UUID,
    customer_id: UUID,
    party_id: UUID,
    doc_id: UUID,
    file: File[UploadedFile],
):
    """ID scan (JPEG/PNG/PDF, max 2 MB)."""
    return services.upload_document_file(
        request.session_member, customer_id, party_id, doc_id, file
    )


@student_router.get(
    _C + "/{customer_id}/parties/{party_id}/documents/{doc_id}/file",
    response={200: None},
    operation_id="customers_document_file_get",
)
@require_bank_permission("customer.view")
def document_file_get(request, session_id: UUID, customer_id: UUID, party_id: UUID, doc_id: UUID):
    return _stream(
        services.open_file(request.session_member, customer_id, party_id, "document", doc_id)
    )


# ----------------------------------------------------------------------- staff routes (read-only)

_S = "/sessions/{session_id}/banks/{bank_id}/customers"


@router.get(_S, response=list[CustomerOut], operation_id="customers_staff_list")
@paginate(CustomerPagination)
def staff_list(request, session_id: UUID, bank_id: UUID, filters: Query[CustomerFilters]):
    return services.staff_list_customers(
        request.user, session_id, bank_id, q=filters.q, type=filters.type
    )


@router.get(_S + "/{customer_id}", response=CustomerDetailOut, operation_id="customers_staff_get")
def staff_get(request, session_id: UUID, bank_id: UUID, customer_id: UUID):
    return services.staff_get_customer(request.user, session_id, bank_id, customer_id)
