from django.db import migrations

# Source: docs/design/permissions.md section 4 (A = allowed; approvals are enforced by limits).
# code -> (category, description, {role: scope})
T, C, M, V, A = "teller", "cso", "manager", "vault_custodian", "accountant"
ALL = "all"
OWN = "own"

MATRIX = {
    "customer.view": ("customer", "View customers", {T: ALL, C: ALL, M: ALL, A: ALL}),
    "customer.create": ("customer", "Create customers", {C: ALL, M: ALL}),
    "customer.update": ("customer", "Update customers", {C: ALL, M: ALL}),
    "account.view": ("account", "View accounts incl. balance", {T: ALL, C: ALL, M: ALL, A: ALL}),
    "account.open": ("account", "Open accounts", {C: ALL, M: ALL}),
    "account.close": ("account", "Close accounts", {C: ALL, M: ALL}),
    "account.statement": ("account", "Account statements", {T: ALL, C: ALL, M: ALL, A: ALL}),
    "chequebook.issue": ("cheque", "Issue chequebooks", {C: ALL, M: ALL}),
    "cheque.stop": ("cheque", "Stop a cheque", {C: ALL, M: ALL}),
    "till.open.request": ("till", "Request to open a till", {T: ALL}),
    "till.close": ("till", "Close own till with a count", {T: ALL}),
    "till.open.approve": ("till", "Approve till opening", {M: ALL}),
    "till.close.approve": ("till", "Approve till closing", {M: ALL}),
    "cash.vault_to_teller.request": ("cash", "Request vault to teller cash", {T: ALL, M: ALL}),
    "cash.teller_to_vault.request": ("cash", "Request teller to vault cash", {T: ALL}),
    "cash.teller_to_teller.request": ("cash", "Request teller to teller cash", {T: ALL}),
    "cash.vault.approve_custodian": ("cash", "Vault transfer first approval", {V: ALL}),
    "cash.vault.approve_manager": ("cash", "Vault transfer second approval", {M: ALL}),
    "txn.cash_deposit": ("transaction", "Post cash deposits", {T: ALL}),
    "txn.cash_withdrawal": ("transaction", "Post cash withdrawals", {T: ALL}),
    "txn.cheque_withdrawal": ("transaction", "Post cheque withdrawals", {T: ALL}),
    "txn.transfer": ("transaction", "Post transfers", {T: ALL, C: ALL}),
    "txn.reverse": ("transaction", "Reverse own transaction, same day", {T: ALL, C: ALL}),
    "approval.decide": ("approval", "Decide approvals", {M: ALL}),
    "vault.view": ("cash", "View the vault", {M: ALL, V: ALL, A: ALL}),
    "gl.view": ("report", "View the general ledger", {M: ALL, A: ALL}),
    "report.financial": ("report", "Financial reports (TB, BS, IS, GL)", {M: ALL, A: ALL}),
    "report.operational": (
        "report",
        "Operational reports (teller, branch, journal)",
        {T: OWN, C: OWN, M: ALL, A: ALL},
    ),
    "eod.run": ("eod", "Run end of day", {M: ALL}),
    "audit.view": ("audit", "View the bank audit log", {M: ALL}),
}


def seed(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    RolePermission = apps.get_model("rbac", "RolePermission")
    for code, (category, description, roles) in MATRIX.items():
        perm, _ = Permission.objects.get_or_create(
            code=code, defaults={"category": category, "description": description}
        )
        for role, scope in roles.items():
            RolePermission.objects.get_or_create(
                role=role, permission=perm, defaults={"scope": scope}
            )


class Migration(migrations.Migration):
    dependencies = [("rbac", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
