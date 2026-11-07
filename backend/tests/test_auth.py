import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts import services
from apps.accounts.models import Institution, PlatformRole, User

PHONE = "+252 61 555 1234"  # initial password 1234


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()


def make(username, role=PlatformRole.STUDENT, phone=PHONE, **kw):
    return services.create_user(username, f"Name {username}", phone, role, **kw)


def csrf_client():
    client = Client(enforce_csrf_checks=True)
    client.get("/api/auth/csrf")
    return client, client.cookies["csrftoken"].value


def post(client, token, url, data=None):
    return client.post(
        url, data=data or {}, content_type="application/json", HTTP_X_CSRFTOKEN=token
    )


def login(username, password):
    client, token = csrf_client()
    resp = post(client, token, "/api/auth/login", {"username": username, "password": password})
    return client, client.cookies["csrftoken"].value, resp


@pytest.mark.django_db
class TestLogin:
    def test_default_institution_exists(self):
        assert Institution.objects.filter(name="SIU").exists()

    def test_first_login_user_must_change_password(self):
        user = make("s1")
        assert user.must_change_password is True
        assert user.check_password("1234")
        assert user.institution.name == "SIU"
        _, _, resp = login("s1", "1234")
        assert resp.status_code == 200
        body = resp.json()["user"]
        assert body["username"] == "s1" and body["must_change_password"] is True

    def test_wrong_password(self):
        make("s1")
        _, _, resp = login("s1", "nope")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    def test_unknown_user_same_message(self):
        _, _, resp = login("ghost", "x")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid username or password"

    def test_inactive_rejected(self):
        user = make("s1")
        user.is_active = False
        user.save()
        _, _, resp = login("s1", "1234")
        assert resp.status_code == 401

    def test_throttle(self):
        make("s1")
        client, token = csrf_client()
        for _ in range(5):
            r = post(client, token, "/api/auth/login", {"username": "s1", "password": "bad"})
            assert r.status_code == 401
        r = post(client, token, "/api/auth/login", {"username": "s1", "password": "1234"})
        assert r.status_code == 429

    def test_me_anonymous_401(self):
        assert Client().get("/api/auth/me").status_code == 401

    def test_me_and_logout(self):
        make("s1")
        client, token, _ = login("s1", "1234")
        assert client.get("/api/auth/me").json()["username"] == "s1"
        assert post(client, token, "/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401


@pytest.mark.django_db
class TestCsrf:
    def test_login_without_token_rejected(self):
        make("s1")
        client = Client(enforce_csrf_checks=True)
        resp = client.post(
            "/api/auth/login",
            data={"username": "s1", "password": "1234"},
            content_type="application/json",
        )
        assert resp.status_code == 403

    def test_logout_without_token_rejected(self):
        make("s1")
        client, token, _ = login("s1", "1234")
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
        make("s1")
        client, token, _ = login("s1", "1234")
        resp = self.change(client, token, "1234", "secret99")
        assert resp.status_code == 200
        assert resp.json()["must_change_password"] is False
        # The same session stays logged in after the password change.
        assert client.get("/api/auth/me").status_code == 200
        assert login("s1", "secret99")[2].status_code == 200

    @pytest.mark.parametrize(
        "cur,new",
        [("wrong", "secret99"), ("1234", "abc"), ("1234", "1234"), ("secret99", "secret99")],
    )
    def test_policy_rejections(self, cur, new):
        user = make("s1")
        if cur == "secret99":
            user.set_password("secret99")
            user.save()
        client, token, resp = login("s1", cur if cur == "secret99" else "1234")
        assert resp.status_code == 200
        assert self.change(client, token, cur, new).status_code == 400

    def test_not_initial_password(self):
        user = make("s1")
        user.set_password("secret99")
        user.save()
        client, token, _ = login("s1", "secret99")
        assert self.change(client, token, "secret99", "1234").status_code == 400

    def test_anonymous_401(self):
        client, token = csrf_client()
        assert self.change(client, token, "a", "bbbbbbb").status_code == 401


@pytest.mark.django_db
class TestResetPassword:
    def reset(self, actor, target):
        actor.must_change_password = False
        actor.save()
        client, token, resp = login(actor.username, "1234")
        assert resp.status_code == 200
        return post(client, token, f"/api/auth/users/{target.id}/reset-password")

    def dirty(self, user):
        user.set_password("changed99")
        user.must_change_password = False
        user.save()

    def test_admin_resets_anyone(self):
        admin = make("a1", PlatformRole.ADMIN)
        inst = make("i1", PlatformRole.INSTRUCTOR)
        self.dirty(inst)
        assert self.reset(admin, inst).status_code == 204
        inst.refresh_from_db()
        assert inst.check_password("1234") and inst.must_change_password

    def test_instructor_resets_student(self):
        inst = make("i1", PlatformRole.INSTRUCTOR)
        stu = make("s1")
        self.dirty(stu)
        assert self.reset(inst, stu).status_code == 204
        stu.refresh_from_db()
        assert stu.check_password("1234") and stu.must_change_password

    def test_instructor_cannot_reset_instructor(self):
        inst = make("i1", PlatformRole.INSTRUCTOR)
        other = make("i2", PlatformRole.INSTRUCTOR)
        assert self.reset(inst, other).status_code == 403

    def test_student_forbidden(self):
        stu = make("s1")
        other = make("s2")
        assert self.reset(stu, other).status_code == 403

    def test_cross_institution_hidden(self):
        admin = make("a1", PlatformRole.ADMIN)
        other_inst = Institution.objects.create(name="Other")
        stu = make("s9", institution=other_inst)
        assert self.reset(admin, stu).status_code == 404


@pytest.mark.django_db
class TestServices:
    def test_initial_password(self):
        assert services.initial_password("061-555-9876") == "9876"
        with pytest.raises(services.ValidationFailed):
            services.initial_password("12-3")

    def test_superuser_defaults(self):
        su = User.objects.create_superuser("root", "pw123456", full_name="Root")
        assert su.platform_role == PlatformRole.ADMIN
        assert su.is_staff and not su.must_change_password


@pytest.mark.django_db
class TestForcedPasswordChange:
    def test_flagged_user_blocked_from_protected_routes(self):
        admin = make("a1", PlatformRole.ADMIN)  # flagged by create_user
        stu = make("s1")
        client, token, resp = login("a1", "1234")
        assert resp.status_code == 200
        r = post(client, token, f"/api/auth/users/{stu.id}/reset-password")
        assert r.status_code == 403
        assert r.json()["detail"] == "Password change required"
        assert client.get("/api/auth/me").status_code == 200  # allowed
        admin.refresh_from_db()

    def test_unflagged_user_allowed(self):
        admin = make("a1", PlatformRole.ADMIN)
        admin.must_change_password = False
        admin.save()
        stu = make("s1")
        client, token, _ = login("a1", "1234")
        assert post(client, token, f"/api/auth/users/{stu.id}/reset-password").status_code == 204

    def test_health_stays_public(self):
        assert Client().get("/api/health").status_code == 200


@pytest.mark.django_db
class TestIpThrottle:
    def test_spraying_usernames_hits_429_at_31(self):
        client, token = csrf_client()
        for i in range(30):
            r = post(client, token, "/api/auth/login", {"username": f"u{i}", "password": "x"})
            assert r.status_code == 401
        r = post(client, token, "/api/auth/login", {"username": "u99", "password": "x"})
        assert r.status_code == 429

    def test_success_resets_user_counter(self):
        make("s1")
        client, token = csrf_client()
        for _ in range(4):
            post(client, token, "/api/auth/login", {"username": "s1", "password": "bad"})
        ok = post(client, token, "/api/auth/login", {"username": "s1", "password": "1234"})
        assert ok.status_code == 200


@pytest.mark.django_db
def test_csrf_endpoint_returns_token():
    client = Client()
    resp = client.get("/api/auth/csrf")
    assert list(resp.json()) == ["csrf_token"]
    assert resp.json()["csrf_token"]
    assert "csrftoken" in client.cookies
