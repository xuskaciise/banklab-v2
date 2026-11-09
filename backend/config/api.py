from django.db import connection
from ninja import NinjaAPI, Schema

from apps.accounts.api import router as auth_router
from apps.accounts.auth import ActiveSessionAuth
from apps.accounts.services import AccountsError
from apps.audit.api import router as audit_router
from apps.banking.api import router as banking_router
from apps.banking.api import student_router as banking_student_router
from apps.banking.txn_api import txn_router
from apps.customers.api import router as customers_router
from apps.customers.api import student_router as customers_student_router
from apps.lab.api import router as lab_router
from apps.lab.api import student_router
from apps.lab.services import LabError
from apps.ledger.api import router as ledger_router
from apps.ledger.api import student_router as ledger_student_router
from apps.ledger.services import LedgerError
from apps.products.api import student_router as products_student_router
from apps.rbac.services import RbacError

api = NinjaAPI(title="BankLab API", version="0.1.0", auth=ActiveSessionAuth())
api.add_router("/auth", auth_router)
api.add_router("/audit", audit_router)
api.add_router("", lab_router)
api.add_router("", student_router)
api.add_router("", ledger_router)
api.add_router("", ledger_student_router)
api.add_router("", banking_router)
api.add_router("", banking_student_router)
api.add_router("", txn_router)
api.add_router("", customers_router)
api.add_router("", customers_student_router)
api.add_router("", products_student_router)


@api.exception_handler(AccountsError)
def accounts_error(request, exc):
    return api.create_response(request, {"detail": exc.message}, status=exc.status)


@api.exception_handler(RbacError)
def rbac_error(request, exc):
    return api.create_response(request, {"detail": exc.message}, status=exc.status)


class HealthOut(Schema):
    status: str
    database: bool


@api.get("/health", response=HealthOut, tags=["system"], auth=None)
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database = True
    except Exception:
        database = False
    return {"status": "ok", "database": database}


@api.exception_handler(LabError)
def lab_error(request, exc):
    return api.create_response(request, {"detail": exc.message}, status=exc.status)


@api.exception_handler(LedgerError)
def ledger_error(request, exc):
    body = {"detail": exc.message, "code": exc.code, **getattr(exc, "extra", {})}
    return api.create_response(request, body, status=exc.status)
