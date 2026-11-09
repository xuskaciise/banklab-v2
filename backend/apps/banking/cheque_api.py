"""Chequebook / cheque API (student routes). Needs a bank role holding `chequebook.issue`
(issue), `cheque.stop` (stop payment) or `account.view` (reads); services re-check role,
account visibility and the archived guard. Cheque withdrawals go through the transactions API
(`POST .../transactions/cheque-withdrawal`).
"""

from datetime import datetime
from uuid import UUID

from ninja import Router, Schema

from apps.rbac.context import require_bank_permission

from . import cheques

cheque_router = Router(tags=["cheques-student"])
_A = "/s/{session_id}/accounts/{account_id}"


class IssueIn(Schema):
    leaves: int


class StopIn(Schema):
    reason: str


class ChequebookOut(Schema):
    id: UUID
    account_id: UUID
    first_no: int
    last_no: int
    leaves: int
    issued_by_id: UUID
    issued_by_name: str
    issued_at: datetime

    @staticmethod
    def resolve_issued_by_name(obj):
        user = obj.issued_by.user
        return user.full_name or user.username


class ChequeOut(Schema):
    id: UUID
    chequebook_id: UUID
    account_id: UUID
    number: int
    status: str
    transaction_id: UUID | None = None
    stopped_at: datetime | None = None
    stop_reason: str

    @staticmethod
    def resolve_account_id(obj):
        return obj.chequebook.account_id


@cheque_router.get(
    _A + "/chequebooks", response=list[ChequebookOut], operation_id="chequebooks_list"
)
@require_bank_permission("account.view")
def chequebooks_list(request, session_id: UUID, account_id: UUID):
    return cheques.list_chequebooks(request.session_member, account_id)


@cheque_router.post(_A + "/chequebooks", response=ChequebookOut, operation_id="chequebooks_issue")
@require_bank_permission("chequebook.issue")
def chequebooks_issue(request, session_id: UUID, account_id: UUID, payload: IssueIn):
    return cheques.issue_chequebook(request.session_member, account_id, payload.leaves)


@cheque_router.get(_A + "/cheques", response=list[ChequeOut], operation_id="cheques_list")
@require_bank_permission("account.view")
def cheques_list(request, session_id: UUID, account_id: UUID, status: str | None = None):
    return cheques.list_cheques(request.session_member, account_id, status)


@cheque_router.post(
    "/s/{session_id}/cheques/{cheque_id}/stop", response=ChequeOut, operation_id="cheques_stop"
)
@require_bank_permission("cheque.stop")
def cheques_stop(request, session_id: UUID, cheque_id: UUID, payload: StopIn):
    return cheques.stop_cheque(request.session_member, cheque_id, payload.reason)
