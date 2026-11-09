"""Products & accounts API (student routes only).

`/s/{session_id}/products` and `/s/{session_id}/accounts...` need a bank role holding
`account.view` (reads) or `account.open` / `account.close` (writes); the service re-checks
role, visibility, KYC and the archived guard. Opening with incomplete KYC answers 400 with
`code = kyc_incomplete` and a `kyc_missing` list.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ninja import Field, Query, Router, Schema
from ninja.pagination import PageNumberPagination, paginate

from apps.rbac.context import require_bank_permission

from . import services

student_router = Router(tags=["accounts-student"])


class AccountPagination(PageNumberPagination):
    page_size = 25


class ProductOut(Schema):
    id: UUID
    code: str
    name: str
    kind: str
    banking_model: str
    currency: str
    min_balance: Decimal
    allows_cheques: bool


class AccountIn(Schema):
    customer_id: UUID
    product_id: UUID
    mandate: str = "any_one"


class AccountFilters(Schema):
    customer_id: UUID | None = None
    status: str | None = None
    account_no: int | None = Field(None, ge=1, le=2147483647)


class AccountOut(Schema):
    id: UUID
    bank_id: UUID
    account_no: int
    customer_id: UUID
    customer_name: str
    cif_no: int
    product_id: UUID
    product_code: str
    product_name: str
    product_kind: str
    currency: str
    status: str
    mandate: str
    ledger_balance: Decimal
    is_seed: bool
    created_by_id: UUID | None = None
    opened_at: datetime
    closed_at: datetime | None = None

    @staticmethod
    def resolve_customer_name(obj):
        return obj.customer.display_name

    @staticmethod
    def resolve_cif_no(obj):
        return obj.customer.cif_no

    @staticmethod
    def resolve_product_code(obj):
        return obj.product.code

    @staticmethod
    def resolve_product_name(obj):
        return obj.product.name

    @staticmethod
    def resolve_product_kind(obj):
        return obj.product.kind


_P = "/s/{session_id}/products"
_A = "/s/{session_id}/accounts"


@student_router.get(_P, response=list[ProductOut], operation_id="products_list")
@require_bank_permission("account.view")
def products_list(request, session_id: UUID):
    return services.list_products(request.session_member)


@student_router.get(_A, response=list[AccountOut], operation_id="accounts_list")
@require_bank_permission("account.view")
@paginate(AccountPagination)
def accounts_list(request, session_id: UUID, filters: Query[AccountFilters]):
    return services.list_accounts(
        request.session_member,
        customer_id=filters.customer_id,
        status=filters.status,
        account_no=filters.account_no,
    )


@student_router.get(_A + "/{account_id}", response=AccountOut, operation_id="accounts_get")
@require_bank_permission("account.view")
def accounts_get(request, session_id: UUID, account_id: UUID):
    return services.get_account(request.session_member, account_id)


@student_router.post(_A, response=AccountOut, operation_id="accounts_open")
@require_bank_permission("account.open")
def accounts_open(request, session_id: UUID, payload: AccountIn):
    return services.open_account(request.session_member, **payload.dict())


@student_router.post(_A + "/{account_id}/close", response=AccountOut, operation_id="accounts_close")
@require_bank_permission("account.close")
def accounts_close(request, session_id: UUID, account_id: UUID):
    return services.close_account(request.session_member, account_id)
