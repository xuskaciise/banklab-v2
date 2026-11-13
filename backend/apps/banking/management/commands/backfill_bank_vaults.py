from django.core.management.base import BaseCommand

from apps.banking.models import Branch, BusinessDay, BusinessDayStatus
from apps.banking.provisioning import provision_bank_cash
from apps.lab.models import Bank, SessionStatus


class Command(BaseCommand):
    help = (
        "Create the main branch, vault, zero cash positions and the opening-capital entry (A1) "
        "for banks that have no branch yet. Idempotent; archived sessions are skipped."
    )

    def handle(self, *args, **options):
        done = skipped = 0
        banks = Bank.objects.filter(branches__isnull=True).select_related("session")
        for bank in banks:
            has_day = BusinessDay.objects.filter(bank=bank, status=BusinessDayStatus.OPEN).exists()
            if bank.session.status != SessionStatus.ACTIVE or not has_day:
                skipped += 1
                self.stdout.write(f"skipped bank {bank.pk} (session not active / no open day)")
                continue
            provision_bank_cash(bank, bank.session)
            done += 1
        total = Branch.objects.count()
        self.stdout.write(f"backfilled {done} bank(s), skipped {skipped}; branches now {total}")
