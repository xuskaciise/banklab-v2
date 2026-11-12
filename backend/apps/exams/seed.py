"""Per-student exam seed data: own customer(s) + account(s) with an opening balance.

Posted as template A2 (Dr 1110 Cash in Vault [vault] / Cr deposit GL [account]) through the
ledger posting service, so the books stay balanced. Rows are `is_seed` with
`seed_owner = member`, which only that student (and the instructor) can see. Idempotent:
the number of seed accounts already owned by the member decides what is still missing.
"""

import hashlib
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.banking.models import BusinessDay, BusinessDayStatus, Vault
from apps.customers.models import Customer, CustomerParty, CustomerType, Party, Relation
from apps.customers.services import _next_cif_no
from apps.lab.models import Session, SessionMember, SessionStatus
from apps.ledger import services as ledger
from apps.ledger.models import GLAccount
from apps.ledger.services import LedgerError
from apps.products.models import Account, Product
from apps.products.services import _next_account_no

from .checks import SEED_SOURCE

FIRST = ["Amina", "Hassan", "Fadumo", "Abdi", "Halima", "Mohamed", "Sagal", "Yusuf", "Ifrah",
         "Omar", "Hodan", "Ahmed", "Maryan", "Ali", "Nasra", "Ibrahim", "Khadija", "Abdullahi",
         "Zamzam", "Farah"]  # fmt: skip
LAST = ["Nur", "Warsame", "Jama", "Osman", "Dahir", "Elmi", "Hirsi", "Abdille", "Guled", "Isse",
        "Roble", "Samatar", "Duale", "Aden", "Mire", "Qorane", "Barre", "Hared", "Sheikh",
        "Egal"]  # fmt: skip
PRODUCT_CODES = ("SAV-USD", "SAV-SOS", "CUR-USD", "CUR-SOS")
MAX_SPECS = 10


def clean_seed(raw) -> list[dict]:
    """Validate the exam's seed config; returns a normalised list (ValueError when bad)."""
    if raw in (None, ""):
        return []
    if not isinstance(raw, list) or len(raw) > MAX_SPECS:
        raise ValueError(f"seed must be a list of at most {MAX_SPECS} accounts")
    out = []
    for spec in raw:
        if not isinstance(spec, dict):
            raise ValueError("Each seed account must be an object")
        code = spec.get("product_code")
        if code not in PRODUCT_CODES:
            raise ValueError(f"product_code must be one of: {', '.join(PRODUCT_CODES)}")
        try:
            amount = Decimal(str(spec.get("amount"))).quantize(Decimal("0.01"))
        except Exception:
            raise ValueError("Seed amount must be a number") from None
        if amount <= 0 or amount > Decimal("1000000000"):
            raise ValueError("Seed amount must be greater than zero")
        out.append({"product_code": code, "amount": str(amount), "vary": bool(spec.get("vary"))})
    return out


def _digest(member: SessionMember, index: int) -> int:
    return int(hashlib.sha256(f"{member.pk}:{index}".encode()).hexdigest(), 16)


def _opening(member: SessionMember, index: int, spec: dict) -> Decimal:
    amount = Decimal(spec["amount"])
    if spec.get("vary"):  # up to +9 steps of 5, so neighbours cannot copy balances
        amount += Decimal(5) * (_digest(member, index) % 10)
    return amount


def ensure_member_seed(exam, member: SessionMember, *, actor=None) -> int:
    """Create the member's missing seed accounts; returns how many were created.

    Does nothing (0) when there is no seed config, the member is not placed in a bank or the
    session is not active (the seed is created at Start instead). When a seed is due but
    cannot be created (no vault, no 1110 GL, no open business day, missing product, posting
    refused) it raises a 409 `LedgerError` with code `exam_seed_failed`."""
    try:
        return _ensure(exam, member, actor)
    except LedgerError as exc:
        if exc.code == "exam_seed_failed":
            raise
        raise LedgerError(
            "exam_seed_failed", f"Exam data could not be prepared ({exc.message})", status=409
        ) from exc


def _ensure(exam, member: SessionMember, actor) -> int:
    specs = exam.seed or []
    if not specs or member.bank_id is None:
        return 0
    with transaction.atomic():
        # Lock order: session -> member -> bank (same as the posting service).
        Session.objects.select_for_update(no_key=True).get(pk=member.session_id)
        member = (
            SessionMember.objects.select_for_update(of=("self",))
            .select_related("session__lab_class", "bank", "user")
            .get(pk=member.pk)
        )
        if member.session.status != SessionStatus.ACTIVE:
            return 0
        bank = member.bank
        have = Account.objects.filter(seed_owner=member, is_seed=True).count()
        if have >= len(specs):
            return 0
        vault = Vault.objects.filter(bank=bank).first()
        vault_gl = GLAccount.objects.filter(bank=bank, system_tag="CASH_VAULT").first()
        if vault is None or vault_gl is None:
            raise LedgerError("exam_seed_failed", "The bank has no vault cash account", status=409)
        if not BusinessDay.objects.filter(bank=bank, status=BusinessDayStatus.OPEN).exists():
            raise LedgerError("exam_seed_failed", "The bank has no open business day", status=409)
        created = 0
        for index in range(have, len(specs)):
            spec = specs[index]
            product = Product.objects.filter(bank=bank, code=spec["product_code"]).first()
            if product is None:
                raise LedgerError("seed_product_missing", "Seed product not found", status=409)
            amount = _opening(member, index, spec)
            h = _digest(member, index)
            name = f"{FIRST[h % 20]} {LAST[(h // 20) % 20]}"
            customer = Customer.objects.create(
                bank=bank,
                cif_no=_next_cif_no(bank.pk),
                type=CustomerType.INDIVIDUAL,
                display_name=name,
                phone=f"+25261{h % 10_000_000:07d}",
                address="Mogadishu",
                is_seed=True,
                seed_owner=member,
            )
            party = Party.objects.create(bank=bank, full_name=name, phone=customer.phone)
            CustomerParty.objects.create(
                bank=bank, customer=customer, party=party, relation=Relation.OWNER, can_sign=True
            )
            account = Account.objects.create(
                bank=bank,
                account_no=_next_account_no(bank.pk),
                customer=customer,
                product=product,
                currency=product.currency,
                is_seed=True,
                seed_owner=member,
                opened_at=timezone.now(),
            )
            ledger.post_entry(
                bank,
                [
                    ledger.LineSpec(
                        vault_gl, debit=amount, cash_holder_type="vault", cash_holder_id=vault.pk
                    ),
                    ledger.LineSpec(product.gl_account, credit=amount, account_id=account.pk),
                ],
                currency=product.currency,
                source_type=SEED_SOURCE,
                source_id=account.pk,
                description=f"Exam seed opening balance, account {account.account_no}",
            )
            created += 1
        if created:
            audit.record(
                "exam.seeded",
                actor=actor,
                actor_role=getattr(actor, "platform_role", "") or "system",
                entity=("session_member", member.pk),
                after={"accounts": created},
                session_id=member.session_id,
                bank_id=bank.pk,
                institution_id=member.session.lab_class.institution_id,
            )
        return created
