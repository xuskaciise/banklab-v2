"""Row-lock helpers for the session row."""

from django.db import connection

from .models import Session


def lock_session_shared(session_id, *, select_related: tuple[str, ...] = ()) -> Session:
    """Take `FOR SHARE` on the session row and return it (fresh, post-lock read).

    Every write that must not run against an archived / inactive session (all postings and
    teller/vault writes) takes this shared lock instead of an exclusive one: any number of
    writers hold it together, so postings in different banks of one session do not queue
    behind each other. It still conflicts with the exclusive locks (archive `FOR UPDATE`,
    exam submit/start `FOR NO KEY UPDATE`), so those wait for in-flight writes and block new
    ones. Must be called inside `transaction.atomic()`. Raises `Session.DoesNotExist`.
    """
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT 1 FROM {Session._meta.db_table} WHERE id = %s FOR SHARE",  # noqa: S608
            [session_id],
        )
        if cur.fetchone() is None:
            raise Session.DoesNotExist
    qs = Session.objects.select_related(*select_related) if select_related else Session.objects
    return qs.get(pk=session_id)
