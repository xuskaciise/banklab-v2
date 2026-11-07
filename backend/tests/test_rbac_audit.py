import uuid
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.db import DatabaseError, connection, transaction
from django.test import Client
from ninja.errors import HttpError

from apps.accounts import services as acc
from apps.accounts.models import Institution, PlatformRole
from apps.audit import services as audit
from apps.audit.models import AuditLog, ImmutableError
from apps.rbac import context, services
from apps.rbac.models import Permission, RolePermission

from .test_auth import login, make, post

T, C, M, V, A = "teller", "cso", "manager", "vault_custodian", "accountant"
ROLES = [T, C, M, V, A]
# code -> {role: scope}; absent role = not granted (docs/design/permissions.md section 4)
EXPECTED = {
    "customer.view": {T: "all", C: "all", M: "all", A: "all"},
    "customer.create": {C: "all", M: "all"},
    "customer.update": {C: "all", M: "all"},
    "account.view": {T: "all", C: "all", M: "all", A: "all"},
    "account.open": {C: "all", M: "all"},
    "account.close": {C: "all", M: "all"},
    "account.statement": {T: "all", C: "all", M: "all", A: "all"},
    "chequebook.issue": {C: "all", M: "all"},
    "cheque.stop": {C: "all", M: "all"},
    "till.open.request": {T: "all"},
    "till.close": {T: "all"},
    "till.open.approve": {M: "all"},
    "till.close.approve": {M: "all"},
    "cash.vault_to_teller.request": {T: "all", M: "all"},
    "cash.teller_to_vault.request": {T: "all"},
    "cash.teller_to_teller.request": {T: "all"},
    "cash.vault.approve_custodian": {V: "all"},
    "cash.vault.approve_manager": {M: "all"},
    "txn.cash_deposit": {T: "all"},
    "txn.cash_withdrawal": {T: "all"},
    "txn.cheque_withdrawal": {T: "all"},
    "txn.transfer": {T: "all", C: "all"},
    "txn.reverse": {T: "all", C: "all"},
    "approval.decide": {M: "all"},
    "vault.view": {M: "all", V: "all", A: "all"},
    "gl.view": {M: "all", A: "all"},
    "report.financial": {M: "all", A: "all"},
    "report.operational": {T: "own", C: "own", M: "all", A: "all"},
    "eod.run": {M: "all"},
    "audit.view": {M: "all"},
}


@pytest.fixture(autouse=True)
def _reset():
    cache.clear()
    services.clear_cache()
    yield
    services.clear_cache()


@pytest.mark.django_db
class TestMatrix:
    def test_seed_counts(self):
        assert Permission.objects.count() == 30
        assert RolePermission.objects.count() == 55

    def test_full_matrix_cell_by_cell(self):
        for role in ROLES:
            for code, cells in EXPECTED.items():
                assert services.permission_scope(role, code) == cells.get(role), (role, code)
        assert set(Permission.objects.values_list("code", flat=True)) == set(EXPECTED)

    def test_scopes(self):
        assert services.permission_scope("teller", "report.operational") == "own"
        assert services.permission_scope("cso", "report.operational") == "own"
        assert services.permission_scope("manager", "report.operational") == "all"
        assert services.permission_scope("teller", "gl.view") is None
        assert services.permission_scope("nobody", "gl.view") is None

    def test_cache_cleared(self):
        assert services.role_has_permission("teller", "txn.cash_deposit")
        RolePermission.objects.filter(role="teller", permission_id="txn.cash_deposit").delete()
        assert services.role_has_permission("teller", "txn.cash_deposit")  # cached
        services.clear_cache()
        assert not services.role_has_permission("teller", "txn.cash_deposit")


