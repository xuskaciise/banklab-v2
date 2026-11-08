"""Branches, vaults, tills and vault/teller cash transfers under dual control.

Staff functions (instructor/admin) manage the physical set-up. Student functions take the
acting `SessionMember` and re-check role permission, separation of duties and limits on the
server. Money only moves through `ledger.post_entry` (templates B1/B2 in transactions.md).

Lock order: session -> transfer row -> (posting service: bank -> business day -> cash
positions by id -> GL balances by id).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.audit import services as audit
from apps.lab import services as lab
from apps.lab.models import Bank, RoleAssignment, Session, SessionMember, SessionStatus
from apps.ledger import services as ledger
from apps.ledger.models import GLAccount
from apps.ledger.services import LedgerError
from apps.rbac import services as rbac

from . import cash
from .models import (
    ACTIVE_SESSION_STATUSES,
    Branch,
    BusinessDay,
    BusinessDayStatus,
    CashPosition,
    CashTransfer,
    Denomination,
    HolderType,
    TellerSession,
    TellerSessionStatus,
    Till,
    TransferStatus,
)

PERM_REQUEST = {
    ("vault", "teller_session"): "cash.vault_to_teller.request",
    ("teller_session", "vault"): "cash.teller_to_vault.request",
    ("teller_session", "teller_session"): "cash.teller_to_teller.request",
}
PERM_CUSTODIAN = "cash.vault.approve_custodian"
PERM_MANAGER = "cash.vault.approve_manager"
ZERO = Decimal("0.00")


def _conflict(code: str, message: str) -> LedgerError:
    return LedgerError(code, message, status=409)


# --------------------------------------------------------------------------- staff: set-up


def _staff_bank(actor: User, session_id, bank_id, *, write: bool) -> tuple[Session, Bank]:
    if write:
        session = lab.get_writable_session(actor, session_id)
    else:
        session = lab.get_session(actor, session_id)
    bank = Bank.objects.filter(pk=bank_id, session=session).first()
    if bank is None:
        raise lab.NotFound("Bank not found in this session")
    return session, bank


def _clean(value, what: str, max_len: int, *, required: bool = True) -> str:
    value = (value or "").strip()
    if required and not value:
        raise lab.ValidationFailed(f"{what} is required")
    if len(value) > max_len:
        raise lab.ValidationFailed(f"{what} is longer than {max_len} characters")
    return value


def _staff_audit(actor, action, entity, session, bank, *, before=None, after=None):
    audit.record(
        action,
        actor=actor,
        actor_role=actor.platform_role,
        entity=entity,
        before=before,
        after=after,
        session_id=session.pk,
        bank_id=bank.pk,
        institution_id=actor.institution_id,
    )


def list_branches(actor: User, session_id, bank_id):
    _, bank = _staff_bank(actor, session_id, bank_id, write=False)
    return Branch.objects.filter(bank=bank).select_related("vault").order_by("code")


@transaction.atomic
def create_branch(actor: User, session_id, bank_id, *, code, name, address="") -> Branch:
    session, bank = _staff_bank(actor, session_id, bank_id, write=True)
    code = _clean(code, "Code", 10)
    name = _clean(name, "Name", 200)
    address = _clean(address, "Address", 300, required=False)
    try:
        with transaction.atomic():
            branch = cash.create_branch(bank, code, name, address)
    except IntegrityError:
        raise lab.Conflict("A branch with this code already exists") from None
    _staff_audit(
        actor,
        "banking.branch_created",
        ("branch", branch.pk),
        session,
        bank,
        after={"code": code, "name": name, "address": address, "vault_id": str(branch.vault.pk)},
    )
    return branch


@transaction.atomic
def update_branch(actor: User, session_id, bank_id, branch_id, *, name=None, address=None):
    session, bank = _staff_bank(actor, session_id, bank_id, write=True)
    branch = (
        Branch.objects.select_for_update(of=("self",))
        .select_related("vault")
        .filter(pk=branch_id, bank=bank)
        .first()
    )
    if branch is None:
        raise lab.NotFound("Branch not found")
    before = {"name": branch.name, "address": branch.address}
    if name is not None:
        branch.name = _clean(name, "Name", 200)
    if address is not None:
        branch.address = _clean(address, "Address", 300, required=False)
    branch.save(update_fields=["name", "address", "updated_at"])
    _staff_audit(
        actor,
        "banking.branch_updated",
        ("branch", branch.pk),
        session,
        bank,
        before=before,
        after={"name": branch.name, "address": branch.address},
    )
    return branch


def list_tills(actor: User, session_id, bank_id, branch_id):
    _, bank = _staff_bank(actor, session_id, bank_id, write=False)
    if not Branch.objects.filter(pk=branch_id, bank=bank).exists():
        raise lab.NotFound("Branch not found")
    return Till.objects.filter(bank=bank, branch_id=branch_id).order_by("code")


@transaction.atomic
def create_till(actor: User, session_id, bank_id, branch_id, *, code) -> Till:
    session, bank = _staff_bank(actor, session_id, bank_id, write=True)
    branch = Branch.objects.filter(pk=branch_id, bank=bank).first()
    if branch is None:
        raise lab.NotFound("Branch not found")
    code = _clean(code, "Code", 10)
    try:
        with transaction.atomic():
            till = Till.objects.create(bank=bank, branch=branch, code=code)
    except IntegrityError:
        raise lab.Conflict("A till with this code already exists") from None
    _staff_audit(
        actor,
        "banking.till_created",
        ("till", till.pk),
        session,
        bank,
        after={"code": code, "branch_id": str(branch.pk)},
    )
    return till


def list_denominations():
    return Denomination.objects.all()


# --------------------------------------------------------------------------- reads


def vault_overview(bank: Bank) -> dict:
    """Vault cash per branch and the cash-vs-GL link check."""
    positions: dict[object, dict[str, Decimal]] = {}
    for holder_id, cur, bal in CashPosition.objects.filter(
        bank=bank, holder_type=HolderType.VAULT
    ).values_list("holder_id", "currency", "balance"):
        positions.setdefault(holder_id, {})[cur] = bal
    branches = []
    for branch in Branch.objects.filter(bank=bank).select_related("vault").order_by("code"):
        held = positions.get(branch.vault.pk, {})
        branches.append(
            {
                "branch_id": branch.pk,
                "branch_code": branch.code,
                "branch_name": branch.name,
                "vault_id": branch.vault.pk,
                "positions": [
                    {"currency": cur, "balance": held.get(cur, ZERO)} for cur in cash.CURRENCIES
                ],
            }
        )
    return {"branches": branches, "reconciliation": ledger.cash_reconciliation(bank)}


def list_transfers(bank: Bank):
    return (
        CashTransfer.objects.filter(bank=bank)
        .select_related("requested_by__user", "approved_by_1__user", "approved_by_2__user")
        .order_by("-created_at")
    )


# --------------------------------------------------------------------------- writes


def _lock_session(member: SessionMember) -> Session:
    """Lock the session of the member (archive guard); the member must be placed in a bank."""
    if member.bank_id is None:
        raise rbac.PermissionDenied("Not allowed")
    session = (
        Session.objects.select_for_update(no_key=True, of=("self",))
        .select_related("lab_class")
        .get(pk=member.session_id)
    )
    if session.status == SessionStatus.ARCHIVED:
        raise _conflict("session_archived", "Session is archived (read-only)")
    if session.status != SessionStatus.ACTIVE:
        raise _conflict("session_not_active", "Session is not active")
    return session


def _role_of(member: SessionMember) -> str:
    assignment = RoleAssignment.objects.filter(
        session_member=member, active_to__isnull=True
    ).first()
    if assignment is None:
        raise rbac.PermissionDenied("Not allowed")
    return assignment.role


def _require(role: str, code: str, session: Session) -> None:
    if not rbac.role_has_permission(role, code, session=session):
        raise rbac.PermissionDenied("Not allowed")


def _audit(member, role, action, transfer, session, *, before=None, after=None):
    audit.record(
        action,
        actor=member.user,
        actor_role=role,
        entity=("cash_transfer", transfer.pk),
        before=before,
        after=after,
        session_id=session.pk,
        bank_id=transfer.bank_id,
        institution_id=session.lab_class.institution_id,
    )


def _transfer_dict(t: CashTransfer) -> dict:
    return {
        "from_type": t.from_type,
        "from_id": str(t.from_id),
        "to_type": t.to_type,
        "to_id": str(t.to_id),
        "currency": t.currency,
        "amount": str(t.amount),
        "status": t.status,
    }


def _locked_transfer(member: SessionMember, transfer_id) -> CashTransfer:
    transfer = (
        CashTransfer.objects.select_for_update(of=("self",))
        .select_related("requested_by", "approved_by_1")
        .filter(pk=transfer_id, bank_id=member.bank_id)
        .first()
    )
    if transfer is None:
        raise LedgerError("not_found", "Cash transfer not found", status=404)
    return transfer


def _resolve_teller_side(member, role, bank, from_type, from_id, to_type, to_id):
    """Pick the teller-session holder of a vault <-> teller transfer and lock its row.

    A teller always uses their OWN pending_open/open session; a client-supplied id that
    differs is rejected (never trusted). Other roles (manager issuing cash) must name a
    pending_open/open session of this bank. Cash leaves a session only while it is `open`;
    it may be issued to a `pending_open` session (opening float) or an `open` one.
    Returns (from_id, to_id).
    """
    sending = from_type == HolderType.TELLER_SESSION
    supplied = from_id if sending else to_id
    wanted = (
        [TellerSessionStatus.OPEN]
        if sending
        else [
            TellerSessionStatus.PENDING_OPEN,
            TellerSessionStatus.OPEN,
        ]
    )
    qs = TellerSession.objects.select_for_update(of=("self",)).select_related("till__branch__vault")
    if role == "teller":
        ts = qs.filter(bank=bank, teller_member=member, status__in=ACTIVE_SESSION_STATUSES).first()
        if ts is None:
            raise _conflict("no_open_till", "You have no teller session today")
        if supplied is not None and str(supplied) != str(ts.pk):
            raise LedgerError(
                "foreign_teller_session", "You can only use your own teller session", status=403
            )
    else:
        if supplied is None:
            raise LedgerError("teller_session_required", "A teller session is required")
        try:
            ts = qs.filter(bank=bank, pk=supplied).first()
        except (ValueError, TypeError, ValidationError):
            ts = None
        if ts is None:
            raise LedgerError("unknown_cash_holder", "teller_session not found in this bank")
    if ts.status not in wanted:
        raise _conflict(
            "till_not_open",
            "The teller session is not open"
            if sending
            else "The teller session cannot receive cash",
        )
    vault_id = to_id if sending else from_id
    if vault_id is not None and str(vault_id) != str(ts.till.branch.vault.pk):
        raise _conflict("wrong_vault", "Cash must go through the vault of the till's branch")
    return (ts.pk, to_id) if sending else (from_id, ts.pk)


def request_vault_transfer(
    member: SessionMember, *, from_type, to_type, currency, amount, from_id=None, to_id=None
) -> CashTransfer:
    """Create a pending vault <-> teller transfer (B1 / B2); nothing posts before both approvals."""
    with transaction.atomic():
        session = _lock_session(member)
        role = _role_of(member)
        direction = (from_type, to_type)
        if direction not in PERM_REQUEST:
            raise LedgerError("invalid_holder_type", "A transfer must involve a vault or a teller")
        _require(role, PERM_REQUEST[direction], session)
        if HolderType.VAULT not in direction:
            raise LedgerError(
                "unsupported_transfer", "Teller to teller transfers are not available yet"
            )
        if currency not in ledger.CURRENCIES:
            raise LedgerError("invalid_currency", "Currency must be USD or SOS")
        value = ledger._check_amount(amount, "Amount")
        if value <= 0:
            raise LedgerError("invalid_amount", "Amount must be greater than zero")
        bank = member.bank
        from_id, to_id = _resolve_teller_side(
            member, role, bank, from_type, from_id, to_type, to_id
        )
        for holder_type, holder_id in ((from_type, from_id), (to_type, to_id)):
            if not cash.holder_exists(bank, holder_type, holder_id):
                raise LedgerError("unknown_cash_holder", f"{holder_type} not found in this bank")
        if from_type == to_type and str(from_id) == str(to_id):
            raise LedgerError("same_holder", "Source and destination must differ")
        if not BusinessDay.objects.filter(bank=bank, status=BusinessDayStatus.OPEN).exists():
            raise _conflict("day_closed", "The bank has no open business day")
        source = CashPosition.objects.filter(
            bank=bank, holder_type=from_type, holder_id=from_id, currency=currency
        ).first()
        if source is None or source.balance < value:
            raise _conflict("insufficient_cash", f"Not enough {currency} cash at the source")
        transfer = CashTransfer.objects.create(
            bank=bank,
            from_type=from_type,
            from_id=from_id,
            to_type=to_type,
            to_id=to_id,
            currency=currency,
            amount=value,
            requested_by=member,
        )
        _audit(
            member,
            role,
            "cash.transfer_requested",
            transfer,
            session,
            after=_transfer_dict(transfer),
        )
        return transfer


def approve_custodian(member: SessionMember, transfer_id) -> CashTransfer:
    """First approval (Vault Custodian)."""
    with transaction.atomic():
        session = _lock_session(member)
        role = _role_of(member)
        _require(role, PERM_CUSTODIAN, session)
        transfer = _locked_transfer(member, transfer_id)
        if transfer.status != TransferStatus.PENDING:
            raise _conflict("invalid_status", "Transfer is not waiting for custodian approval")
        rbac.assert_maker_checker(transfer.requested_by.user_id, member.user_id)
        transfer.approved_by_1 = member
        transfer.status = TransferStatus.CUSTODIAN_APPROVED
        transfer.save(update_fields=["approved_by_1", "status", "updated_at"])
        _audit(
            member,
            role,
            "cash.transfer_custodian_approved",
            transfer,
            session,
            before={"status": TransferStatus.PENDING},
            after={"status": transfer.status},
        )
        return transfer


def approve_manager(member: SessionMember, transfer_id) -> CashTransfer:
    """Second approval (Manager); posts the transfer to the ledger."""
    with transaction.atomic():
        session = _lock_session(member)
        role = _role_of(member)
        _require(role, PERM_MANAGER, session)
        transfer = _locked_transfer(member, transfer_id)
        if transfer.status == TransferStatus.PENDING:
            raise _conflict("custodian_approval_required", "The vault custodian must approve first")
        if transfer.status != TransferStatus.CUSTODIAN_APPROVED:
            raise _conflict("invalid_status", "Transfer is not waiting for manager approval")
        rbac.assert_dual_control(
            transfer.requested_by.user_id, transfer.approved_by_1.user_id, member.user_id
        )
        _recheck_teller_state(transfer)
        entry = _post_cash_transfer(transfer, member)
        transfer.approved_by_2 = member
        transfer.status = TransferStatus.POSTED
        transfer.journal_entry = entry
        transfer.save(update_fields=["approved_by_2", "status", "journal_entry", "updated_at"])
        _audit(
            member,
            role,
            "cash.transfer_posted",
            transfer,
            session,
            before={"status": TransferStatus.CUSTODIAN_APPROVED},
            after={"status": transfer.status, "entry_no": entry.entry_no},
        )
        return transfer


def reject_transfer(member: SessionMember, transfer_id, reason) -> CashTransfer:
    """Reject (approvers) or cancel (the requester) an open transfer; nothing is posted."""
    with transaction.atomic():
        session = _lock_session(member)
        role = _role_of(member)
        transfer = _locked_transfer(member, transfer_id)
        cancelling = transfer.requested_by_id == member.pk
        if not cancelling and not (
            rbac.role_has_permission(role, PERM_CUSTODIAN, session=session)
            or rbac.role_has_permission(role, PERM_MANAGER, session=session)
        ):
            raise rbac.PermissionDenied("Not allowed")
        reason = (reason or "").strip()
        if not reason and not cancelling:
            raise LedgerError("reason_required", "A reason is required")
        if len(reason) > 300:
            raise LedgerError("text_too_long", "Reason is longer than 300 characters")
        if transfer.status not in (TransferStatus.PENDING, TransferStatus.CUSTODIAN_APPROVED):
            raise _conflict("invalid_status", "Transfer can no longer be rejected")
        before = {"status": transfer.status}
        if cancelling:
            transfer.status = TransferStatus.CANCELLED
            reason = reason or "Cancelled by requester"
        else:
            transfer.status = TransferStatus.REJECTED
        transfer.rejected_by = member
        transfer.reason = reason
        transfer.save(update_fields=["status", "rejected_by", "reason", "updated_at"])
        _audit(
            member,
            role,
            "cash.transfer_cancelled" if cancelling else "cash.transfer_rejected",
            transfer,
            session,
            before=before,
            after={"status": transfer.status, "reason": reason},
        )
        return transfer


def _recheck_teller_state(transfer: CashTransfer) -> None:
    """At posting time the teller side must still be in a state that allows the movement."""
    for side, holder_type, holder_id in (
        ("from", transfer.from_type, transfer.from_id),
        ("to", transfer.to_type, transfer.to_id),
    ):
        if holder_type != HolderType.TELLER_SESSION:
            continue
        ts = (
            TellerSession.objects.select_for_update(of=("self",))
            .filter(bank_id=transfer.bank_id, pk=holder_id)
            .first()
        )
        allowed = (
            (TellerSessionStatus.OPEN,)
            if side == "from"
            else (TellerSessionStatus.PENDING_OPEN, TellerSessionStatus.OPEN)
        )
        if ts is None or ts.status not in allowed:
            raise _conflict("till_not_open", "The teller session can no longer take part")


def _post_cash_transfer(transfer: CashTransfer, poster: SessionMember):
    """B1 (vault -> teller) / B2 (teller -> vault): Dr destination cash, Cr source cash.

    The only place that builds transfer lines; the ledger re-checks the source balance.
    """
    gl = {
        a.system_tag: a
        for a in GLAccount.objects.filter(
            bank_id=transfer.bank_id, system_tag__in=list(cash.GL_TAG_HOLDER)
        )
    }
    amount = transfer.amount
    lines = [
        ledger.LineSpec(
            gl[cash.HOLDER_GL_TAG[transfer.to_type]],
            debit=amount,
            cash_holder_type=transfer.to_type,
            cash_holder_id=transfer.to_id,
        ),
        ledger.LineSpec(
            gl[cash.HOLDER_GL_TAG[transfer.from_type]],
            credit=amount,
            cash_holder_type=transfer.from_type,
            cash_holder_id=transfer.from_id,
        ),
    ]
    kind = "B1 vault to teller" if transfer.from_type == HolderType.VAULT else "B2 teller to vault"
    return ledger.post_entry(
        transfer.bank,
        lines,
        currency=transfer.currency,
        source_type="cash_transfer",
        source_id=transfer.pk,
        description=f"{kind} cash transfer",
        actor_member=poster,
    )
