import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Currency(models.TextChoices):
    USD = "USD", "US Dollar"
    SOS = "SOS", "Somali Shilling"


class AccountType(models.TextChoices):
    ASSET = "asset", "Asset"
    LIABILITY = "liability", "Liability"
    EQUITY = "equity", "Equity"
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"


DEBIT_NORMAL_TYPES = frozenset({AccountType.ASSET, AccountType.EXPENSE})


class LedgerImmutableError(Exception):
    pass


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise LedgerImmutableError("Journal rows cannot be updated")

    def delete(self):
        raise LedgerImmutableError("Journal rows cannot be deleted")

    def bulk_update(self, *args, **kwargs):
        raise LedgerImmutableError("Journal rows cannot be updated")

    def _raw_delete(self, using):
        raise LedgerImmutableError("Journal rows cannot be deleted")


class CoaTemplate(TimeStampedModel):
    institution = models.ForeignKey(
        "accounts.Institution", on_delete=models.PROTECT, related_name="coa_templates"
    )
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["institution", "name"], name="uniq_coa_template_name")
        ]

    def __str__(self) -> str:
        return self.name


class CoaTemplateLine(TimeStampedModel):
    template = models.ForeignKey(CoaTemplate, on_delete=models.CASCADE, related_name="lines")
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=10, choices=AccountType.choices)
    parent_code = models.CharField(max_length=10, blank=True, default="")
    postable = models.BooleanField(default=False)
    system_tag = models.CharField(max_length=40, blank=True, default="")
    is_active = models.BooleanField(default=True)
    allow_negative = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["template", "code"], name="uniq_coa_line_code")
        ]


class GLAccount(TimeStampedModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="gl_accounts")
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=10, choices=AccountType.choices)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    postable = models.BooleanField(default=False)
    system_tag = models.CharField(max_length=40, blank=True, default="")
    is_active = models.BooleanField(default=True)
    allow_negative = models.BooleanField(default=False)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["bank", "code"], name="uniq_gl_account_code"),
            models.UniqueConstraint(
                fields=["bank", "system_tag"],
                condition=~models.Q(system_tag=""),
                name="uniq_gl_account_system_tag",
            ),
        ]

    @property
    def debit_normal(self) -> bool:
        return self.type in DEBIT_NORMAL_TYPES

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class GLBalance(TimeStampedModel):
    """Running balance per (GL account, currency), in the account's normal side."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="gl_balances")
    gl_account = models.ForeignKey(GLAccount, on_delete=models.PROTECT, related_name="balances")
    currency = models.CharField(max_length=3, choices=Currency.choices)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["gl_account", "currency"], name="uniq_gl_balance")
        ]


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="journal_entries")
    entry_no = models.PositiveBigIntegerField()
    business_date = models.DateField()
    currency = models.CharField(max_length=3, choices=Currency.choices)
    source_type = models.CharField(max_length=40)
    source_id = models.UUIDField(null=True, blank=True)
    description = models.CharField(max_length=300, blank=True, default="")
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    posted_by = models.ForeignKey(
        "lab.SessionMember",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    posted_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["-entry_no"]
        verbose_name_plural = "journal entries"
        constraints = [
            models.UniqueConstraint(fields=["bank", "entry_no"], name="uniq_journal_entry_no"),
            models.CheckConstraint(
                condition=models.Q(currency__in=["USD", "SOS"]), name="journal_entry_currency"
            ),
        ]
        indexes = [models.Index(fields=["bank", "business_date"], name="je_bank_date_idx")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise LedgerImmutableError("Journal entries cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LedgerImmutableError("Journal entries cannot be deleted")


class JournalLine(models.Model):
    id = models.BigAutoField(primary_key=True)
    entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name="lines")
    gl_account = models.ForeignKey(GLAccount, on_delete=models.PROTECT, related_name="lines")
    currency = models.CharField(max_length=3, choices=Currency.choices)
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
    # Sub-ledger links; enforced by the transaction services (1.5 / 1.7).
    account_id = models.UUIDField(null=True, blank=True)
    cash_holder_type = models.CharField(max_length=20, blank=True, default="")
    cash_holder_id = models.UUIDField(null=True, blank=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0, credit=0) | models.Q(credit__gt=0, debit=0)),
                name="journal_line_one_side",
            ),
            models.CheckConstraint(
                condition=models.Q(currency__in=["USD", "SOS"]), name="journal_line_currency"
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise LedgerImmutableError("Journal lines cannot be updated")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LedgerImmutableError("Journal lines cannot be deleted")
