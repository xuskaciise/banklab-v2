"""Bank cash provisioning: main branch, vault and the opening-capital entry (A1).

Used when a bank is created and by the `backfill_bank_vaults` command. Idempotent.
"""

from decimal import Decimal

from django.db import transaction

from apps.ledger import services as ledger
from apps.ledger.models import GLAccount, JournalEntry

from . import cash
from .models import Branch

MAIN_BRANCH_CODE = "001"
MAIN_BRANCH_NAME = "Main Branch"
OPENING_SOURCE = "opening_capital"


def opening_capital(session) -> dict[str, Decimal]:
    return {"USD": session.opening_capital_usd, "SOS": session.opening_capital_sos}


@transaction.atomic
def provision_bank_cash(bank, session) -> Branch:
    """Create the main branch + vault + zero positions and post A1 per currency
    (Dr 1110 [vault] / Cr 3100, actor: system). Safe to call again: nothing is duplicated."""
    branch = Branch.objects.filter(bank=bank).order_by("code").first()
    if branch is None:
        branch = cash.create_branch(bank, MAIN_BRANCH_CODE, MAIN_BRANCH_NAME)
    vault = branch.vault
    vault_gl = GLAccount.objects.get(bank=bank, system_tag="CASH_VAULT")
    capital_gl = GLAccount.objects.get(bank=bank, system_tag="CAPITAL")
    for currency, amount in opening_capital(session).items():
        if amount <= 0:
            continue
        if JournalEntry.objects.filter(
            bank=bank, source_type=OPENING_SOURCE, currency=currency
        ).exists():
            continue
        ledger.post_entry(
            bank,
            [
                ledger.LineSpec(
                    vault_gl, debit=amount, cash_holder_type="vault", cash_holder_id=vault.pk
                ),
                ledger.LineSpec(capital_gl, credit=amount),
            ],
            currency=currency,
            source_type=OPENING_SOURCE,
            source_id=bank.pk,
            description=f"Opening capital {currency}",
        )
    return branch