@pytest.mark.django_db
class TestSeparation:
    def test_maker_checker(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        services.assert_maker_checker(a, b)
        with pytest.raises(services.PermissionDenied):
            services.assert_maker_checker(a, str(a).upper())
        with pytest.raises(services.PermissionDenied):
            services.assert_maker_checker(5, "5")

    @pytest.mark.parametrize("bad", [None, "", "  "])
    def test_rejects_empty_ids(self, bad):
        with pytest.raises((services.PermissionDenied, TypeError)):
            services.assert_maker_checker(bad, "x")
        with pytest.raises((services.PermissionDenied, TypeError)):
            services.assert_maker_checker("x", bad)
        with pytest.raises((services.PermissionDenied, TypeError)):
            services.assert_dual_control("x", "y", bad)

    def test_rejects_objects(self):
        with pytest.raises(TypeError):
            services.assert_maker_checker(SimpleNamespace(pk=1), 1)
        with pytest.raises(TypeError):
            services.assert_dual_control(1, 2, object())

    def test_dual_control(self):
        services.assert_dual_control("m", "c", "g")
        for args in [("m", "m", "g"), ("m", "c", "m"), ("m", "c", "c"), ("a", "a", "a")]:
            with pytest.raises(services.PermissionDenied):
                services.assert_dual_control(*args)

    def test_error_maps_to_403(self):
        assert services.PermissionDenied.status == 403


@pytest.mark.django_db
class TestRequirePermission:
    def call(self, monkeypatch, role, code="txn.cash_deposit"):
        monkeypatch.setattr(context, "get_active_bank_role", lambda request: role)

        @context.require_bank_permission(code)
        def view(request):
            return request.permission_scope

        request = SimpleNamespace()
        return view(request)

    def test_allowed(self, monkeypatch):
        assert self.call(monkeypatch, "teller") == "all"
        assert self.call(monkeypatch, "teller", "report.operational") == "own"

    def test_denied(self, monkeypatch):
        with pytest.raises(HttpError) as exc:
            self.call(monkeypatch, "cso")
        assert exc.value.status_code == 403 and exc.value.message == "Not allowed"

    def test_no_role_denied_by_default(self):
        @context.require_bank_permission("txn.cash_deposit")
        def view(request):
            return 1

        with pytest.raises(HttpError):
            view(SimpleNamespace())


@pytest.mark.django_db
class TestAuditLog:
    def test_record_and_scrub(self):
        user = make("s1")
        row = audit.record(
            "x.y",
            actor=user,
            entity=("thing", 5),
            after={
                "name": "a",
                "Password": "p",
                "api_key": "k",
                "sessionid": "s",
                "pw_hash": "h",
                "PIN": "1",
                "nested": [{"csrf_token": "t", "ok": 1}, ({"secret": 1, "fine": 2},)],
            },
        )
        row.refresh_from_db()
        assert row.entity_id == "5"
        assert row.after == {"name": "a", "nested": [{"ok": 1}, [{"fine": 2}]]}
        assert row.institution_id == user.institution_id

    def test_update_and_delete_refused(self):
        row = audit.record("x.y")
        row.action = "other"
        with pytest.raises(ImmutableError):
            row.save()
        with pytest.raises(ImmutableError):
            row.delete()
        with pytest.raises(ImmutableError):
            AuditLog.objects.update(action="z")
        with pytest.raises(ImmutableError):
            AuditLog.objects.all().delete()
        assert AuditLog.objects.get(pk=row.pk).action == "x.y"

    def test_db_level_update_and_delete_fail(self):
        row = audit.record("x.y")
        with pytest.raises(DatabaseError), transaction.atomic():
            AuditLog(id=row.pk, action="hacked").save(force_update=True)
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("UPDATE audit_auditlog SET action = 'hacked'")
        with pytest.raises(DatabaseError), transaction.atomic():
            with connection.cursor() as cur:
                cur.execute("DELETE FROM audit_auditlog")
        with pytest.raises(ImmutableError):
            AuditLog.objects.filter(pk=row.pk)._raw_delete(AuditLog.objects.db)
        assert AuditLog.objects.get(pk=row.pk).action == "x.y"


@pytest.mark.django_db
class TestAuthAudit:
    def test_login_success_and_logout(self):
        user = make("s1")
        client, token, _ = login("s1", "1234")
        post(client, token, "/api/auth/logout")
        rows = list(AuditLog.objects.order_by("at").values_list("action", "actor_id"))
        assert rows == [("auth.login", user.pk), ("auth.logout", user.pk)]
        assert AuditLog.objects.first().ip

    def test_login_failed(self):
        user = make("s1")
        login("s1", "wrong-secret")
        row = AuditLog.objects.get(action="auth.login_failed")
        assert row.actor is None
        assert (row.entity_type, row.entity_id) == ("user", str(user.pk))
        assert row.institution_id == user.institution_id
        assert "wrong-secret" not in str(row.__dict__)

    def test_login_failed_unknown_username_not_stored(self):
        login("typed-by-mistake", "pw")
        row = AuditLog.objects.get(action="auth.login_failed")
        assert (row.entity_type, row.entity_id) == ("unknown_username", "")
        assert row.institution_id is None
        assert "typed-by-mistake" not in str(row.__dict__)

    def test_change_password_rolls_back_with_audit_failure(self, monkeypatch):
        user = make("s1")
        client, token, _ = login("s1", "1234")

        def boom(*a, **k):
            raise RuntimeError("audit down")

        monkeypatch.setattr("apps.accounts.api.audit.record", boom)
        client.raise_request_exception = False
        resp = post(
            client,
            token,
            "/api/auth/change-password",
            {"current_password": "1234", "new_password": "newpass1"},
        )
        assert resp.status_code == 500
        user.refresh_from_db()
        assert user.check_password("1234") and user.must_change_password

    def test_change_password(self):
        user = make("s1")
        client, token, _ = login("s1", "1234")
        resp = post(
            client,
            token,
            "/api/auth/change-password",
            {"current_password": "1234", "new_password": "newpass1"},
        )
        assert resp.status_code == 200
        row = AuditLog.objects.get(action="auth.password_changed")
        assert row.actor_id == user.pk
        assert "newpass1" not in str(row.__dict__)

    def test_reset_password(self):
        admin = make("boss", PlatformRole.ADMIN)
        target = make("s1")
        acc.change_password(admin, "1234", "adminpass1")
        client, token, resp = login("boss", "adminpass1")
        resp = post(client, token, f"/api/auth/users/{target.pk}/reset-password")
        assert resp.status_code == 204
        row = AuditLog.objects.get(action="auth.password_reset")
        assert row.actor_id == admin.pk and row.entity_id == str(target.pk)


@pytest.mark.django_db
class TestAuditApi:
    def client_for(self, username, role):
        user = make(username, role)
        acc.change_password(user, "1234", "pass-1234")
        client, _, resp = login(username, "pass-1234")
        assert resp.status_code == 200
        return client, user

    def test_anonymous_401(self):
        assert Client().get("/api/audit").status_code == 401

    @pytest.mark.parametrize("role", [PlatformRole.INSTRUCTOR, PlatformRole.STUDENT])
    def test_non_admin_403(self, role):
        client, _ = self.client_for("u1", role)
        assert client.get("/api/audit").status_code == 403

    def test_flagged_user_403(self):
        make("flagged", PlatformRole.ADMIN)
        client, _, resp = login("flagged", "1234")
        assert resp.status_code == 200
        assert client.get("/api/audit").status_code == 403

    def test_admin_lists_newest_first_with_filters(self):
        client, admin = self.client_for("boss", PlatformRole.ADMIN)
        make("other")
        login("other", "bad")
        body = client.get("/api/audit").json()
        assert body["count"] == 2
        ats = [r["at"] for r in body["items"]]
        assert ats == sorted(ats, reverse=True)
        assert body["items"][0]["action"] == "auth.login_failed"

        by_action = client.get("/api/audit", {"action": "auth.login_failed"}).json()
        assert by_action["count"] == 1
        by_actor = client.get("/api/audit", {"actor": "boss"}).json()
        assert by_actor["count"] >= 1
        assert all(r["actor_username"] == "boss" for r in by_actor["items"])
        day = AuditLog.objects.first().at.date().isoformat()
        assert client.get("/api/audit", {"date_from": day, "date_to": day}).json()["count"] == 2
        assert client.get("/api/audit", {"date_from": "2999-01-01"}).json()["count"] == 0

    def test_page_size_50(self):
        client, admin = self.client_for("boss", PlatformRole.ADMIN)
        for i in range(60):
            audit.record("bulk.test", entity=("n", i), institution_id=admin.institution_id)
        body = client.get("/api/audit").json()
        assert len(body["items"]) == 50 and body["count"] >= 60

    def test_cross_institution_isolation(self):
        client, admin = self.client_for("boss", PlatformRole.ADMIN)
        other_inst = Institution.objects.create(name="Other")
        outsider = make("out1", institution=other_inst)
        audit.record("secret.other", actor=outsider)
        audit.record("secret.null")  # no institution: hidden
        actions = {r["action"] for r in client.get("/api/audit").json()["items"]}
        assert "secret.other" not in actions and "secret.null" not in actions
        assert "auth.login" in actions
