from django.db import models


class BankRole(models.TextChoices):
    TELLER = "teller", "Teller"
    CSO = "cso", "Customer Service Officer"
    MANAGER = "manager", "Supervisor / Manager"
    VAULT_CUSTODIAN = "vault_custodian", "Vault Custodian"
    ACCOUNTANT = "accountant", "Accountant"


class PermissionScope(models.TextChoices):
    ALL = "all", "All rows in the bank"
    OWN = "own", "Own work only"


class Permission(models.Model):
    code = models.CharField(max_length=80, primary_key=True)
    description = models.CharField(max_length=200)
    category = models.CharField(max_length=40)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class RolePermission(models.Model):
    """Default grant of a permission to a bank role (docs/design/permissions.md section 4)."""

    role = models.CharField(max_length=20, choices=BankRole.choices)
    permission = models.ForeignKey(
        Permission, on_delete=models.CASCADE, related_name="role_permissions"
    )
    scope = models.CharField(
        max_length=3, choices=PermissionScope.choices, default=PermissionScope.ALL
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uniq_role_permission")
        ]

    def __str__(self) -> str:
        return f"{self.role}:{self.permission_id}({self.scope})"
