"""Teller sessions (1.8): open with manager approval, denomination count on close, over/short.

Student functions take the acting `SessionMember` and re-check role permission, separation
of duties and state on the server. Money only moves through `ledger.post_entry`:
E1 over/short and B2 return of the till cash to the vault (transactions.md).

Decisions:
- Opening float is requested together with the open request; the vault -> teller transfers
  use the normal dual control (custodian + manager) and may target the `pending_open` session.
- A rejected open request stays `pending_open` with a note; the teller may cancel it
  (`cancelled`, only while the session holds no cash).
- `closing` freezes the session's cash (no transfers in or out). A rejected close goes
  back to `open`; the next count gets the next `attempt`, old counts stay as history.
- The manager's close approval alone posts E1 and the B2 return (no custodian step); the
  B2 transfer is stored as `posted` with the manager as both approvers.

Lock order: lab session -> teller session row -> (posting service: bank -> business day ->
cash positions -> GL balances).
"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit import services as audit
from apps.core import platform
from apps.lab.models import SessionMember
from apps.ledger import services as ledger
from apps.ledger.models import GLAccount
from apps.ledger.services import LedgerError
from apps.rbac import services as rbac

from . import cash
from . import services as banking
from .models import (
    ACTIVE_SESSION_STATUSES,
    BusinessDay,
    BusinessDayStatus,
    CashCount,
    CashCountKind,
    CashCountLine,
    CashPosition,
    CashTransfer,
    Denomination,
    HolderType,
    TellerSession,
    TellerSessionStatus,
    Till,
    TransferStatus,
)

ZERO = Decimal("0.00")
P_OPEN_REQUEST = "till.open.request"
P_CLOSE = "till.close"
P_OPEN_APPROVE = "till.open.approve"
P_CLOSE_APPROVE = "till.close.approve"
MAX_QUANTITY = 10_000_000
_conflict = banking._conflict


# --------------------------------------------------------------------------- helpers


def _name(member) -> str | None:
    if member is None:
        return None
    return member.user.full_name or member.user.username


def _audit(member, role, action, ts, session, *, before=None, after=None):
    audit.record(
        action,
        actor=member.user,
        actor_role=role,
        entity=("teller_session", ts.pk),
        before=before,
        after=after,
        session_id=session.pk,
        bank_id=ts.bank_id,
        institution_id=session.lab_class.institution_id,
    )


def _open_day(bank) -> BusinessDay:
    day = BusinessDay.objects.filter(bank=bank, status=BusinessDayStatus.OPEN).first()
    if day is None:
        raise _conflict("day_closed", "The bank has no open business day")
    return day


def _locked_ts(member: SessionMember, session_id) -> TellerSession:
    ts = (
        TellerSession.objects.select_for_update(of=("self",))
        .select_related("teller_member__user", "till__branch__vault")
        .filter(pk=session_id, bank_id=member.bank_id)
        .first()
    )
    if ts is None:
        raise LedgerError("not_found", "Teller session not found", status=404)
    return ts


def _open_transfers(ts: TellerSession):
    return CashTransfer.objects.filter(
        bank_id=ts.bank_id,
        status__in=(TransferStatus.PENDING, TransferStatus.CUSTODIAN_APPROVED),
    ).filter(
        Q(from_type=HolderType.TELLER_SESSION, from_id=ts.pk)
        | Q(to_type=HolderType.TELLER_SESSION, to_id=ts.pk)
    )


def _balances(ts: TellerSession) -> dict[str, Decimal]:
    held = dict(
        CashPosition.objects.filter(
            bank_id=ts.bank_id, holder_type=HolderType.TELLER_SESSION, holder_id=ts.pk
        ).values_list("currency", "balance")
    )
    return {cur: held.get(cur, ZERO) for cur in cash.CURRENCIES}


def _require_own(member, ts):
    if ts.teller_member_id != member.pk:
        raise rbac.PermissionDenied("Not allowed")


# --------------------------------------------------------------------------- reads


def _can_any(member, *codes) -> str:
    """Role of the member when it holds at least one of `codes`; else 403."""
    if member.bank_id is None:
        raise rbac.PermissionDenied("Not allowed")
    role = banking._role_of(member)
    if not any(rbac.role_has_permission(role, c, session=member.session) for c in codes):
        raise rbac.PermissionDenied("Not allowed")
    return role


def _count_dict(c: CashCount) -> dict:
    return {
        "id": c.pk,
        "kind": c.kind,
        "currency": c.currency,
        "attempt": c.attempt,
        "counted_total": c.counted_total,
        "system_total": c.system_total,
        "difference": c.difference,
        "approved": c.approved_by_id is not None,
        "lines": [
            {
                "denomination_id": ln.denomination_id,
                "value": ln.denomination.value,
                "quantity": ln.quantity,
            }
            for ln in c.lines.all()
        ],
    }


def session_view(ts: TellerSession) -> dict:
    """Plain dict for the API: balances, pending transfers and the latest closing counts."""
    latest = (
        CashCount.objects.filter(teller_session=ts, kind=CashCountKind.CLOSE)
        .select_related("approved_by")
        .prefetch_related("lines__denomination")
        .order_by("-attempt", "currency")
    )
    counts, seen_attempt = [], None
    for c in latest:
        if seen_attempt is None:
            seen_attempt = c.attempt
        if c.attempt != seen_attempt:
            break
        counts.append(_count_dict(c))
    pending = [
        {
            "id": t.pk,
            "direction": "vault_to_teller"
            if t.from_type == HolderType.VAULT
            else "teller_to_vault",
            "currency": t.currency,
            "amount": t.amount,
            "status": t.status,
        }
        for t in _open_transfers(ts).order_by("created_at")
    ]
    bal = _balances(ts)
    return {
        "id": ts.pk,
        "bank_id": ts.bank_id,
        "till_id": ts.till_id,
        "till_code": ts.till.code,
        "branch_id": ts.till.branch_id,
        "teller_member_id": ts.teller_member_id,
        "teller_name": _name(ts.teller_member),
        "business_date": ts.business_date,
        "status": ts.status,
        "open_requested_at": ts.open_requested_at,
        "opened_at": ts.opened_at,
        "open_approved_by_name": _name(ts.open_approved_by),
        "open_reject_note": ts.open_reject_note,
        "close_requested_at": ts.close_requested_at,
        "closed_at": ts.closed_at,
        "close_approved_by_name": _name(ts.close_approved_by),
        "close_reject_note": ts.close_reject_note,
        "balances": [{"currency": c, "balance": b} for c, b in bal.items()],
        "pending_transfers": pending,
        "latest_counts": counts,
    }


def _sessions_qs():
    return TellerSession.objects.select_related(
        "teller_member__user", "till__branch", "open_approved_by__user", "close_approved_by__user"
    )


def my_session(member: SessionMember) -> dict | None:
    """The caller's session for the open business day (None when there is none)."""
    _can_any(member, P_OPEN_REQUEST, P_CLOSE)
    day = BusinessDay.objects.filter(bank_id=member.bank_id, status=BusinessDayStatus.OPEN).first()
    if day is None:
        return None
    ts = (
        _sessions_qs()
        .filter(bank_id=member.bank_id, teller_member=member, business_date=day.date)
        .exclude(status=TellerSessionStatus.CANCELLED)
        .first()
    )
    return session_view(ts) if ts else None


