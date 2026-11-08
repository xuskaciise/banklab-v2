from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.ledger.models import Currency


class BusinessDayStatus(models.TextChoices):
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class BusinessDay(TimeStampedModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="business_days")
    date = models.DateField()
    status = models.CharField(
        max_length=6, choices=BusinessDayStatus.choices, default=BusinessDayStatus.OPEN
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["bank", "date"], name="uniq_business_day"),
            models.UniqueConstraint(
                fields=["bank"],
                condition=models.Q(status="open"),
                name="uniq_open_business_day_per_bank",
            ),
        ]


# --------------------------------------------------------------------------- cash & vault


class HolderType(models.TextChoices):
    VAULT = "vault", "Vault"
    TELLER_SESSION = "teller_session", "Teller session"


class NoDeleteQuerySet(models.QuerySet):
    def delete(self):
        raise NotImplementedError("Financial records are never deleted")

    def _raw_delete(self, using):
        raise NotImplementedError("Financial records are never deleted")


class NoDeleteModel(TimeStampedModel):
    objects = NoDeleteQuerySet.as_manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Financial records are never deleted")


class Branch(NoDeleteModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="branches")
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "branches"
        constraints = [models.UniqueConstraint(fields=["bank", "code"], name="uniq_branch_code")]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class Vault(NoDeleteModel):
    """Physical vault, one per branch. Its cash lives in `CashPosition` rows."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="vaults")
    branch = models.OneToOneField(Branch, on_delete=models.PROTECT, related_name="vault")

    class Meta:
        ordering = ["branch__code"]


class Till(NoDeleteModel):
    """Physical teller drawer; cash is held per teller session (1.8), not on the till."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="tills")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="tills")
    code = models.CharField(max_length=10)

    class Meta:
        ordering = ["code"]
        constraints = [models.UniqueConstraint(fields=["bank", "code"], name="uniq_till_code")]


class DenominationKind(models.TextChoices):
    NOTE = "note", "Note"
    COIN = "coin", "Coin"


class Denomination(models.Model):
    """Global lookup of note/coin values per currency."""

    id = models.BigAutoField(primary_key=True)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    kind = models.CharField(max_length=4, choices=DenominationKind.choices)

    class Meta:
        ordering = ["currency", "-value"]
        constraints = [
            models.UniqueConstraint(fields=["currency", "value"], name="uniq_denomination")
        ]


class CashPosition(NoDeleteModel):
    """Cash on hand per holder and currency. Written ONLY by the ledger posting service."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="cash_positions")
    holder_type = models.CharField(max_length=20, choices=HolderType.choices)
    holder_id = models.UUIDField()
    currency = models.CharField(max_length=3, choices=Currency.choices)
    balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["bank", "holder_type", "holder_id", "currency"], name="uniq_cash_position"
            ),
            models.CheckConstraint(condition=models.Q(balance__gte=0), name="cash_position_gte_0"),
        ]


class TransferStatus(models.TextChoices):
    PENDING = "pending", "Pending custodian approval"
    CUSTODIAN_APPROVED = "custodian_approved", "Awaiting manager approval"
    POSTED = "posted", "Posted"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled by requester"


class CashTransfer(NoDeleteModel):
    """Vault <-> teller cash movement under dual control; posted via the ledger."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="cash_transfers")
    from_type = models.CharField(max_length=20, choices=HolderType.choices)
    from_id = models.UUIDField()
    to_type = models.CharField(max_length=20, choices=HolderType.choices)
    to_id = models.UUIDField()
    currency = models.CharField(max_length=3, choices=Currency.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=TransferStatus.choices, default=TransferStatus.PENDING
    )
    requested_by = models.ForeignKey(
        "lab.SessionMember", on_delete=models.PROTECT, related_name="+"
    )
    approved_by_1 = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_by_2 = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    rejected_by = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.CharField(max_length=300, blank=True, default="")
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="cash_transfer_amount_gt_0"
            ),
            models.CheckConstraint(
                condition=~models.Q(from_type=models.F("to_type"), from_id=models.F("to_id")),
                name="cash_transfer_distinct_holders",
            ),
        ]


# --------------------------------------------------------------------------- teller sessions


class TellerSessionStatus(models.TextChoices):
    PENDING_OPEN = "pending_open", "Waiting for opening approval"
    OPEN = "open", "Open"
    CLOSING = "closing", "Waiting for closing approval"
    CLOSED = "closed", "Closed"
    CANCELLED = "cancelled", "Request cancelled"


# Sessions that still occupy a till.
ACTIVE_SESSION_STATUSES = (
    TellerSessionStatus.PENDING_OPEN,
    TellerSessionStatus.OPEN,
    TellerSessionStatus.CLOSING,
)


class TellerSession(NoDeleteModel):
    """One teller on one till for one business day. Holds the teller's cash (CashPosition)."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="teller_sessions")
    till = models.ForeignKey(Till, on_delete=models.PROTECT, related_name="teller_sessions")
    teller_member = models.ForeignKey(
        "lab.SessionMember", on_delete=models.PROTECT, related_name="teller_sessions"
    )
    business_date = models.DateField()
    status = models.CharField(
        max_length=12, choices=TellerSessionStatus.choices, default=TellerSessionStatus.PENDING_OPEN
    )
    open_requested_at = models.DateTimeField(auto_now_add=True)
    open_approved_by = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    opened_at = models.DateTimeField(null=True, blank=True)
    open_reject_note = models.CharField(max_length=300, blank=True, default="")
    close_requested_at = models.DateTimeField(null=True, blank=True)
    close_approved_by = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reject_note = models.CharField(max_length=300, blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-business_date", "-open_requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank", "teller_member", "business_date"],
                condition=~models.Q(status="cancelled"),
                name="uniq_teller_session_per_day",
            ),
            models.UniqueConstraint(
                fields=["till"],
                condition=models.Q(status__in=["pending_open", "open", "closing"]),
                name="uniq_active_session_per_till",
            ),
        ]


class CashCountKind(models.TextChoices):
    OPEN = "open", "Opening count"
    CLOSE = "close", "Closing count"


class CashCount(NoDeleteModel):
    """Denomination count of one currency; `difference` = counted - system (over/short).

    A rejected closing count stays as history; the teller's recount gets the next `attempt`.
    """

    teller_session = models.ForeignKey(
        TellerSession, on_delete=models.PROTECT, related_name="counts"
    )
    kind = models.CharField(max_length=5, choices=CashCountKind.choices)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    attempt = models.PositiveSmallIntegerField(default=1)
    counted_total = models.DecimalField(max_digits=18, decimal_places=2)
    system_total = models.DecimalField(max_digits=18, decimal_places=2)
    difference = models.DecimalField(max_digits=18, decimal_places=2)
    counted_by = models.ForeignKey("lab.SessionMember", on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["teller_session_id", "kind", "attempt", "currency"]
        constraints = [
            models.UniqueConstraint(
                fields=["teller_session", "kind", "currency", "attempt"], name="uniq_cash_count"
            ),
        ]


class CashCountLine(NoDeleteModel):
    cash_count = models.ForeignKey(CashCount, on_delete=models.PROTECT, related_name="lines")
    denomination = models.ForeignKey(Denomination, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()

    class Meta:
        ordering = ["-denomination__value"]
        constraints = [
            models.UniqueConstraint(
                fields=["cash_count", "denomination"], name="uniq_cash_count_line"
            ),
        ]
