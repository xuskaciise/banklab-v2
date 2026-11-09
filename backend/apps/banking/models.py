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


# --------------------------------------------------------------------------- transactions (1.9)


class TxnType(models.TextChoices):
    CASH_DEPOSIT = "cash_deposit", "Cash deposit"
    CASH_WITHDRAWAL = "cash_withdrawal", "Cash withdrawal"
    TRANSFER = "transfer", "Transfer"
    CHEQUE_WITHDRAWAL = "cheque_withdrawal", "Cheque withdrawal"
    REVERSAL = "reversal", "Reversal"


class TxnStatus(models.TextChoices):
    PENDING_APPROVAL = "pending_approval", "Pending approval"
    POSTED = "posted", "Posted"
    REJECTED = "rejected", "Rejected"
    REVERSED = "reversed", "Reversed"


class Transaction(NoDeleteModel):
    """Customer transaction (C1, C2, C4, D1). Status changes only through the services;
    the money itself lives in the linked journal entry."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="transactions")
    ref_no = models.CharField(max_length=40)
    seq = models.PositiveIntegerField()
    type = models.CharField(max_length=20, choices=TxnType.choices)
    status = models.CharField(max_length=16, choices=TxnStatus.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    account = models.ForeignKey(
        "products.Account", on_delete=models.PROTECT, related_name="transactions"
    )
    counter_account = models.ForeignKey(
        "products.Account", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    teller_session = models.ForeignKey(
        TellerSession, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    party_name = models.CharField(max_length=200, blank=True, default="")
    party_id_no = models.CharField(max_length=60, blank=True, default="")
    party_phone = models.CharField(max_length=30, blank=True, default="")
    narration = models.CharField(max_length=300, blank=True, default="")
    business_date = models.DateField()
    created_by = models.ForeignKey("lab.SessionMember", on_delete=models.PROTECT, related_name="+")
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversals"
    )
    cheque = models.ForeignKey(
        "Cheque", null=True, blank=True, on_delete=models.PROTECT, related_name="withdrawals"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["bank", "ref_no"], name="uniq_txn_ref_no"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="txn_amount_gt_0"),
            models.UniqueConstraint(
                fields=["reversal_of"],
                condition=models.Q(reversal_of__isnull=False),
                name="uniq_txn_reversal_of",
            ),
            # a cheque backs at most one live (pending or posted) withdrawal: paid once only
            models.UniqueConstraint(
                fields=["cheque"],
                condition=models.Q(cheque__isnull=False, status__in=["pending_approval", "posted"]),
                name="uniq_txn_live_cheque",
            ),
        ]
        indexes = [models.Index(fields=["bank", "business_date"], name="txn_bank_date_idx")]


class LimitRule(NoDeleteModel):
    """Largest amount a role may post alone; above it the transaction needs approval."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="limit_rules")
    role = models.CharField(max_length=20)
    txn_type = models.CharField(max_length=20, choices=TxnType.choices)
    currency = models.CharField(max_length=3, choices=Currency.choices)
    max_amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        ordering = ["role", "txn_type", "currency"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank", "role", "txn_type", "currency"], name="uniq_limit_rule"
            ),
            models.CheckConstraint(condition=models.Q(max_amount__gte=0), name="limit_max_ge_0"),
        ]


class ApprovalReason(models.TextChoices):
    LIMIT = "limit", "Over limit"
    TILL_OPEN = "till_open", "Till open"
    TILL_CLOSE = "till_close", "Till close"
    DUAL_CONTROL = "dual_control", "Dual control"
    TELLER_TO_TELLER = "teller_to_teller", "Teller to teller"


class ApprovalStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Approval(NoDeleteModel):
    """Generic maker-checker queue entry. Only `limit` on a transaction is used so far."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="approvals")
    subject_type = models.CharField(max_length=30)
    subject_id = models.UUIDField()
    reason = models.CharField(max_length=20, choices=ApprovalReason.choices)
    requested_by = models.ForeignKey(
        "lab.SessionMember", on_delete=models.PROTECT, related_name="+"
    )
    decided_by = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    status = models.CharField(
        max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank", "subject_type", "subject_id", "reason"],
                condition=models.Q(status="pending"),
                name="uniq_pending_approval",
            ),
        ]
        indexes = [models.Index(fields=["bank", "status"], name="approval_bank_status_idx")]


# --------------------------------------------------------------------------- cheques


class ChequeStatus(models.TextChoices):
    ISSUED = "issued", "Issued"
    PAID = "paid", "Paid"
    STOPPED = "stopped", "Stopped"


class Chequebook(NoDeleteModel):
    """A book of consecutive cheque numbers issued to one account (no journal entry)."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="chequebooks")
    account = models.ForeignKey(
        "products.Account", on_delete=models.PROTECT, related_name="chequebooks"
    )
    first_no = models.PositiveIntegerField()
    last_no = models.PositiveIntegerField()
    leaves = models.PositiveSmallIntegerField()
    issued_by = models.ForeignKey("lab.SessionMember", on_delete=models.PROTECT, related_name="+")
    issued_at = models.DateTimeField()

    class Meta:
        ordering = ["-issued_at"]
        indexes = [models.Index(fields=["bank", "account"], name="chequebook_account_idx")]


class Cheque(NoDeleteModel):
    """One leaf. `transaction` holds the withdrawal that reserved or paid it (cleared again
    when that withdrawal is rejected or reversed); `Transaction.cheque` keeps the history."""

    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="cheques")
    chequebook = models.ForeignKey(Chequebook, on_delete=models.PROTECT, related_name="cheques")
    number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=8, choices=ChequeStatus.choices, default=ChequeStatus.ISSUED
    )
    transaction = models.OneToOneField(
        "Transaction", null=True, blank=True, on_delete=models.PROTECT, related_name="paid_cheque"
    )
    stopped_by = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    stopped_at = models.DateTimeField(null=True, blank=True)
    stop_reason = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["bank", "number"], name="uniq_cheque_no_per_bank"),
        ]