def list_sessions(member: SessionMember, business_date=None) -> list[dict]:
    """Manager view: teller sessions of a day (default: the open business day)."""
    _can_any(member, P_OPEN_APPROVE, P_CLOSE_APPROVE)
    if business_date is None:
        day = BusinessDay.objects.filter(
            bank_id=member.bank_id, status=BusinessDayStatus.OPEN
        ).first()
        if day is None:
            return []
        business_date = day.date
    qs = _sessions_qs().filter(bank_id=member.bank_id, business_date=business_date)
    return [session_view(ts) for ts in qs.order_by("open_requested_at")]


def list_tills_availability(member: SessionMember) -> list[dict]:
    _can_any(member, P_OPEN_REQUEST, P_OPEN_APPROVE, P_CLOSE_APPROVE)
    busy = {
        ts.till_id: ts
        for ts in _sessions_qs().filter(bank_id=member.bank_id, status__in=ACTIVE_SESSION_STATUSES)
    }
    out = []
    for till in Till.objects.filter(bank_id=member.bank_id).select_related("branch__vault"):
        ts = busy.get(till.pk)
        out.append(
            {
                "id": till.pk,
                "code": till.code,
                "branch_id": till.branch_id,
                "branch_code": till.branch.code,
                "branch_name": till.branch.name,
                "branch_address": till.branch.address,
                "vault_id": till.branch.vault.pk,
                "available": ts is None,
                "in_use_by": _name(ts.teller_member) if ts else None,
                "session_status": ts.status if ts else None,
            }
        )
    return sorted(out, key=lambda r: (r["branch_code"], r["code"]))


