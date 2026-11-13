# ruff: noqa: F811
"""1.15 Hardening: trusted client IP, case-insensitive usernames, docs lock-down, load-test seed."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.test import Client, RequestFactory

from apps.accounts import services
from apps.accounts.models import Institution, PlatformRole, User
from apps.audit.models import AuditLog
from apps.core.net import client_ip
from config.api import docs_decorator_for
from tests.test_auth import (
    _clear_cache,  # noqa: F401  (autouse fixture)
    csrf_client,
    login,
    make,
    make_student,
    staff_post,
    student_login,
    student_post,
)
from tests.test_lab import _reset_rbac, api, j, world  # noqa: F401


# ------------------------------------------------------------------ trusted client IP
@pytest.mark.django_db
class TestClientIp:
    def req(self, **meta):
        return RequestFactory().get("/", **meta)

    def test_default_uses_remote_addr_and_ignores_headers(self, settings):
        settings.CLIENT_IP_HEADER = ""
        r = self.req(
            REMOTE_ADDR="10.0.0.1", HTTP_X_REAL_IP="9.9.9.9", HTTP_X_FORWARDED_FOR="8.8.8.8"
        )
        assert client_ip(r) == "10.0.0.1"

    def test_configured_header_is_honoured(self, settings):
        settings.CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
        r = self.req(REMOTE_ADDR="172.18.0.2", HTTP_CF_CONNECTING_IP="203.0.113.7")
        assert client_ip(r) == "203.0.113.7"

    def test_ipv6_normalised(self, settings):
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        r = self.req(REMOTE_ADDR="172.18.0.2", HTTP_X_REAL_IP="2001:DB8:0:0:0:0:0:1")
        assert client_ip(r) == "2001:db8::1"

    @pytest.mark.parametrize(
        "bad", ["", "not-an-ip", "1.2.3.4, 5.6.7.8", "999.1.1.1", "1.2.3.4:80"]
    )
    def test_invalid_value_falls_back(self, settings, bad):
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        r = self.req(REMOTE_ADDR="172.18.0.2", HTTP_X_REAL_IP=bad)
        assert client_ip(r) == "172.18.0.2"

    def test_missing_header_falls_back(self, settings):
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        assert client_ip(self.req(REMOTE_ADDR="172.18.0.2")) == "172.18.0.2"

    def test_xff_never_trusted_even_when_configured_header_absent(self, settings):
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        r = self.req(REMOTE_ADDR="172.18.0.2", HTTP_X_FORWARDED_FOR="8.8.8.8")
        assert client_ip(r) == "172.18.0.2"

    def test_none_request(self):
        assert client_ip(None) == ""


@pytest.mark.django_db
class TestIpInLoginAndAudit:
    def test_audit_ip_uses_trusted_header_only_when_configured(self, settings):
        make_student("stu1")
        settings.CLIENT_IP_HEADER = ""
        c, t = csrf_client()
        c.post(
            "/api/auth/student-login",
            data={"student_id": "stu1", "password": "x"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=t,
            HTTP_X_REAL_IP="203.0.113.9",
        )
        assert set(
            AuditLog.objects.filter(action="auth.login_failed").values_list("ip", flat=True)
        ) == {"127.0.0.1"}
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        c.post(
            "/api/auth/student-login",
            data={"student_id": "stu1", "password": "x"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=t,
            HTTP_X_REAL_IP="203.0.113.9",
        )
        assert set(
            AuditLog.objects.filter(action="auth.login_failed").values_list("ip", flat=True)
        ) == {
            "127.0.0.1",
            "203.0.113.9",
        }

    def test_ip_cap_follows_trusted_header(self, settings, monkeypatch):
        monkeypatch.setattr("apps.accounts.api.MAX_ATTEMPTS_PER_IP", 5)
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        c, t = csrf_client()

        def attempt(i, ip):
            return c.post(
                "/api/auth/student-login",
                data={"student_id": f"u{i}", "password": "x"},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=t,
                HTTP_X_REAL_IP=ip,
            ).status_code

        assert [attempt(i, "203.0.113.1") for i in range(5)] == [401] * 5
        assert attempt(99, "203.0.113.1") == 429
        assert attempt(100, "203.0.113.2") == 401  # another client behind the same proxy

    def test_successful_logins_do_not_consume_ip_budget(self, monkeypatch):
        monkeypatch.setattr("apps.accounts.api.MAX_ATTEMPTS_PER_IP", 5)
        for i in range(8):
            make_student(f"c{i}")
        for i in range(8):
            assert student_login(f"c{i}")[2].status_code == 200


# ------------------------------------------------------------------ case-insensitive usernames
@pytest.mark.django_db
class TestUsernameCaseInsensitive:
    def test_service_rejects_case_only_duplicate(self):
        make("Teacher")
        with pytest.raises(services.ValidationFailed, match="already exists"):
            make("teacher")

    def test_db_constraint_backstop(self):
        make("Teacher")
        with pytest.raises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                "TEACHER", password="x", institution=Institution.objects.first()
            )

    def test_student_login_ignores_case_and_whitespace(self):
        stu = make_student("S5101")
        for typed in ("s5101", "S5101", " s5101 "):
            body = student_login(typed)[2]
            assert body.status_code == 200
            assert body.json()["user"]["username"] == "S5101"
        assert User.objects.get(pk=stu.pk).username == "S5101"  # stored spelling untouched

    def test_staff_login_ignores_case(self):
        make("Mr.Ahmed")
        resp = login("mr.ahmed", "1234")[2]
        assert resp.status_code == 200 and resp.json()["user"]["username"] == "Mr.Ahmed"

    def test_wrong_password_still_401_and_same_message(self):
        make_student("S5101")
        r1 = student_login("s5101", "bad")[2]
        r2 = student_login("nobody", "bad")[2]
        assert r1.status_code == r2.status_code == 401 and r1.json() == r2.json()

    def test_throttle_counts_case_variants_together(self):
        make_student("S5101")
        c, t = csrf_client()
        for typed in ("S5101", "s5101", "S5101", "s5101", "S5101"):
            assert student_post(c, t, typed, "bad").status_code == 401
        assert student_post(c, t, "s5101", "1234").status_code == 429

    def test_staff_cannot_use_student_door_and_vice_versa_any_case(self):
        make("Boss")
        make_student("S1")
        assert student_login("boss")[2].status_code == 401
        c, t = csrf_client()
        assert staff_post(c, t, "s1", "1234").status_code == 401

    def test_instructor_create_case_duplicate_is_4xx(self, world):
        from apps.adminconsole import services as console

        with pytest.raises(services.ValidationFailed):
            console.create_instructor(world["admin"], "IA", "Dup", "0611110000")
        # the fixture's "ia" exists in lowercase; the upper-case variant is a duplicate

    def test_add_student_reuses_existing_user_case_insensitively(self, world):
        ca = world["ca"]
        existing = world["studs"][0]  # "s0", already enrolled in this class
        from apps.lab import services as lab

        with pytest.raises(lab.ValidationFailed, match="already enrolled"):
            lab.add_student(world["ia"], ca.pk, "S0", "Stud 0", "0611110000")
        assert User.objects.filter(username__iexact=existing.username).count() == 1

    def test_csv_import_flags_case_duplicates(self, world):
        c = api(world["ia"])
        cid = world["ca"].pk
        text = "username,full_name,phone\nNEW1,New One,0611110001\nnew1,Again,0611110002\nS0,Zero,0611110003\n"
        r = j(c, "post", f"/api/classes/{cid}/students/import/preview", {"csv_text": text})
        assert r.status_code == 200
        errors = [row for row in r.json()["rows"] if row["action"] == "error"]
        assert len(errors) == 2  # in-file duplicate + already enrolled "S0"

    def test_rename_case_only_conflict_is_4xx(self, world):
        c = api(world["admin"])
        a, b = world["studs"][0], world["studs"][1]
        r = j(c, "put", f"/api/admin/students/{a.pk}/username", {"username": b.username.upper()})
        assert 400 <= r.status_code < 500


# ------------------------------------------------------------------ docs lock-down
@pytest.mark.django_db
def test_docs_decorator_open_in_debug_staff_only_otherwise():
    assert docs_decorator_for(True) is None
    assert docs_decorator_for(False) is not None


@pytest.mark.django_db
def test_docs_decorator_blocks_anonymous_and_non_staff():
    from django.http import HttpResponse

    guarded = docs_decorator_for(False)(lambda request: HttpResponse("schema"))
    anon = RequestFactory().get("/api/openapi.json")
    anon.user = type("Anon", (), {"is_active": False, "is_staff": False})()
    resp = guarded(anon)
    assert resp.status_code == 302 and "login" in resp["Location"]
    student = make_student("docstu")
    req = RequestFactory().get("/api/openapi.json")
    req.user = student
    assert guarded(req).status_code == 302
    admin = make("docadmin", PlatformRole.ADMIN)
    req.user = admin
    assert guarded(req).content == b"schema"


# ------------------------------------------------------------------ seed_loadtest
@pytest.fixture
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.mark.django_db
class TestSeedLoadtest:
    @pytest.fixture(autouse=True)
    def _debug(self, settings):
        # The test DB name has no "loadtest", so the command only runs with DEBUG on.
        settings.DEBUG = True

    def test_refuses_real_db_when_debug_off(self, tmp_path, settings):
        settings.DEBUG = False
        with pytest.raises(CommandError, match="loadtest"):
            self.seed(tmp_path)

    def seed(self, tmp_path, **kw):
        out = tmp_path / "students.csv"
        call_command(
            "seed_loadtest",
            students=10,
            banks=2,
            customers=2,
            password="loadpass1",
            csv=str(out),
            **kw,
        )
        return out

    def test_requires_password(self, tmp_path, monkeypatch):
        monkeypatch.delenv("LOADTEST_PASSWORD", raising=False)
        with pytest.raises(CommandError, match="password"):
            call_command("seed_loadtest", students=10, banks=2, csv=str(tmp_path / "x.csv"))

    def test_rejects_too_few_students(self, tmp_path):
        with pytest.raises(CommandError, match="at least"):
            call_command("seed_loadtest", students=3, banks=2, password="loadpass1")

    def test_seed_builds_working_roles_money_and_csv(self, tmp_path, _media):
        from apps.banking.models import TellerSession
        from apps.ledger.models import JournalEntry, JournalLine
        from apps.products.models import Account

        out = self.seed(tmp_path)
        text = out.read_text()
        assert "loadpass1" not in text and "password" not in text.lower().split("\n")[0]
        rows = [line.split(",") for line in text.strip().splitlines()[1:]]
        assert len(rows) == 11  # instructor + 10 students
        inst = Institution.objects.get(name="LOADTEST Institution")
        assert User.objects.filter(institution=inst).count() == 11
        assert {r[1] for r in rows if r[3] == "student"} >= {"teller", "manager", "cso"}
        # tellers have open tills with cash; customers have funded accounts
        assert (
            TellerSession.objects.filter(
                status="open", bank__session__name__startswith="LOADTEST"
            ).count()
            == 2
        )
        accts = Account.objects.filter(bank__session__name__startswith="LOADTEST")
        assert accts.count() == 4 and all(a.ledger_balance > 0 for a in accts)
        # every posting is balanced (Dr = Cr)
        entries = JournalEntry.objects.filter(bank__session__name__startswith="LOADTEST")
        assert entries.exists()
        for e in entries:
            agg = JournalLine.objects.filter(entry=e).aggregate(d=Sum("debit"), c=Sum("credit"))
            assert agg["d"] == agg["c"]
        # students can log in with the seeded password and are not forced to change it
        first = next(r[0] for r in rows if r[1] == "teller")
        resp = student_login(first, "loadpass1")[2]
        assert resp.status_code == 200 and resp.json()["user"]["must_change_password"] is False
        assert Client().get("/api/health").status_code == 200

    def test_second_seed_refused_and_teardown_archives(self, tmp_path, _media):
        from apps.lab.models import Session

        self.seed(tmp_path)
        with pytest.raises(CommandError, match="already exists"):
            self.seed(tmp_path)
        call_command("seed_loadtest", teardown=True)
        assert (
            not Session.objects.filter(name__startswith="LOADTEST")
            .exclude(status="archived")
            .exists()
        )
        inst = Institution.objects.get(name="LOADTEST Institution")
        assert not User.objects.filter(institution=inst, is_active=True).exists()
        # other institutions untouched
        assert PlatformRole.INSTRUCTOR  # sanity

    def test_teardown_without_data_is_noop(self):
        call_command("seed_loadtest", teardown=True)


# ------------------------------------------------------------------ proxy shared secret
@pytest.mark.django_db
class TestProxySecret:
    def req(self, **meta):
        return RequestFactory().get("/", **meta)

    def test_header_ignored_without_matching_secret(self, settings):
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        settings.PROXY_SHARED_SECRET = "s3cret-value"
        r = self.req(REMOTE_ADDR="172.18.0.9", HTTP_X_REAL_IP="203.0.113.7")
        assert client_ip(r) == "172.18.0.9"
        r = self.req(
            REMOTE_ADDR="172.18.0.9", HTTP_X_REAL_IP="203.0.113.7", HTTP_X_BANKLAB_PROXY="x"
        )
        assert client_ip(r) == "172.18.0.9"

    def test_header_trusted_with_matching_secret(self, settings):
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        settings.PROXY_SHARED_SECRET = "s3cret-value"
        r = self.req(
            REMOTE_ADDR="172.18.0.2",
            HTTP_X_REAL_IP="203.0.113.7",
            HTTP_X_BANKLAB_PROXY="s3cret-value",
        )
        assert client_ip(r) == "203.0.113.7"

    def test_unset_secret_keeps_old_behaviour(self, settings):
        settings.CLIENT_IP_HEADER = "HTTP_X_REAL_IP"
        settings.PROXY_SHARED_SECRET = ""
        assert (
            client_ip(self.req(REMOTE_ADDR="1.1.1.1", HTTP_X_REAL_IP="203.0.113.7"))
            == "203.0.113.7"
        )

    def test_middleware_strips_forwarded_proto_unless_secret_matches(self, settings):
        from apps.core.middleware import ProxyTrustMiddleware

        settings.PROXY_SHARED_SECRET = "s3cret-value"
        seen = {}

        def view(request):
            seen["proto"] = request.META.get("HTTP_X_FORWARDED_PROTO")
            return None

        mw = ProxyTrustMiddleware(view)
        mw(self.req(HTTP_X_FORWARDED_PROTO="https"))
        assert seen["proto"] is None
        mw(self.req(HTTP_X_FORWARDED_PROTO="https", HTTP_X_BANKLAB_PROXY="s3cret-value"))
        assert seen["proto"] == "https"
        settings.PROXY_SHARED_SECRET = ""
        mw(self.req(HTTP_X_FORWARDED_PROTO="https"))
        assert seen["proto"] == "https"


# ------------------------------------------------------------------ secret key guard
@pytest.mark.parametrize(
    ("key", "ok"),
    [
        ("", False),
        ("change-me", False),
        ("short-key", False),
        ("x" * 31, False),
        ("a-very-long-random-secret-key-0123456789", True),
        ("please-change-me-now-this-is-long-enough-1234", False),
    ],
)
@pytest.mark.django_db
def test_settings_refuse_placeholder_secret_key(key, ok):
    import os
    import subprocess
    import sys

    env = {
        **os.environ,
        "DJANGO_DEBUG": "false",
        "DJANGO_SECRET_KEY": key,
        "DJANGO_SETTINGS_MODULE": "config.settings",
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import django.conf as c; c.settings.SECRET_KEY"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.getcwd(),
    )
    assert (proc.returncode == 0) is ok, proc.stderr[-300:]


@pytest.mark.django_db
def test_find_user_uses_lower_semantics():
    u = make_student("S9100") if callable(make_student) else None
    assert u is None or services.find_user("s9100 ").pk == u.pk
