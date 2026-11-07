from django.db import connection
from ninja import NinjaAPI, Schema

from apps.accounts.api import router as auth_router
from apps.accounts.auth import ActiveSessionAuth
from apps.accounts.services import AccountsError

api = NinjaAPI(title="BankLab API", version="0.1.0", auth=ActiveSessionAuth())
api.add_router("/auth", auth_router)


@api.exception_handler(AccountsError)
def accounts_error(request, exc):
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