# --------------------------------------------------------------------------- open


def request_open(member: SessionMember, till_id, floats=None) -> TellerSession:
    """Teller asks to open a till; optional opening float per currency (vault -> teller)."""
    with transaction.atomic():
        session = banking._lock_session(member)
        role = banking._role_of(member)
        banking._require(role, P_OPEN_REQUEST, session)
        bank = member.bank
        day = _open_day(bank)
        till = Till.objects.select_related("branch__vault").filter(pk=till_id, bank=bank).first()
        if till is None:
            raise LedgerError("not_found", "Till not found", status=404)
        wanted = []
        seen = set()
        for item in floats or []:
            currency, amount = item["currency"], item["amount"]
            if currency not in ledger.CURRENCIES:
                raise LedgerError("invalid_currency", "Currency must be USD or SOS")
            platform.require_currency_enabled(currency)
            if currency in seen:
                raise LedgerError("duplicate_currency", "One opening float per currency")
            seen.add(currency)
            value = ledger._check_amount(amount, "Opening float")
            if value < 0:
                raise LedgerError("invalid_amount", "Opening float cannot be negative")
            if value > 0:
                wanted.append((currency, value))
        if (
            TellerSession.objects.filter(bank=bank, teller_member=member, business_date=day.date)
            .exclude(status=TellerSessionStatus.CANCELLED)
            .exists()
        ):
            raise _conflict("session_exists", "You already have a teller session for this day")
        if TellerSession.objects.filter(till=till, status__in=ACTIVE_SESSION_STATUSES).exists():
            raise _conflict("till_in_use", "This till is already in use")
        try:
            with transaction.atomic():
                ts = TellerSession.objects.create(
                    bank=bank, till=till, teller_member=member, business_date=day.date
                )
        except IntegrityError:
            raise _conflict("till_in_use", "This till is already in use") from None
        cash.create_position_rows(bank, HolderType.TELLER_SESSION.value, ts.pk)
        _audit(
            member,
            role,
            "till.open_requested",
            ts,
            session,
            after={
                "till_id": str(till.pk),
                "business_date": str(day.date),
                "floats": {c: str(v) for c, v in wanted},
            },
        )
        for currency, value in wanted:
            banking.request_vault_transfer(
                member,
                from_type=HolderType.VAULT,
                from_id=till.branch.vault.pk,
                to_type=HolderType.TELLER_SESSION,
                to_id=ts.pk,
                currency=currency,
                amount=value,
            )
        return ts


def cancel_open(member: SessionMember, session_id) -> TellerSession:
    with transaction.atomic():
        session = banking._lock_session(member)
        role = banking._role_of(member)
        banking._require(role, P_OPEN_REQUEST, session)
        ts = _locked_ts(member, session_id)
        _require_own(member, ts)
        if ts.status != TellerSessionStatus.PENDING_OPEN:
            raise _conflict("invalid_status", "Only a pending open request can be cancelled")
        if any(b > 0 for b in _balances(ts).values()):
            raise _conflict(
                "session_holds_cash", "Cash was already issued to this session; return it first"
            )
        for t in _open_transfers(ts).select_for_update(of=("self",)):
            before = {"status": t.status}
            t.status = TransferStatus.CANCELLED
            t.rejected_by = member
            t.reason = "Till open request cancelled"
            t.save(update_fields=["status", "rejected_by", "reason", "updated_at"])
            banking._audit(
                member,
                role,
                "cash.transfer_cancelled",
                t,
                session,
                before=before,
                after={"status": t.status, "reason": t.reason},
            )
        ts.status = TellerSessionStatus.CANCELLED
        ts.cancelled_at = timezone.now()
        ts.save(update_fields=["status", "cancelled_at", "updated_at"])
        _audit(
            member,
            role,
            "till.open_cancelled",
            ts,
            session,
            before={"status": TellerSessionStatus.PENDING_OPEN},
            after={"status": ts.status},
        )
        return ts


