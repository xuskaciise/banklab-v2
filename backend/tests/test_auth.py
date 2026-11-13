import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts import services
from apps.accounts.models import Institution, PlatformRole, User
from apps.audit.models import AuditLog

PHONE = "+252 61 555 1234"  # initial password for everyone: 1234
STAFF = PlatformRole.INSTRUCTOR


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def make(username, role=STAFF, phone=PHONE, **kw):
    return services.create_user(username, f"Name {username}", phone, role, **kw)


def make_student(username="stu1", phone=PHONE, **kw):
    return make(username, PlatformRole.STUDENT, phone, **kw)


def csrf_client():
    client = Client(enforce_csrf_checks=True)
    client.get("/api/auth/csrf")
    return client, client.cookies["csrftoken"].value


def post(client, token, url, data=None):
    return client.post(
        url, data=data or {}, content_type="application/json", HTTP_X_CSRFTOKEN=token
    )


def login(username, password):
    """Staff login."""
    client, token = csrf_client()
    resp = post(
        client, token, "/api/auth/staff-login", {"username": username, "password": password}
    )
    return client, client.cookies["csrftoken"].value, resp


def student_login(student_id, password="1234"):
    client, token = csrf_client()
    resp = post(
        client, token, "/api/auth/student-login", {"student_id": student_id, "password": password}
    )
    return client, client.cookies["csrftoken"].value, resp


def student_post(client, token, student_id, password):
    return post(
        client, token, "/api/auth/student-login", {"student_id": student_id, "password": password}
    )


def staff_post(client, token, username, password):
    return post(
        client, token, "/api/auth/staff-login", {"username": username, "password": password}
    )


