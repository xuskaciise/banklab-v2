from django.db import models

from apps.banking.models import NoDeleteModel
from apps.ledger.models import Currency


class ProductKind(models.TextChoices):
    SAVINGS = "savings", "Savings"
    CURRENT = "current", "Current"


class BankingModel(models.TextChoices):
    CONVENTIONAL = "conventional", "Conventional"
    ISLAMIC = "islamic", "Islamic"


class AccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    CLOSED = "closed", "Closed"


class Mandate(models.TextChoices):
    ANY_ONE = "any_one", "Any one to sign"
    ALL_JOINTLY = "all_jointly", "All jointly"


ACCOUNT_NO_START = 1000001


class Product(NoDeleteModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="products")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=ProductKind.choices)
    banking_model = models.CharField(
        max_length=12, choices=BankingModel.choices, default=BankingModel.CONVENTIONAL
    )
    currency = models.CharField(max_length=3, choices=Currency.choices)
    min_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    allows_cheques = models.BooleanField(default=False)
    gl_account = models.ForeignKey(
        "ledger.GLAccount", on_delete=models.PROTECT, related_name="products"
    )

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["bank", "code"], name="uniq_product_code"),
            models.CheckConstraint(condition=models.Q(min_balance__gte=0), name="product_min_ge_0"),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class Account(NoDeleteModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="accounts")
    account_no = models.PositiveIntegerField()
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="accounts"
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="accounts")
    currency = models.CharField(max_length=3, choices=Currency.choices)
    status = models.CharField(
        max_length=6, choices=AccountStatus.choices, default=AccountStatus.ACTIVE
    )
    mandate = models.CharField(max_length=12, choices=Mandate.choices, default=Mandate.ANY_ONE)
    # Changed only by the posting service (later phase); no API writes it.
    ledger_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    created_by = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    is_seed = models.BooleanField(default=False)
    seed_owner = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["account_no"]
        constraints = [
            models.UniqueConstraint(fields=["bank", "account_no"], name="uniq_account_no"),
            models.CheckConstraint(
                condition=models.Q(ledger_balance__gte=0), name="account_balance_ge_0"
            ),
        ]
        indexes = [models.Index(fields=["bank", "customer"], name="account_customer_idx")]