def approve_open(member: SessionMember, session_id) -> TellerSession:
    with transaction.atomic():
        session = banking._lock_session(member)
        role = banking._role_of(member)
        banking._require(role, P_OPEN_APPROVE, session)
        ts = _locked_ts(member, session_id)
        if ts.status != TellerSessionStatus.PENDING_OPEN:
            raise _conflict("invalid_status", "Session is not waiting for opening approval")
        rbac.assert_maker_checker(ts.teller_member.user_id, member.user_id)
        if ts.business_date != _open_day(member.bank).date:
            raise _conflict("stale_session", "The request belongs to another business day")
        ts.status = TellerSessionStatus.OPEN
        ts.open_approved_by = member
        ts.opened_at = timezone.now()
        ts.open_reject_note = ""
        ts.save(
            update_fields=[
                "status",
                "open_approved_by",
                "opened_at",
                "open_reject_note",
                "updated_at",
            ]
        )
        _audit(
            member,
            role,
            "till.open_approved",
            ts,
            session,
            before={"status": TellerSessionStatus.PENDING_OPEN},
            after={"status": ts.status},
        )
        return ts


def _clean_reason(reason) -> str:
    reason = (reason or "").strip()
    if not reason:
        raise LedgerError("reason_required", "A reason is required")
    if len(reason) > 300:
        raise LedgerError("text_too_long", "Reason is longer than 300 characters")
    return reason


def reject_open(member: SessionMember, session_id, reason) -> TellerSession:
    """The request stays `pending_open` with the note; the teller may wait or cancel."""
    with transaction.atomic():
        session = banking._lock_session(member)
        role = banking._role_of(member)
        banking._require(role, P_OPEN_APPROVE, session)
        ts = _locked_ts(member, session_id)
        if ts.status != TellerSessionStatus.PENDING_OPEN:
            raise _conflict("invalid_status", "Session is not waiting for opening approval")
        rbac.assert_maker_checker(ts.teller_member.user_id, member.user_id)
        ts.open_reject_note = _clean_reason(reason)
        ts.save(update_fields=["open_reject_note", "updated_at"])
        _audit(
            member,
            role,
            "till.open_rejected",
            ts,
            session,
            after={"status": ts.status, "reason": ts.open_reject_note},
        )
        return ts


# --------------------------------------------------------------------------- close


def _parse_counts(counts) -> dict[str, list[tuple[Denomination, int]]]:
    """counts: [{currency, lines: [{denomination_id, quantity}]}] -> per-currency lines."""
    by_currency: dict[str, list[tuple[Denomination, int]]] = {c: [] for c in cash.CURRENCIES}
    seen_currency = set()
    ids = {ln["denomination_id"] for item in counts or [] for ln in item.get("lines", [])}
    denoms = {d.pk: d for d in Denomination.objects.filter(pk__in=ids)}
    for item in counts or []:
        currency = item["currency"]
        if currency not in by_currency:
            raise LedgerError("invalid_currency", "Currency must be USD or SOS")
        if currency in seen_currency:
            raise LedgerError("duplicate_currency", "One count per currency")
        seen_currency.add(currency)
        used = set()
        for ln in item.get("lines", []):
            denom = denoms.get(ln["denomination_id"])
            if denom is None or denom.currency != currency:
                raise LedgerError("invalid_denomination", "Unknown denomination for this currency")
            if denom.pk in used:
                raise LedgerError("duplicate_denomination", "Each denomination only once")
            used.add(denom.pk)
            qty = ln["quantity"]
            if not isinstance(qty, int) or isinstance(qty, bool) or qty < 0 or qty > MAX_QUANTITY:
                raise LedgerError("invalid_quantity", "Quantity must be a whole number, 0 or more")
            if qty:
                by_currency[currency].append((denom, qty))
    return by_currency


