from django.db import connection
from ninja import NinjaAPI, Schema

api = NinjaAPI(title="BankLab API", version="0.1.0")


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
