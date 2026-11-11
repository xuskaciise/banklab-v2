"""Deposit products and customer accounts.

Role permission, row visibility and the archived-session guard are enforced here on the
server; every write is audited. Nothing is deleted: an account is closed, never removed, and
a closed account stays closed. `ledger_balance` is never written here (posting service only).

Lock order: session -> bank row (account numbering) | account row.
"""

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.audit import services as audit
from apps.core import platform
from apps.customers import services as customers
from apps.lab.models import Bank, SessionMember
from apps.ledger.services import LedgerError

from .models import ACCOUNT_NO_START, Account, AccountStatus, Mandate, Product

PERM_VIEW = "account.view"
PERM_OPEN = "account.open"
PERM_CLOSE = "account.close"


def _bad(code: str, message: str, status: int = 400, **extra) -> LedgerError:
    err = LedgerError(code, message, status=status)
    err.extra = extra
    return err


def _not_found(what: str = "Account") -> LedgerError:
    return LedgerError("not_found", f"{what} not found", status=404)


def _audit(member, role, action, session, account, *, before=None, after=None):
    audit.record(
        action,
        actor=member.user,
        actor_role=role,
        entity=("account", account.pk),
        before=before,
        after=after,
        session_id=session.pk,
        bank_id=account.bank_id,
        institution_id=session.lab_class.institution_id,
    )


def _account_dict(a: Account) -> dict:
    return {
        "account_no": a.account_no,
        "customer_id": str(a.customer_id),
        "product_id": str(a.product_id),
        "currency": a.currency,
        "status": a.status,
        "mandate": a.mandate,
        "ledger_balance": str(a.ledger_balance),
    }


def _visible(member: SessionMember, scope: str):
    """Accounts of the member's bank; "own" scope: own work + shared / own seed data."""
    qs = Account.objects.filter(bank_id=member.bank_id)
    if scope == "own":
        qs = qs.filter(
            Q(created_by=member) | Q(seed_owner=member) | Q(is_seed=True, seed_owner__isnull=True)
        )
    return qs


def _with_related(qs):
    return qs.select_related("customer", "product")


# --------------------------------------------------------------------------- reads


def list_products(member: SessionMember):
    customers._read_scope(member, PERM_VIEW)
    return Product.objects.filter(bank_id=member.bank_id).order_by("code")


def list_accounts(member: SessionMember, *, customer_id=None, status=None, account_no=None):
    _, _, scope = customers._read_scope(member, PERM_VIEW)
    qs = _visible(member, scope)
    if account_no is not None:
        qs = qs.filter(account_no=account_no)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    if status:
        if status not in AccountStatus.values:
            raise _bad(
                "invalid_account", f"Status must be one of: {', '.join(AccountStatus.values)}"
            )
        qs = qs.filter(status=status)
    return _with_related(qs).order_by("account_no")


def get_account(member: SessionMember, account_id) -> Account:
    _, _, scope = customers._read_scope(member, PERM_VIEW)
    account = _with_related(_visible(member, scope)).filter(pk=account_id).first()
    if account is None:
        raise _not_found()
    return account


# --------------------------------------------------------------------------- writes


def _next_account_no(bank_id) -> int:
    """Sequential per bank; the bank row lock serialises concurrent opens."""
    Bank.objects.select_for_update(of=("self",)).get(pk=bank_id)
    current = Account.objects.filter(bank_id=bank_id).aggregate(m=Max("account_no"))["m"]
    return (current or ACCOUNT_NO_START - 1) + 1


def open_account(member: SessionMember, *, customer_id, product_id, mandate=Mandate.ANY_ONE):
    with transaction.atomic():
        session, role, scope = customers._write_ctx(member, PERM_OPEN)
        if mandate not in Mandate.values:
            raise _bad("invalid_account", f"Mandate must be one of: {', '.join(Mandate.values)}")
        customer = (
            customers._detail_qs(customers._visible(member, scope))
            .select_for_update(of=("self",))
            .filter(pk=customer_id)
            .first()
        )
        if customer is None:
            raise _not_found("Customer")
        product = Product.objects.filter(pk=product_id, bank_id=member.bank_id).first()
        if product is None:
            raise _not_found("Product")
        platform.require_currency_enabled(product.currency)
        missing = customers.kyc_missing(customer)
        if missing:
            raise _bad(
                "kyc_incomplete",
                "Customer KYC is incomplete; complete it before opening an account",
                kyc_missing=[
                    {**m, "party_id": str(m["party_id"]) if m["party_id"] else None}
                    for m in missing
                ],
            )
        account = Account.objects.create(
            bank_id=member.bank_id,
            account_no=_next_account_no(member.bank_id),
            customer=customer,
            product=product,
            currency=product.currency,
            mandate=mandate,
            created_by=member,
            opened_at=timezone.now(),
        )
        _audit(member, role, "account.opened", session, account, after=_account_dict(account))
        return _with_related(Account.objects).get(pk=account.pk)


def close_account(member: SessionMember, account_id) -> Account:
    with transaction.atomic():
        session, role, scope = customers._write_ctx(member, PERM_CLOSE)
        account = (
            _visible(member, scope).select_for_update(of=("self",)).filter(pk=account_id).first()
        )
        if account is None:
            raise _not_found()
        if account.status != AccountStatus.ACTIVE:
            raise _bad("account_not_active", "Account is already closed", status=409)
        if account.ledger_balance != 0:
            raise _bad(
                "balance_not_zero", "Account balance must be zero before closing", status=409
            )
        before = _account_dict(account)
        account.status = AccountStatus.CLOSED
        account.closed_at = timezone.now()
        account.save(update_fields=["status", "closed_at", "updated_at"])
        _audit(
            member,
            role,
            "account.closed",
            session,
            account,
            before=before,
            after=_account_dict(account),
        )
        return _with_related(Account.objects).get(pk=account.pk)


def visible_accounts(member: SessionMember, scope: str):
    """Accounts the member may read in `scope` ("all" | "own"); for report services."""
    return _visible(member, scope)