def submit_close_count(member: SessionMember, session_id, counts) -> TellerSession:
    """Teller submits the denomination count (USD and SOS); the session becomes `closing`.

    A currency that is not listed counts as zero.
    """
    with transaction.atomic():
        session = banking._lock_session(member)
        role = banking._role_of(member)
        banking._require(role, P_CLOSE, session)
        ts = _locked_ts(member, session_id)
        _require_own(member, ts)
        if ts.status != TellerSessionStatus.OPEN:
            raise _conflict("invalid_status", "Only an open teller session can be closed")
        if _open_transfers(ts).exists():
            raise _conflict(
                "transfers_pending", "Finish or cancel the pending cash transfers first"
            )
        parsed = _parse_counts(counts)
        balances = _balances(ts)
        last = (
            CashCount.objects.filter(teller_session=ts, kind=CashCountKind.CLOSE)
            .order_by("-attempt")
            .values_list("attempt", flat=True)
            .first()
        )
        attempt = (last or 0) + 1
        summary = {}
        for currency in cash.CURRENCIES:
            counted = sum((d.value * q for d, q in parsed[currency]), ZERO)
            system = balances[currency]
            count = CashCount.objects.create(
                teller_session=ts,
                kind=CashCountKind.CLOSE,
                currency=currency,
                attempt=attempt,
                counted_total=counted,
                system_total=system,
                difference=counted - system,
                counted_by=member,
            )
            CashCountLine.objects.bulk_create(
                [
                    CashCountLine(cash_count=count, denomination=d, quantity=q)
                    for d, q in parsed[currency]
                ]
            )
            summary[currency] = {
                "counted": str(counted),
                "system": str(system),
                "difference": str(counted - system),
            }
        ts.status = TellerSessionStatus.CLOSING
        ts.close_requested_at = timezone.now()
        ts.close_reject_note = ""
        ts.save(update_fields=["status", "close_requested_at", "close_reject_note", "updated_at"])
        _audit(
            member,
            role,
            "till.close_requested",
            ts,
            session,
            before={"status": TellerSessionStatus.OPEN},
            after={"status": ts.status, "attempt": attempt, "counts": summary},
        )
        return ts


def reject_close(member: SessionMember, session_id, reason) -> TellerSession:
    """Back to `open`; the teller recounts. The rejected count stays as history."""
    with transaction.atomic():
        session = banking._lock_session(member)
        role = banking._role_of(member)
        banking._require(role, P_CLOSE_APPROVE, session)
        ts = _locked_ts(member, session_id)
        if ts.status != TellerSessionStatus.CLOSING:
            raise _conflict("invalid_status", "Session is not waiting for closing approval")
        rbac.assert_maker_checker(ts.teller_member.user_id, member.user_id)
        ts.status = TellerSessionStatus.OPEN
        ts.close_reject_note = _clean_reason(reason)
        ts.save(update_fields=["status", "close_reject_note", "updated_at"])
        _audit(
            member,
            role,
            "till.close_rejected",
            ts,
            session,
            before={"status": TellerSessionStatus.CLOSING},
            after={"status": ts.status, "reason": ts.close_reject_note},
        )
        return ts