@pytest.mark.django_db
class TestStaffLogin:
    def test_default_institution_exists(self):
        assert Institution.objects.filter(name="SIU").exists()

    def test_first_login_must_change_password(self):
        user = make("i1")
        assert user.must_change_password is True
        assert user.check_password("1234")
        _, _, resp = login("i1", "1234")
        assert resp.status_code == 200
        body = resp.json()["user"]
        assert body["username"] == "i1" and body["must_change_password"] is True

    def test_wrong_password(self):
        make("i1")
        _, _, resp = login("i1", "nope")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_unknown_user_same_message(self):
        _, _, resp = login("ghost", "x")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_inactive_rejected(self):
        user = make("i1")
        user.is_active = False
        user.save()
        assert login("i1", "1234")[2].status_code == 401

    def test_student_rejected_generic_401(self):
        stu = make_student("stu1")
        stu.set_password("1234")  # even with a usable password a student cannot use this door
        stu.save()
        _, _, resp = login("stu1", "1234")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"
        assert resp.json() == login("ghost", "1234")[2].json()

    def test_old_login_endpoint_removed(self):
        client, token = csrf_client()
        r = post(client, token, "/api/auth/login", {"username": "a", "password": "b"})
        assert r.status_code == 404

    def test_throttle(self):
        make("i1")
        client, token = csrf_client()
        for _ in range(5):
            assert staff_post(client, token, "i1", "bad").status_code == 401
        assert staff_post(client, token, "i1", "1234").status_code == 429

    def test_me_anonymous_401(self):
        assert Client().get("/api/auth/me").status_code == 401

    def test_me_and_logout(self):
        make("i1")
        client, token, _ = login("i1", "1234")
        assert client.get("/api/auth/me").json()["username"] == "i1"
        assert post(client, token, "/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401


@pytest.mark.django_db
class TestStudentLogin:
    def test_happy_path(self):
        stu = make_student("stu1")
        assert stu.has_usable_password() and stu.must_change_password is True
        assert stu.check_password("1234")
        client, _, resp = student_login("stu1", "1234")
        assert resp.status_code == 200
        body = resp.json()["user"]
        assert body["username"] == "stu1" and body["must_change_password"] is True
        assert body["platform_role"] == "student"
        assert client.get("/api/auth/me").status_code == 200

    @pytest.mark.parametrize("typed", ["", "   ", "0615551234", "061 555 1234", "0000", "12345"])
    def test_wrong_password(self, typed):
        make_student("stu1")
        _, _, resp = student_login("stu1", typed)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_unknown_student_same_message(self):
        _, _, resp = student_login("ghost", "1234")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_inactive_rejected(self):
        stu = make_student("stu1")
        stu.is_active = False
        stu.save()
        assert student_login("stu1", "1234")[2].status_code == 401

    @pytest.mark.parametrize("role", [PlatformRole.INSTRUCTOR, PlatformRole.ADMIN])
    def test_staff_rejected_generic_401(self, role):
        make("boss", role)
        _, _, resp = student_login("boss", "1234")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_throttle_per_id(self):
        make_student("stu1")
        client, token = csrf_client()
        for _ in range(5):
            assert student_post(client, token, "stu1", "1").status_code == 401
        assert student_post(client, token, "stu1", "1234").status_code == 429

    def test_throttle_per_ip(self, monkeypatch):
        monkeypatch.setattr("apps.accounts.api.MAX_ATTEMPTS_PER_IP", 30)
        client, token = csrf_client()
        for i in range(30):
            assert student_post(client, token, f"u{i}", "1").status_code == 401
        assert student_post(client, token, "u99", "1").status_code == 429

    def test_ip_budget_shared_across_endpoints(self, monkeypatch):
        monkeypatch.setattr("apps.accounts.api.MAX_ATTEMPTS_PER_IP", 30)
        client, token = csrf_client()
        for i in range(15):
            assert student_post(client, token, f"s{i}", "1").status_code == 401
            assert staff_post(client, token, f"u{i}", "x").status_code == 401
        assert student_post(client, token, "s99", "1").status_code == 429
        assert staff_post(client, token, "u99", "x").status_code == 429

    @pytest.mark.parametrize("kind", ["student", "staff"])
    def test_per_id_cap_across_ips(self, kind):
        make_student("stu1")
        client, token = csrf_client()
        url = f"/api/auth/{kind}-login"
        body = (
            {"student_id": "stu1", "password": "1"}
            if kind == "student"
            else {"username": "stu1", "password": "x"}
        )
        for i in range(20):
            r = client.post(
                url,
                data=body,
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
                REMOTE_ADDR=f"10.0.0.{i + 1}",
            )
            assert r.status_code == 401
        r = client.post(
            url,
            data=body,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
            REMOTE_ADDR="10.0.1.1",
        )
        assert r.status_code == 429

    def test_success_resets_id_counter(self):
        make_student("stu1")
        client, token = csrf_client()
        for _ in range(4):
            student_post(client, token, "stu1", "1")
        assert student_post(client, token, "stu1", "1234").status_code == 200

    def test_without_csrf_token_rejected(self):
        make_student("stu1")
        client = Client(enforce_csrf_checks=True)
        resp = client.post(
            "/api/auth/student-login",
            data={"student_id": "stu1", "password": "1234"},
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_student_logout(self):
        make_student("stu1")
        client, token, _ = student_login("stu1", "1234")
        assert post(client, token, "/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401


@pytest.mark.django_db
class TestLoginAudit:
    def test_student_success_and_failure_rows(self):
        stu = make_student("stu1")
        student_login("stu1", "999999999")
        student_login("stu1", "1234")
        failed = AuditLog.objects.get(action="auth.login_failed")
        assert (failed.entity_type, failed.entity_id) == ("user", str(stu.pk))
        assert failed.after == {"method": "student"}
        ok = AuditLog.objects.get(action="auth.login")
        assert ok.actor_id == stu.pk and ok.after == {"method": "student"}
        for row in AuditLog.objects.all():
            assert "999999999" not in str(row.__dict__) and "5551234" not in str(row.__dict__)

    def test_unknown_student_marker_only(self):
        student_login("typed-id-xyz", "0611111111")
        row = AuditLog.objects.get(action="auth.login_failed")
        assert (row.entity_type, row.entity_id) == ("unknown_username", "")
        assert "typed-id-xyz" not in str(row.__dict__) and "611111111" not in str(row.__dict__)

    def test_staff_method_recorded(self):
        user = make("i1")
        login("i1", "bad-secret")
        login("i1", "1234")
        assert AuditLog.objects.get(action="auth.login_failed").after == {"method": "staff"}
        assert AuditLog.objects.get(action="auth.login").actor_id == user.pk
        assert "bad-secret" not in str([r.__dict__ for r in AuditLog.objects.all()])


@pytest.mark.django_db
class TestCsrf:
    def test_staff_login_without_token_rejected(self):
        make("i1")
        client = Client(enforce_csrf_checks=True)
        resp = client.post(
            "/api/auth/staff-login",
            data={"username": "i1", "password": "1234"},
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_logout_without_token_rejected(self):
        make("i1")
        client, token, _ = login("i1", "1234")
        resp = client.post("/api/auth/logout", content_type="application/json")
        assert resp.status_code == 403
        assert client.get("/api/auth/me").status_code == 200


@pytest.mark.django_db
class TestChangePassword:
    def change(self, client, token, cur, new):
        return post(
            client,
            token,
            "/api/auth/change-password",
            {"current_password": cur, "new_password": new},
        )

    def test_ok_clears_flag(self):
        make("i1")
        client, token, _ = login("i1", "1234")
        resp = self.change(client, token, "1234", "secret99")
        assert resp.status_code == 200
        assert resp.json()["must_change_password"] is False
        assert client.get("/api/auth/me").status_code == 200
        assert login("i1", "secret99")[2].status_code == 200

    @pytest.mark.parametrize(
        "cur,new",
        [("wrong", "secret99"), ("1234", "abc"), ("1234", "1234"), ("secret99", "secret99")],
    )
    def test_policy_rejections(self, cur, new):
        user = make("i1")
        if cur == "secret99":
            user.set_password("secret99")
            user.save()
        client, token, resp = login("i1", cur if cur == "secret99" else "1234")
        assert resp.status_code == 200
        assert self.change(client, token, cur, new).status_code == 400

    def test_not_initial_password(self):
        user = make("i1")
        user.set_password("secret99")
        user.save()
        client, token, _ = login("i1", "secret99")
        assert self.change(client, token, "secret99", "1234").status_code == 400

    def test_anonymous_401(self):
        client, token = csrf_client()
        assert self.change(client, token, "a", "bbbbbbb").status_code == 401

    def test_student_changes_password(self):
        stu = make_student("stu1")
        client, token, _ = student_login("stu1", "1234")
        assert self.change(client, token, "1234", "newsecret1").status_code == 200
        stu.refresh_from_db()
        assert stu.check_password("newsecret1") and stu.must_change_password is False
        assert student_login("stu1", "newsecret1")[2].status_code == 200
        assert student_login("stu1", "1234")[2].status_code == 401

    def test_student_policy_rejections(self):
        make_student("stu1")
        client, token, _ = student_login("stu1", "1234")
        assert self.change(client, token, "wrong", "newsecret1").status_code == 400
        assert self.change(client, token, "1234", "1234").status_code == 400
        assert self.change(client, token, "1234", "abc").status_code == 400


@pytest.mark.django_db
class TestResetPassword:
    def reset(self, actor, target):
        actor.must_change_password = False
        actor.save()
        if actor.platform_role == PlatformRole.STUDENT:
            client, token, resp = student_login(actor.username, "1234")
        else:
            client, token, resp = login(actor.username, "1234")
        assert resp.status_code == 200
        return post(client, token, f"/api/auth/users/{target.id}/reset-password")

    def dirty(self, user):
        user.set_password("changed99")
        user.must_change_password = False
        user.save()

    def test_admin_resets_instructor(self):
        admin = make("a1", PlatformRole.ADMIN)
        inst = make("i1", PlatformRole.INSTRUCTOR)
        self.dirty(inst)
        assert self.reset(admin, inst).status_code == 204
        inst.refresh_from_db()
        assert inst.check_password("1234") and inst.must_change_password
        row = AuditLog.objects.get(action="auth.password_reset")
        assert row.actor_id == admin.pk and row.entity_id == str(inst.pk)

    def test_admin_resets_student(self):
        admin = make("a1", PlatformRole.ADMIN)
        stu = make_student("s1")
        self.dirty(stu)
        assert self.reset(admin, stu).status_code == 204
        stu.refresh_from_db()
        assert stu.check_password("1234") and stu.must_change_password
        assert student_login("s1", "1234")[2].status_code == 200

    def test_instructor_resets_student(self):
        inst = make("i1", PlatformRole.INSTRUCTOR)
        stu = make_student("s1")
        from apps.lab.models import Class, Enrollment

        cls = Class.objects.create(
            institution_id=inst.institution_id, instructor=inst, name="C", code="C1"
        )
        Enrollment.objects.create(lab_class=cls, user=stu)
        self.dirty(stu)
        assert self.reset(inst, stu).status_code == 204
        stu.refresh_from_db()
        assert stu.check_password("1234") and stu.must_change_password
        row = AuditLog.objects.get(action="auth.password_reset")
        assert row.actor_id == inst.pk and row.entity_id == str(stu.pk)

    def test_instructor_cannot_reset_student_outside_own_classes(self):
        inst = make("i1", PlatformRole.INSTRUCTOR)
        other = make("i2", PlatformRole.INSTRUCTOR)
        stu = make_student("s1")
        from apps.lab.models import Class, Enrollment

        cls = Class.objects.create(
            institution_id=other.institution_id, instructor=other, name="C", code="C2"
        )
        Enrollment.objects.create(lab_class=cls, user=stu)
        assert self.reset(inst, stu).status_code == 403
        assert self.reset(other, stu).status_code == 204

    def test_instructor_cannot_reset_staff(self):
        inst = make("i1", PlatformRole.INSTRUCTOR)
        other = make("i2", PlatformRole.INSTRUCTOR)
        admin = make("a1", PlatformRole.ADMIN)
        self.dirty(other)
        self.dirty(admin)
        assert self.reset(inst, other).status_code == 403
        assert self.reset(inst, admin).status_code == 403
        other.refresh_from_db()
        assert other.check_password("changed99")

    def test_student_forbidden(self):
        stu = make_student("s1")
        other = make_student("s2")
        assert self.reset(stu, other).status_code == 403
        other.refresh_from_db()
        assert other.check_password("1234") and other.must_change_password

    def test_cross_institution_hidden(self):
        admin = make("a1", PlatformRole.ADMIN)
        inst = Institution.objects.create(name="Other")
        for role in (PlatformRole.INSTRUCTOR, PlatformRole.STUDENT):
            target = make(f"x-{role}", role, institution=inst)
            assert self.reset(admin, target).status_code == 404


@pytest.mark.django_db
class TestPhoneNormalisation:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("+252 61 234 5678", "612345678"),
            ("00252612345678", "612345678"),
            ("0612345678", "612345678"),
            ("612345678", "612345678"),
            ("061-234-5678", "612345678"),
            ("(061) 234 5678", "612345678"),
            ("252612345678", "612345678"),
            ("252123456", "252123456"),  # 9 digits: 252 is not a country code here
            ("", ""),
            ("   ", ""),
            ("0000", ""),
            (None, ""),
        ],
    )
    def test_normalize(self, raw, expected):
        assert services.normalize_phone(raw) == expected


@pytest.mark.django_db
class TestServices:
    def test_initial_password(self):
        assert services.initial_password("061-555-9876") == "9876"
        with pytest.raises(services.ValidationFailed):
            services.initial_password("12-3")

    def test_student_created_with_initial_password(self):
        stu = make_student("s1")
        assert stu.check_password("1234") and stu.must_change_password is True

    def test_student_requires_phone(self):
        with pytest.raises(services.ValidationFailed):
            make_student("s2", phone="")

    def test_staff_keeps_initial_password_flow(self):
        inst = make("i1")
        assert inst.check_password("1234") and inst.must_change_password is True

    def test_superuser_defaults(self):
        su = User.objects.create_superuser("root", "pw123456", full_name="Root")
        assert su.platform_role == PlatformRole.ADMIN
        assert su.is_staff and not su.must_change_password


@pytest.mark.django_db
class TestForcedPasswordChange:
    def test_flagged_staff_blocked_from_protected_routes(self):
        make("a1", PlatformRole.ADMIN)  # flagged by create_user
        stu = make_student("s1")
        client, token, resp = login("a1", "1234")
        assert resp.status_code == 200
        r = post(client, token, f"/api/auth/users/{stu.id}/reset-password")
        assert r.status_code == 403
        assert r.json()["detail"] == "Password change required"
        assert client.get("/api/auth/me").status_code == 200  # allowed

    def test_unflagged_staff_allowed(self):
        admin = make("a1", PlatformRole.ADMIN)
        admin.must_change_password = False
        admin.save()
        inst = make("i1")
        client, token, _ = login("a1", "1234")
        assert post(client, token, f"/api/auth/users/{inst.id}/reset-password").status_code == 204

    def test_flagged_student_blocked_like_staff(self):
        stu = make_student("s1")  # flagged by create_user
        client, token, resp = student_login("s1", "1234")
        assert resp.status_code == 200
        r = post(client, token, f"/api/auth/users/{stu.id}/reset-password")
        assert r.status_code == 403
        assert r.json()["detail"] == "Password change required"
        assert client.get("/api/audit").json()["detail"] == "Password change required"
        assert client.get("/api/auth/me").status_code == 200  # allowed
        change = post(
            client,
            token,
            "/api/auth/change-password",
            {"current_password": "1234", "new_password": "newsecret1"},
        )
        assert change.status_code == 200
        r = post(client, token, f"/api/auth/users/{stu.id}/reset-password")
        assert r.json()["detail"] != "Password change required"

    def test_health_stays_public(self):
        assert Client().get("/api/health").status_code == 200


@pytest.mark.django_db
class TestIpThrottle:
    def test_spraying_usernames_hits_429_at_31(self, monkeypatch):
        monkeypatch.setattr("apps.accounts.api.MAX_ATTEMPTS_PER_IP", 30)
        client, token = csrf_client()
        for i in range(30):
            assert staff_post(client, token, f"u{i}", "x").status_code == 401
        assert staff_post(client, token, "u99", "x").status_code == 429

    def test_success_resets_user_counter(self):
        make("i1")
        client, token = csrf_client()
        for _ in range(4):
            staff_post(client, token, "i1", "bad")
        assert staff_post(client, token, "i1", "1234").status_code == 200


@pytest.mark.django_db
def test_csrf_endpoint_returns_token():
    client = Client()
    resp = client.get("/api/auth/csrf")
    assert list(resp.json()) == ["csrf_token"]
    assert resp.json()["csrf_token"]
    assert "csrftoken" in client.cookies


@pytest.mark.django_db
class TestAdminStudents:
    def _admin_client(self):
        User.objects.create_superuser("root", "pw123456", full_name="Root")
        c = Client()
        c.login(username="root", password="pw123456")
        return c

    def _add(self, c, username, role, phone="0615551234", pw=""):
        return c.post(
            "/admin/accounts/user/add/",
            {
                "username": username,
                "institution": Institution.objects.first().pk,
                "full_name": "X",
                "phone": phone,
                "platform_role": role,
                "password1": pw,
                "password2": pw,
            },
        )

    def test_add_student_without_password_gets_initial(self):
        resp = self._add(self._admin_client(), "adm-stu", "student")
        assert resp.status_code == 302
        u = User.objects.get(username="adm-stu")
        assert u.check_password("1234") and u.must_change_password is True
        assert student_login("adm-stu", "1234")[2].status_code == 200

    def test_add_student_ignores_given_password(self):
        self._add(self._admin_client(), "adm-stu2", "student", pw="Sup3rSecret!x")
        u = User.objects.get(username="adm-stu2")
        assert u.check_password("1234") and not u.check_password("Sup3rSecret!x")
        assert u.must_change_password is True

    def test_add_student_needs_phone_with_4_digits(self):
        resp = self._add(self._admin_client(), "adm-stu3", "student", phone="12")
        assert resp.status_code == 200
        assert not User.objects.filter(username="adm-stu3").exists()

    def test_staff_requires_password(self):
        resp = self._add(self._admin_client(), "adm-i", "instructor")
        assert resp.status_code == 200
        assert not User.objects.filter(username="adm-i").exists()

    def test_role_change_to_student_sets_initial_password(self):
        from django.contrib import admin as dj_admin

        from apps.accounts.admin import UserAdmin

        user = make("i1")
        user.set_password("changed99")
        user.must_change_password = False
        user.platform_role = PlatformRole.STUDENT
        form = type("F", (), {"changed_data": ["platform_role"]})()
        UserAdmin(User, dj_admin.site).save_model(None, user, form, True)
        user.refresh_from_db()
        assert user.check_password("1234") and user.must_change_password is True

    def test_unrelated_edit_of_student_keeps_password(self):
        from django.contrib import admin as dj_admin

        from apps.accounts.admin import UserAdmin

        stu = make_student("s1")
        stu.set_password("changed99")
        stu.must_change_password = False
        form = type("F", (), {"changed_data": ["full_name"]})()
        UserAdmin(User, dj_admin.site).save_model(None, stu, form, True)
        stu.refresh_from_db()
        assert stu.check_password("changed99") and stu.must_change_password is False


@pytest.mark.django_db
class TestThrottleReset:
    def test_success_resets_per_id_counter(self):
        make_student("stu1")
        client, token = csrf_client()
        for i in range(15):
            client.post(
                "/api/auth/student-login",
                data={"student_id": "stu1", "password": "1"},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
                REMOTE_ADDR=f"10.1.0.{i + 1}",
            )
        assert student_post(client, token, "stu1", "1234").status_code == 200
        token = client.cookies["csrftoken"].value  # login rotates the CSRF token
        for i in range(15):
            r = client.post(
                "/api/auth/student-login",
                data={"student_id": "stu1", "password": "1"},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
                REMOTE_ADDR=f"10.2.0.{i + 1}",
            )
            assert r.status_code == 401  # would be 429 without the reset (31st > 20)

    def test_class_from_one_ip_not_blocked(self):
        for i in range(40):
            make_student(f"c{i}")
        for i in range(40):
            assert student_login(f"c{i}", "1234")[2].status_code == 200


@pytest.mark.django_db
class TestMigration0004:
    def test_students_without_usable_password_get_initial(self):
        import importlib

        from django.apps import apps as django_apps

        mod = importlib.import_module("apps.accounts.migrations.0004_students_initial_password")
        stu = make_student("s1", phone="061-555-9876")
        User.objects.filter(pk=stu.pk).update(password="!", must_change_password=False)
        keep = make_student("s2")
        keep.set_password("mine-1234")
        keep.must_change_password = False
        keep.save()
        mod.give_students_initial_password(django_apps, None)
        stu.refresh_from_db()
        keep.refresh_from_db()
        assert stu.check_password("9876") and stu.must_change_password is True
        assert keep.check_password("mine-1234") and keep.must_change_password is False
