import uuid

from django.db import models

from apps.banking.models import NoDeleteModel


class CustomerType(models.TextChoices):
    INDIVIDUAL = "individual", "Individual"
    COMPANY = "company", "Company"
    JOINT = "joint", "Joint"
    NGO = "ngo", "NGO"


class Relation(models.TextChoices):
    OWNER = "owner", "Owner"
    JOINT_HOLDER = "joint_holder", "Joint holder"
    SIGNATORY = "signatory", "Signatory"
    DIRECTOR = "director", "Director"


class Sex(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"


class DocType(models.TextChoices):
    NATIONAL_ID = "national_id", "National ID"
    PASSPORT = "passport", "Passport"
    LOCAL_LETTER = "local_letter", "Local letter"


def _upload_path(kind: str, instance, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"customers/{instance.bank_id}/{kind}/{uuid.uuid4().hex}.{ext[:5]}"


def photo_path(instance, filename):
    return _upload_path("photo", instance, filename)


def signature_path(instance, filename):
    return _upload_path("signature", instance, filename)


def document_path(instance, filename):
    return _upload_path("document", instance, filename)


class Customer(NoDeleteModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="customers")
    cif_no = models.PositiveIntegerField()
    type = models.CharField(max_length=10, choices=CustomerType.choices)
    display_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True, default="")
    email = models.CharField(max_length=254, blank=True, default="")
    address = models.CharField(max_length=300, blank=True, default="")
    reg_no = models.CharField(max_length=60, blank=True, default="")
    created_by = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    is_seed = models.BooleanField(default=False)
    seed_owner = models.ForeignKey(
        "lab.SessionMember", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["cif_no"]
        constraints = [
            models.UniqueConstraint(fields=["bank", "cif_no"], name="uniq_customer_cif_no"),
        ]
        indexes = [models.Index(fields=["bank", "display_name"], name="customer_name_idx")]


class Party(NoDeleteModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="parties")
    full_name = models.CharField(max_length=200)
    sex = models.CharField(max_length=6, choices=Sex.choices, blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True, default="")
    mother_name = models.CharField(max_length=200, blank=True, default="")
    guardian_phone = models.CharField(max_length=30, blank=True, default="")
    photo = models.FileField(upload_to=photo_path, null=True, blank=True)
    signature = models.FileField(upload_to=signature_path, null=True, blank=True)

    class Meta:
        verbose_name_plural = "parties"
        ordering = ["created_at"]


class CustomerParty(NoDeleteModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="+")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="links")
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="links")
    relation = models.CharField(max_length=12, choices=Relation.choices)
    can_sign = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "party", "relation"], name="uniq_customer_party_relation"
            ),
        ]


class IdentityDocument(NoDeleteModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="+")
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="documents")
    type = models.CharField(max_length=14, choices=DocType.choices)
    number = models.CharField(max_length=60)
    issue_date = models.DateField()
    expiry_date = models.DateField()
    file = models.FileField(upload_to=document_path, null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expiry_date__gt=models.F("issue_date")),
                name="identity_document_expiry_after_issue",
            ),
        ]


class NextOfKin(NoDeleteModel):
    bank = models.ForeignKey("lab.Bank", on_delete=models.PROTECT, related_name="+")
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="next_of_kin")
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True, default="")
    relationship = models.CharField(max_length=60)

    class Meta:
        verbose_name_plural = "next of kin"
        ordering = ["created_at"]
