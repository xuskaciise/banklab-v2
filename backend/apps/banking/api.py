"""Branch / vault / till / cash-transfer API.

Staff routes (instructor of the class, or admin) set up branches and tills. Student routes
need a bank role: `vault.view` for the vault screens, the cash permissions for transfers
(checked again inside the service).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ninja import Router, Schema

from apps.rbac import context as rbac_context
from apps.rbac.context import require_bank_permission

from . import services

router = Router(tags=["banking"])
student_router = Router(tags=["banking-student"])


# ----------------------------------------------------------------------- schemas


class BranchIn(Schema):
    code: str
    name: str
    address: str = ""


class BranchUpdateIn(Schema):
    name: str | None = None
    address: str | None = None


class BranchOut(Schema):
    id: UUID
    bank_id: UUID
    code: str
    name: str
    address: str
    vault_id: UUID

    @staticmethod
    def resolve_vault_id(obj):
        return obj.vault.pk


class TillIn(Schema):
    code: str


class TillOut(Schema):
    id: UUID
    bank_id: UUID
    branch_id: UUID
    code: str


class DenominationOut(Schema):
    id: int
    currency: str
    value: Decimal
    kind: str


class CashPositionOut(Schema):
    currency: str
    balance: Decimal


class VaultBranchOut(Schema):
    branch_id: UUID
    branch_code: str
    branch_name: str
    vault_id: UUID
    positions: list[CashPositionOut]


class CashReconciliationOut(Schema):
    currency: str
    vault_total: Decimal
    gl_vault: Decimal
    teller_total: Decimal
    gl_teller: Decimal
    ok: bool


class VaultOut(Schema):
    branches: list[VaultBranchOut]
    reconciliation: list[CashReconciliationOut]


class TransferIn(Schema):
    from_type: str
    from_id: UUID
    to_type: str
    to_id: UUID
    currency: str
    amount: Decimal


class RejectIn(Schema):
    reason: str


class TransferOut(Schema):
    id: UUID
    from_type: str
    from_id: UUID
    to_type: str
    to_id: UUID
    currency: str
    amount: Decimal
    status: str
    requested_by_id: UUID
    requested_by_name: str
    approved_by_1_id: UUID | None = None
    approved_by_1_name: str | None = None
    approved_by_2_id: UUID | None = None
    approved_by_2_name: str | None = None
    rejected_by_id: UUID | None = None
    reason: str
    journal_entry_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def _name(member):
        if member is None:
            return None
        return member.user.full_name or member.user.username

    @staticmethod
    def resolve_requested_by_name(obj):
        return TransferOut._name(obj.requested_by)

    @staticmethod
    def resolve_approved_by_1_name(obj):
        return TransferOut._name(obj.approved_by_1)

    @staticmethod
    def resolve_approved_by_2_name(obj):
        return TransferOut._name(obj.approved_by_2)


# ----------------------------------------------------------------------- staff routes

_BASE = "/sessions/{session_id}/banks/{bank_id}"


@router.get(
    _BASE + "/branches", response=list[BranchOut], operation_id="banking_staff_branches_list"
)
def branches_list(request, session_id: UUID, bank_id: UUID):
    return services.list_branches(request.user, session_id, bank_id)


@router.post(_BASE + "/branches", response=BranchOut, operation_id="banking_staff_branches_create")
def branches_create(request, session_id: UUID, bank_id: UUID, payload: BranchIn):
    return services.create_branch(request.user, session_id, bank_id, **payload.dict())


@router.patch(
    _BASE + "/branches/{branch_id}",
    response=BranchOut,
    operation_id="banking_staff_branches_update",
)
def branches_update(
    request, session_id: UUID, bank_id: UUID, branch_id: UUID, payload: BranchUpdateIn
):
    return services.update_branch(
        request.user, session_id, bank_id, branch_id, **payload.dict(exclude_unset=True)
    )


@router.get(
    _BASE + "/branches/{branch_id}/tills",
    response=list[TillOut],
    operation_id="banking_staff_tills_list",
)
def tills_list(request, session_id: UUID, bank_id: UUID, branch_id: UUID):
    return services.list_tills(request.user, session_id, bank_id, branch_id)


@router.post(
    _BASE + "/branches/{branch_id}/tills",
    response=TillOut,
    operation_id="banking_staff_tills_create",
)
def tills_create(request, session_id: UUID, bank_id: UUID, branch_id: UUID, payload: TillIn):
    return services.create_till(request.user, session_id, bank_id, branch_id, code=payload.code)


# ----------------------------------------------------------------------- student routes


@student_router.get(
    "/denominations", response=list[DenominationOut], operation_id="banking_denominations"
)
def denominations(request):
    return services.list_denominations()


@student_router.get("/s/{session_id}/vault", response=VaultOut, operation_id="banking_vault")
@require_bank_permission("vault.view")
def vault(request, session_id: UUID):
    return services.vault_overview(request.bank)


@student_router.get(
    "/s/{session_id}/cash-transfers",
    response=list[TransferOut],
    operation_id="banking_transfers_list",
)
@require_bank_permission("vault.view")
def transfers_list(request, session_id: UUID):
    return services.list_transfers(request.bank)


def _member(request, session_id):
    return rbac_context.resolve_bank_context(request, session_id).member


@student_router.post(
    "/s/{session_id}/cash-transfers", response=TransferOut, operation_id="banking_transfers_request"
)
def transfers_request(request, session_id: UUID, payload: TransferIn):
    member = _member(request, session_id)
    return services.request_vault_transfer(member, **payload.dict())


@student_router.post(
    "/s/{session_id}/cash-transfers/{transfer_id}/approve-custodian",
    response=TransferOut,
    operation_id="banking_transfers_approve_custodian",
)
def transfers_approve_custodian(request, session_id: UUID, transfer_id: UUID):
    return services.approve_custodian(_member(request, session_id), transfer_id)


@student_router.post(
    "/s/{session_id}/cash-transfers/{transfer_id}/approve-manager",
    response=TransferOut,
    operation_id="banking_transfers_approve_manager",
)
def transfers_approve_manager(request, session_id: UUID, transfer_id: UUID):
    return services.approve_manager(_member(request, session_id), transfer_id)


@student_router.post(
    "/s/{session_id}/cash-transfers/{transfer_id}/reject",
    response=TransferOut,
    operation_id="banking_transfers_reject",
)
def transfers_reject(request, session_id: UUID, transfer_id: UUID, payload: RejectIn):
    return services.reject_transfer(_member(request, session_id), transfer_id, payload.reason)