def approve_close(member: SessionMember, session_id) -> TellerSession:
    """Post E1 over/short per currency, return the rest to the vault (B2), close the session."""
    with transaction.atomic():
        session = banking._lock_session(member)
        role = banking._role_of(member)
        banking._require(role, P_CLOSE_APPROVE, session)
        ts = _locked_ts(member, session_id)
        if ts.status != TellerSessionStatus.CLOSING:
            raise _conflict("invalid_status", "Session is not waiting for closing approval")
        rbac.assert_maker_checker(ts.teller_member.user_id, member.user_id)
        if _open_transfers(ts).exists():
            raise _conflict("transfers_pending", "Cash transfers are still pending")
        attempt = (
            CashCount.objects.filter(teller_session=ts, kind=CashCountKind.CLOSE)
            .order_by("-attempt")
            .values_list("attempt", flat=True)
            .first()
        )
        counts = {
            c.currency: c
            for c in CashCount.objects.select_for_update(of=("self",)).filter(
                teller_session=ts, kind=CashCountKind.CLOSE, attempt=attempt
            )
        }
        balances = _balances(ts)
        gl = {
            a.system_tag: a
            for a in GLAccount.objects.filter(
                bank_id=ts.bank_id,
                system_tag__in=("CASH_TELLER", "CASH_VAULT", "CASH_OVER", "CASH_SHORT"),
            )
        }
        vault = ts.till.branch.vault
        result = {}
        for currency in cash.CURRENCIES:
            count = counts[currency]
            if balances[currency] != count.system_total:
                raise _conflict("balance_changed", "Till cash changed after the count; recount")
            diff = count.difference
            holder = dict(cash_holder_type=HolderType.TELLER_SESSION, cash_holder_id=ts.pk)
            if diff != 0:
                if diff > 0:  # over
                    lines = [
                        ledger.LineSpec(gl["CASH_TELLER"], debit=diff, **holder),
                        ledger.LineSpec(gl["CASH_OVER"], credit=diff),
                    ]
                else:  # short
                    lines = [
                        ledger.LineSpec(gl["CASH_SHORT"], debit=-diff),
                        ledger.LineSpec(gl["CASH_TELLER"], credit=-diff, **holder),
                    ]
                entry = ledger.post_entry(
                    ts.bank,
                    lines,
                    currency=currency,
                    source_type="till_close",
                    source_id=ts.pk,
                    description=f"E1 till close {'over' if diff > 0 else 'short'}",
                    actor_member=member,
                )
                count.journal_entry = entry
            returned = count.counted_total
            if returned > 0:
                transfer = CashTransfer.objects.create(
                    bank=ts.bank,
                    from_type=HolderType.TELLER_SESSION,
                    from_id=ts.pk,
                    to_type=HolderType.VAULT,
                    to_id=vault.pk,
                    currency=currency,
                    amount=returned,
                    status=TransferStatus.POSTED,
                    requested_by=ts.teller_member,
                    approved_by_1=member,
                    approved_by_2=member,
                    reason="Till close",
                )
                transfer.journal_entry = banking._post_cash_transfer(transfer, member)
                transfer.save(update_fields=["journal_entry", "updated_at"])
                banking._audit(
                    member,
                    role,
                    "cash.transfer_posted",
                    transfer,
                    session,
                    after={**banking._transfer_dict(transfer), "source": "till_close"},
                )
            count.approved_by = member
            count.save(update_fields=["journal_entry", "approved_by", "updated_at"])
            result[currency] = {
                "difference": str(diff),
                "returned_to_vault": str(returned if returned > 0 else ZERO),
            }
        ts.status = TellerSessionStatus.CLOSED
        ts.close_approved_by = member
        ts.closed_at = timezone.now()
        ts.save(update_fields=["status", "close_approved_by", "closed_at", "updated_at"])
        _audit(
            member,
            role,
            "till.close_approved",
            ts,
            session,
            before={"status": TellerSessionStatus.CLOSING},
            after={"status": ts.status, "currencies": result},
        )
        return ts


def get_session(member: SessionMember, session_id) -> dict:
    """One session in the caller's bank; tellers only see their own."""
    role = _can_any(member, P_OPEN_REQUEST, P_CLOSE, P_OPEN_APPROVE, P_CLOSE_APPROVE)
    ts = _sessions_qs().filter(pk=session_id, bank_id=member.bank_id).first()
    if ts is None:
        raise LedgerError("not_found", "Teller session not found", status=404)
    manager_view = any(
        rbac.role_has_permission(role, c, session=member.session)
        for c in (P_OPEN_APPROVE, P_CLOSE_APPROVE)
    )
    if not manager_view and ts.teller_member_id != member.pk:
        raise rbac.PermissionDenied("Not allowed")
    return session_view(ts)


def view_by_id(ts: TellerSession) -> dict:
    return session_view(_sessions_qs().get(pk=ts.pk))
