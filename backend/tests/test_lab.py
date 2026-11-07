import pytest
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory
from django.utils import timezone
from ninja.errors import HttpError

from apps.accounts import services as acc
from apps.accounts.models import PlatformRole, User
from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.banking.models import BusinessDay
from apps.lab import services as lab
from apps.lab.models import Bank, RoleAssignment, Session, SessionMember
from apps.rbac import context
from apps.rbac import services as rbac

PHONE = "+252 61 555 1234"


@pytest.fixture(autouse=True)
def _reset_rbac():
    rbac.clear_cache()
    yield
    rbac.clear_cache()


def mk(username, role=PlatformRole.STUDENT, phone=PHONE):
    user = acc.create_user(username, f"Name {username}", phone, role)
    user.must_change_password = False
    user.save(update_fields=["must_change_password"])
    return user


def api(user):
    client = Client()
    client.force_login(user)
    return client


def j(client, method, url, data=None):
    return getattr(client, method)(
        url, data=data if data is not None else {}, content_type="application/json"
    )


@pytest.fixture
def world():
    """Instructor A with class + 3 students; instructor B with own class + 1 student; admin."""
    ia, ib = mk("ia", PlatformRole.INSTRUCTOR), mk("ib", PlatformRole.INSTRUCTOR)
    admin = mk("adm", PlatformRole.ADMIN)
    ca = lab.create_class(ia, "Banking A", "BA")
    cb = lab.create_class(ib, "Banking B", "BB")
    studs = []
    for i in range(3):
        u, _ = lab.add_student(ia, ca.pk, f"s{i}", f"Stud {i}", f"+25261000{i}111")
        u.must_change_password = False
        u.save(update_fields=["must_change_password"])
        studs.append(u)
    other, _ = lab.add_student(ib, cb.pk, "o1", "Other One", "0611112222")
    return {"ia": ia, "ib": ib, "admin": admin, "ca": ca, "cb": cb, "studs": studs, "other": other}


def active_session(w, name="Lecture 1", **kw):
    s = lab.create_session(w["ia"], w["ca"].pk, name, **kw)
    lab.add_members(w["ia"], s.pk, all_enrolled=True)
    return lab.open_session(w["ia"], s.pk, 3 if kw.get("structure") == "per_group" else None)


def student_session(world, role=None, **kw):
    s = active_session(world, **kw)
    member = SessionMember.objects.get(session=s, user=world["studs"][0])
    if role:
        lab.assign_role(world["ia"], s.pk, member.pk, role)
    return s, member


@pytest.mark.django_db
class TestClassesAndStudents:
    def test_create_class_and_audit(self, world):
        c = world["ca"]
        assert c.instructor_id == world["ia"].id
        row = AuditLog.objects.get(action="lab.class_created", entity_id=str(c.pk))
        assert row.actor_id == world["ia"].id

    def test_student_cannot_create_class(self, world):
        with pytest.raises(lab.PermissionDenied):
            lab.create_class(world["studs"][0], "X", "X")
        r = j(api(world["studs"][0]), "post", "/api/classes", {"name": "a", "code": "b"})
        assert r.status_code == 403

    def test_instructor_cannot_create_for_other(self, world):
        with pytest.raises(lab.PermissionDenied):
            lab.create_class(world["ia"], "X", "X1", instructor_id=world["ib"].id)

    def test_admin_creates_for_instructor(self, world):
        c = lab.create_class(world["admin"], "Z", "ZZ", instructor_id=world["ib"].id)
        assert c.instructor_id == world["ib"].id

    def test_duplicate_code(self, world):
        with pytest.raises(lab.ValidationFailed):
            lab.create_class(world["ib"], "Dup", "BA")

    def test_cross_class_isolation_api(self, world):
        a, b = api(world["ia"]), api(world["ib"])
        assert [c["code"] for c in a.get("/api/classes").json()] == ["BA"]
        assert b.get(f"/api/classes/{world['ca'].pk}").status_code == 404
        assert b.get(f"/api/classes/{world['ca'].pk}/students").status_code == 404
        r = j(b, "post", f"/api/classes/{world['ca'].pk}/students", {"username": "zz"})
        assert r.status_code == 404
        assert len(api(world["admin"]).get("/api/classes").json()) == 2

    def test_manual_add_new_and_existing(self, world):
        u, created = lab.add_student(world["ib"], world["cb"].pk, "n1", "New One", "0612345678")
        assert created and u.check_password("5678") and u.must_change_password
        u2, created2 = lab.add_student(world["ib"], world["cb"].pk, "s0")
        assert not created2 and u2.pk == world["studs"][0].pk
        with pytest.raises(lab.ValidationFailed):
            lab.add_student(world["ib"], world["cb"].pk, "s0")  # already enrolled
        with pytest.raises(lab.ValidationFailed):
            lab.add_student(world["ib"], world["cb"].pk, "ia")  # staff username
        with pytest.raises(lab.ValidationFailed):
            lab.add_student(world["ib"], world["cb"].pk, "n2", "N", "12")  # short phone
        assert not User.objects.filter(username="n2").exists()

    def test_csv_preview_and_confirm(self, world):
        csv_text = (
            "username,full_name,phone\n"
            "c1,Csv One,0611110001\n"
            "c1,Dup Row,0611110002\n"
            "c2,,0611110003\n"
            "c3,Csv Three,12\n"
            "s0,Existing,\n"
            "ia,Staff,0611110004\n"
            "c4,Csv Four,0611110005\n"
            ",,\n"
        )
        cid = world["cb"].pk
        client = api(world["ib"])
        before = User.objects.count()
        r = j(client, "post", f"/api/classes/{cid}/students/import/preview", {"csv_text": csv_text})
        body = r.json()
        assert r.status_code == 200 and not body["imported"]
        assert User.objects.count() == before  # preview writes nothing
        actions = {}
        for x in body["rows"]:
            if x["username"]:
                actions.setdefault(x["username"], (x["action"], x["error"]))
        assert actions["c1"][0] == "create" and actions["c4"][0] == "create"
        assert actions["s0"][0] == "enroll"
        assert "duplicate" in [x["error"] for x in body["rows"] if x["line"] == 3][0]
        assert "full_name" in actions["c2"][1] and "phone" in actions["c3"][1]
        assert "non-student" in actions["ia"][1]
        assert (body["ok_count"], body["error_count"]) == (3, 4)
        r = j(client, "post", f"/api/classes/{cid}/students/import/confirm", {"csv_text": csv_text})
        assert r.status_code == 200 and r.json()["imported"]
        assert User.objects.get(username="c1").check_password("0001")
        enrolled = set(world["cb"].enrollments.values_list("user__username", flat=True))
        assert {"c1", "c4", "s0"} <= enrolled
        assert not User.objects.filter(username__in=["c2", "c3"]).exists()
        assert AuditLog.objects.filter(action="lab.students_imported").exists()
        again = j(client, "post", f"/api/classes/{cid}/students/import/confirm", {"csv_text": csv_text})
        assert again.json()["ok_count"] == 0

    def test_csv_missing_columns_and_foreign_class(self, world):
        client = api(world["ib"])
        url = f"/api/classes/{world['cb'].pk}/students/import/preview"
        r = j(client, "post", url, {"csv_text": "username,name\nx,y\n"})
        assert r.status_code == 400 and "full_name" in r.json()["detail"]
        r = j(
            client,
            "post",
            f"/api/classes/{world['ca'].pk}/students/import/confirm",
            {"csv_text": "username,full_name,phone\nq,Q,0611110000\n"},
        )
        assert r.status_code == 404
        assert not User.objects.filter(username="q").exists()

    def test_update_student_scoped(self, world):
        s = world["studs"][0]
        url = f"/api/classes/{world['ca'].pk}/students/{s.pk}"
        body = {"full_name": "Renamed", "phone": "0619998888", "is_active": False}
        r = api(world["ia"]).patch(url, data=body, content_type="application/json")
        assert r.status_code == 200 and r.json()["is_active"] is False
        s.refresh_from_db()
        assert s.full_name == "Renamed" and s.phone == "0619998888" and not s.is_active
        assert AuditLog.objects.filter(action="lab.student_updated", entity_id=str(s.pk)).exists()
        for cid in (world["ca"].pk, world["cb"].pk):
            r = api(world["ib"]).patch(
                f"/api/classes/{cid}/students/{s.pk}",
                data={"full_name": "Hack"},
                content_type="application/json",
            )
            assert r.status_code == 404
        r = api(world["studs"][1]).patch(url, data={"full_name": "x"}, content_type="application/json")
        assert r.status_code == 403
        s.refresh_from_db()
        assert s.full_name == "Renamed"
        with pytest.raises(lab.ValidationFailed):
            lab.update_student(world["ia"], world["ca"].pk, s.pk, phone="12")


@pytest.mark.django_db
class TestTemplatesAndSessions:
    def test_template_and_create_from_template(self, world):
        t = lab.create_template(
            world["ia"],
            name="Teller lecture",
            kind="practice",
            structure="per_group",
            allowed_roles=["teller"],
            default_visibility="all",
            learning_panel=False,
            seed_profile="basic",
            class_id=world["ca"].pk,
        )
        s = lab.create_session(world["ia"], world["ca"].pk, "L3", template_id=t.pk)
        assert (s.structure, s.allowed_roles, s.default_visibility, s.learning_panel) == (
            "per_group",
            ["teller"],
            "all",
            False,
        )
        assert s.status == "draft" and s.template_id == t.pk
        s2 = lab.create_session(
            world["ia"], world["ca"].pk, "L4", template_id=t.pk, default_visibility="own"
        )
        assert s2.default_visibility == "own"

    def test_template_access(self, world):
        kw = {
            "name": "T",
            "kind": "practice",
            "structure": "single_bank",
            "allowed_roles": ["teller"],
            "default_visibility": "own",
        }
        with pytest.raises(lab.PermissionDenied):
            lab.create_template(world["ia"], **kw)  # institution-wide = admin only
        wide = lab.create_template(world["admin"], **kw)
        mine = lab.create_template(world["ia"], class_id=world["ca"].pk, **kw)
        with pytest.raises(lab.NotFound):
            lab.create_template(world["ib"], class_id=world["ca"].pk, **kw)
        with pytest.raises(lab.NotFound):
            lab.create_session(world["ib"], world["cb"].pk, "x", template_id=mine.pk)
        lab.create_session(world["ib"], world["cb"].pk, "ok", template_id=wide.pk)
        ids = {t["id"] for t in api(world["ib"]).get("/api/templates").json()}
        assert str(wide.pk) in ids and str(mine.pk) not in ids
        with pytest.raises(lab.ValidationFailed):
            lab.create_template(world["admin"], **{**kw, "allowed_roles": ["king"]})

    def test_exam_forces_restrictions(self, world):
        s = lab.create_session(
            world["ia"],
            world["ca"].pk,
            "Exam",
            kind="exam",
            structure="per_group",
            default_visibility="all",
            learning_panel=True,
        )
        assert (s.structure, s.default_visibility, s.learning_panel) == ("single_bank", "own", False)

    def test_open_single_bank_creates_bank_and_day(self, world):
        s = active_session(world)
        assert s.status == "active" and s.opened_at
        bank = Bank.objects.get(session=s)
        day = BusinessDay.objects.get(bank=bank)
        assert day.status == "open" and day.date == timezone.localdate(s.opened_at)
        banks = set(SessionMember.objects.filter(session=s).values_list("bank_id", flat=True))
        assert banks == {bank.pk}
        assert AuditLog.objects.filter(action="lab.session_opened", session_id=s.pk).exists()
        assert AuditLog.objects.filter(action="lab.bank_created", bank_id=bank.pk).exists()

    def test_open_per_group(self, world):
        s = lab.create_session(world["ia"], world["ca"].pk, "G", structure="per_group")
        with pytest.raises(lab.ValidationFailed):
            lab.open_session(world["ia"], s.pk)
        lab.open_session(world["ia"], s.pk, 3)
        assert list(Bank.objects.filter(session=s).values_list("group_no", flat=True)) == [1, 2, 3]
        assert BusinessDay.objects.filter(bank__session=s, status="open").count() == 3
        assert lab.add_group_bank(world["ia"], s.pk).group_no == 4
        with pytest.raises(lab.Conflict):
            lab.open_session(world["ia"], s.pk, 2)  # no longer a draft

    def test_one_open_business_day_per_bank_db_constraint(self, world):
        bank = Bank.objects.get(session=active_session(world))
        with pytest.raises(IntegrityError), transaction.atomic():
            BusinessDay.objects.create(bank=bank, date="2030-01-01")

    def test_session_cross_class(self, world):
        s = active_session(world)
        b = api(world["ib"])
        assert b.get(f"/api/sessions/{s.pk}").status_code == 404
        assert j(b, "post", f"/api/sessions/{s.pk}/archive").status_code == 404
        assert b.get(f"/api/sessions/{s.pk}/members").status_code == 404
        assert b.get(f"/api/sessions/{s.pk}/permissions").status_code == 404
        assert api(world["ia"]).get(f"/api/sessions/{s.pk}").status_code == 200
        assert api(world["admin"]).get(f"/api/sessions/{s.pk}").status_code == 200
        assert api(world["studs"][0]).get(f"/api/sessions/{s.pk}").status_code == 403
        body = {"class_id": str(world["cb"].pk), "name": "x"}
        assert j(api(world["ia"]), "post", "/api/sessions", body).status_code == 404

    def test_archive_reopen_cycle(self, world):
        s = active_session(world)
        with pytest.raises(lab.Conflict):
            lab.reopen_session(world["ia"], s.pk)
        lab.archive_session(world["ia"], s.pk)
        s.refresh_from_db()
        assert s.status == "archived" and s.archived_at
        with pytest.raises(lab.Conflict):
            lab.archive_session(world["ia"], s.pk)
        lab.reopen_session(world["ia"], s.pk)
        s.refresh_from_db()
        assert s.status == "active" and s.archived_at is None
        actions = set(AuditLog.objects.filter(session_id=s.pk).values_list("action", flat=True))
        assert {"lab.session_archived", "lab.session_reopened"} <= actions

    def test_archived_rejects_every_write(self, world):
        s = active_session(world)
        member = SessionMember.objects.filter(session=s).first()
        bank = Bank.objects.get(session=s)
        lab.archive_session(world["ia"], s.pk)
        ia, sid = world["ia"], s.pk
        calls = [
            lambda: lab.add_members(ia, sid, [world["studs"][0].pk]),
            lambda: lab.move_member(ia, sid, member.pk, bank.pk),
            lambda: lab.set_visibility_override(ia, sid, member.pk, "all"),
            lambda: lab.assign_role(ia, sid, member.pk, "teller"),
            lambda: lab.set_permission_override(ia, sid, "teller", "gl.view", True),
            lambda: lab.clear_permission_override(ia, sid, "teller", "gl.view"),
            lambda: lab.add_group_bank(ia, sid),
        ]
        for call in calls:
            with pytest.raises(lab.Conflict):
                call()
        assert api(ia).get(f"/api/sessions/{sid}/members").status_code == 200


@pytest.mark.django_db
class TestMembersAndRoles:
    def test_members_must_be_enrolled(self, world):
        s = lab.create_session(world["ia"], world["ca"].pk, "L")
        with pytest.raises(lab.ValidationFailed):
            lab.add_members(world["ia"], s.pk, [world["other"].pk])
        added = lab.add_members(world["ia"], s.pk, [world["studs"][0].pk])
        assert added[0].bank_id is None  # draft: not placed yet
        with pytest.raises(lab.ValidationFailed):
            lab.add_members(world["ia"], s.pk, [world["studs"][0].pk])

    def test_add_to_active_single_bank_autoplaces(self, world):
        s = lab.create_session(world["ia"], world["ca"].pk, "L")
        lab.open_session(world["ia"], s.pk)
        m = lab.add_members(world["ia"], s.pk, [world["studs"][0].pk])[0]
        assert m.bank_id == Bank.objects.get(session=s).pk

    def test_move_member_between_banks_only_within_session(self, world):
        s = active_session(world, structure="per_group")
        other = active_session(world, name="Other")
        m = SessionMember.objects.filter(session=s).first()
        b2 = Bank.objects.filter(session=s).order_by("group_no")[1]
        lab.move_member(world["ia"], s.pk, m.pk, b2.pk)
        m.refresh_from_db()
        assert m.bank_id == b2.pk
        foreign_bank = Bank.objects.get(session=other)
        with pytest.raises(lab.NotFound):
            lab.move_member(world["ia"], s.pk, m.pk, foreign_bank.pk)
        with pytest.raises(lab.NotFound):  # member of another session
            lab.move_member(world["ia"], other.pk, m.pk, foreign_bank.pk)

    def test_one_active_role_and_history(self, world):
        s = active_session(world)
        m = SessionMember.objects.filter(session=s).first()
        a1 = lab.assign_role(world["ia"], s.pk, m.pk, "teller")
        assert lab.assign_role(world["ia"], s.pk, m.pk, "teller").pk == a1.pk  # no-op
        a2 = lab.assign_role(world["ia"], s.pk, m.pk, "cso")
        a1.refresh_from_db()
        assert a1.active_to is not None and a2.active_to is None
        assert RoleAssignment.objects.filter(session_member=m, active_to__isnull=True).count() == 1
        assert RoleAssignment.objects.filter(session_member=m).count() == 2
        with pytest.raises(IntegrityError), transaction.atomic():
            RoleAssignment.objects.create(
                session_member=m,
                role="manager",
                assigned_by=world["ia"],
                active_from=a2.active_from,
            )
        assert AuditLog.objects.filter(action="lab.role_assigned", session_id=s.pk).count() == 2

    def test_role_must_be_allowed(self, world):
        s = active_session(world, allowed_roles=["teller"])
        m = SessionMember.objects.filter(session=s).first()
        with pytest.raises(lab.ValidationFailed):
            lab.assign_role(world["ia"], s.pk, m.pk, "manager")
        with pytest.raises(lab.ValidationFailed):
            lab.assign_role(world["ia"], s.pk, m.pk, "nonsense")

    def test_role_api_permissions(self, world):
        s = active_session(world)
        m = SessionMember.objects.filter(session=s).first()
        url = f"/api/sessions/{s.pk}/members/{m.pk}/role"
        assert j(api(world["ib"]), "post", url, {"role": "teller"}).status_code == 404
        assert j(api(world["studs"][0]), "post", url, {"role": "teller"}).status_code == 403
        assert j(api(world["ia"]), "post", url, {"role": "teller"}).status_code == 200
        rows = api(world["ia"]).get(f"/api/sessions/{s.pk}/members").json()
        assert {x["role"] for x in rows} == {"teller", None}

    def test_visibility_override(self, world):
        s = active_session(world)
        m = SessionMember.objects.filter(session=s).first()
        lab.set_visibility_override(world["ia"], s.pk, m.pk, "all")
        m.refresh_from_db()
        assert m.visibility_override == "all"
        lab.set_visibility_override(world["ia"], s.pk, m.pk, None)
        with pytest.raises(lab.ValidationFailed):
            lab.set_visibility_override(world["ia"], s.pk, m.pk, "x")


@pytest.mark.django_db
class TestPermissionOverrides:
    def test_override_applied_and_cleared(self, world):
        s = active_session(world)
        assert not rbac.role_has_permission("teller", "gl.view", session=s)
        lab.set_permission_override(world["ia"], s.pk, "teller", "gl.view", True)
        assert rbac.permission_scope("teller", "gl.view", session=s) == "all"
        assert not rbac.role_has_permission("teller", "gl.view")  # defaults untouched
        lab.set_permission_override(world["ia"], s.pk, "teller", "txn.cash_deposit", False)
        assert not rbac.role_has_permission("teller", "txn.cash_deposit", session=s)
        assert rbac.permission_scope("teller", "report.operational", session=s) == "own"
        lab.set_permission_override(world["ia"], s.pk, "teller", "gl.view", False)  # update
        assert not rbac.role_has_permission("teller", "gl.view", session=s)
        lab.clear_permission_override(world["ia"], s.pk, "teller", "gl.view")
        with pytest.raises(lab.NotFound):
            lab.clear_permission_override(world["ia"], s.pk, "teller", "gl.view")
        s2 = active_session(world, name="Other")  # other session unaffected
        assert rbac.role_has_permission("teller", "txn.cash_deposit", session=s2)

    def test_matrix_api(self, world):
        s = active_session(world)
        lab.set_permission_override(world["ia"], s.pk, "cso", "gl.view", True)
        cells = api(world["ia"]).get(f"/api/sessions/{s.pk}/permissions").json()
        assert len(cells) == 5 * 30
        cell = next(c for c in cells if c["role"] == "cso" and c["permission_code"] == "gl.view")
        assert (cell["default_scope"], cell["override"], cell["effective_scope"]) == (
            None,
            True,
            "all",
        )

    def test_invalid_inputs_and_api(self, world):
        s = active_session(world)
        with pytest.raises(lab.ValidationFailed):
            lab.set_permission_override(world["ia"], s.pk, "teller", "no.such", True)
        with pytest.raises(lab.ValidationFailed):
            lab.set_permission_override(world["ia"], s.pk, "king", "gl.view", True)
        url = f"/api/sessions/{s.pk}/permissions/overrides"
        body = {"role": "teller", "permission_code": "gl.view", "allowed": True}
        assert api(world["ib"]).put(url, data=body, content_type="application/json").status_code == 404
        assert api(world["ia"]).put(url, data=body, content_type="application/json").status_code == 200
        assert j(api(world["ia"]), "post", url + "/clear", body).status_code == 204

    def test_sod_not_overridable(self, world, monkeypatch):
        s = active_session(world)
        lab.set_permission_override(world["ia"], s.pk, "teller", "approval.decide", True)
        lab.set_permission_override(world["ia"], s.pk, "teller", "cash.vault.approve_manager", True)
        with pytest.raises(rbac.PermissionDenied):
            rbac.assert_maker_checker("u1", "u1")
        with pytest.raises(rbac.PermissionDenied):
            rbac.assert_dual_control("u1", "u2", "u1")
        monkeypatch.setitem(rbac.SOD_FORBIDDEN_GRANTS, "teller", frozenset({"gl.view"}))
        with pytest.raises(rbac.RbacError):
            lab.set_permission_override(world["ia"], s.pk, "teller", "gl.view", True)
        lab.set_permission_override(world["ia"], s.pk, "teller", "gl.view", False)

    def test_override_audited(self, world):
        s = active_session(world)
        lab.set_permission_override(world["ia"], s.pk, "teller", "gl.view", True)
        row = AuditLog.objects.get(action="lab.permission_override_set")
        assert row.session_id == s.pk and row.after["allowed"] is True


@pytest.mark.django_db
class TestStudentContext:
    def test_my_sessions_active_only(self, world):
        s, _ = student_session(world, "teller")
        draft = lab.create_session(world["ia"], world["ca"].pk, "Draft")
        lab.add_members(world["ia"], draft.pk, all_enrolled=True)
        arch, _ = student_session(world)
        lab.archive_session(world["ia"], arch.pk)
        rows = api(world["studs"][0]).get("/api/my/sessions").json()
        assert [r["session_id"] for r in rows] == [str(s.pk)]
        assert rows[0]["role"] == "teller"
        assert api(world["ia"]).get("/api/my/sessions").status_code == 403

    def test_me(self, world):
        s, _ = student_session(world, "teller")
        client = api(world["studs"][0])
        r = client.get(f"/api/s/{s.pk}/me")
        body = r.json()
        assert r.status_code == 200
        assert body["role"] == "teller" and body["bank_name"] == s.name
        assert body["visibility"] == "own" and body["learning_panel"] is True
        assert body["business_date"] == str(BusinessDay.objects.get(bank__session=s).date)
        perms = {p["code"]: p["scope"] for p in body["permissions"]}
        assert perms["txn.cash_deposit"] == "all" and "gl.view" not in perms
        lab.set_permission_override(world["ia"], s.pk, "teller", "gl.view", True)
        after = client.get(f"/api/s/{s.pk}/me").json()["permissions"]
        assert "gl.view" in {p["code"] for p in after}

    def test_me_isolation(self, world):
        s, _ = student_session(world, "teller")
        assert api(world["other"]).get(f"/api/s/{s.pk}/me").status_code == 403  # not a member
        assert api(world["ia"]).get(f"/api/s/{s.pk}/me").status_code == 403
        s2 = lab.create_session(world["ia"], world["ca"].pk, "S2")
        lab.add_members(world["ia"], s2.pk, [world["studs"][1].pk])
        lab.open_session(world["ia"], s2.pk)
        # student 1 is in both sessions, student 0 only in the first
        assert api(world["studs"][1]).get(f"/api/s/{s2.pk}/me").status_code == 200
        assert api(world["studs"][0]).get(f"/api/s/{s2.pk}/me").status_code == 403

    def test_me_without_role_draft_archived(self, world):
        s, _ = student_session(world)
        body = api(world["studs"][0]).get(f"/api/s/{s.pk}/me").json()
        assert body["role"] is None and body["permissions"] == []
        draft = lab.create_session(world["ia"], world["ca"].pk, "D")
        lab.add_members(world["ia"], draft.pk, all_enrolled=True)
        assert api(world["studs"][0]).get(f"/api/s/{draft.pk}/me").status_code == 409
        lab.archive_session(world["ia"], s.pk)
        r = api(world["studs"][0]).get(f"/api/s/{s.pk}/me").json()
        assert r["read_only"] is True and r["status"] == "archived"

    def test_effective_visibility(self, world):
        s, member = student_session(world, "teller")
        ev = context.effective_visibility
        assert ev(s, member, "teller") == "own"
        member.visibility_override = "all"
        assert ev(s, member, "teller") == "all"
        member.visibility_override = "own"
        s.default_visibility = "all"
        assert ev(s, member, "cso") == "own"
        for role in ("manager", "vault_custodian", "accountant"):
            assert ev(s, member, role) == "all"
        s.kind = "exam"
        member.visibility_override = "all"
        assert ev(s, member, "manager") == "own" and ev(s, member, "teller") == "own"


@pytest.mark.django_db
class TestBankPermissionDecorator:
    def view(self, code="txn.cash_deposit"):
        @context.require_bank_permission(code)
        def v(request, session_id):
            return request.permission_scope, request.bank_role, request.bank, request.session_member

        return v

    def req(self, user, method="POST"):
        r = RequestFactory().generic(method, "/x")
        r.user = user
        return r

    def test_resolves_and_sets_context(self, world):
        s, member = student_session(world, "teller")
        v = self.view()
        scope, role, bank, m = v(self.req(world["studs"][0]), session_id=s.pk)
        assert (scope, role, m.pk) == ("own", "teller", member.pk)
        assert bank.session_id == s.pk
        lab.assign_role(world["ia"], s.pk, member.pk, "cso")  # cso lacks the permission
        with pytest.raises(HttpError) as e:
            v(self.req(world["studs"][0]), session_id=s.pk)
        assert e.value.status_code == 403
        with pytest.raises(HttpError) as e:
            v(self.req(world["other"]), session_id=s.pk)  # not a member
        assert e.value.status_code == 403
        with pytest.raises(HttpError) as e:
            v(self.req(world["studs"][1]), session_id=s.pk)  # member without role
        assert e.value.status_code == 403
        with pytest.raises(HttpError):
            v(self.req(world["studs"][0]), session_id=None)

    def test_override_and_scope(self, world):
        s, member = student_session(world, "cso")
        lab.set_permission_override(world["ia"], s.pk, "cso", "txn.cash_deposit", True)
        lab.set_visibility_override(world["ia"], s.pk, member.pk, "all")
        scope, role, *_ = self.view()(self.req(world["studs"][0]), session_id=s.pk)
        assert (scope, role) == ("all", "cso")

    def test_archived_reads_ok_writes_blocked(self, world):
        s, _ = student_session(world, "teller")
        lab.archive_session(world["ia"], s.pk)
        v = self.view("report.operational")
        assert v(self.req(world["studs"][0], "GET"), session_id=s.pk)[1] == "teller"
        with pytest.raises(HttpError) as e:
            v(self.req(world["studs"][0], "POST"), session_id=s.pk)
        assert e.value.status_code == 409

    def test_cross_bank_isolation(self, world):
        s, _ = student_session(world, "teller", structure="per_group")
        banks = list(Bank.objects.filter(session=s).order_by("group_no"))
        m1 = SessionMember.objects.get(session=s, user=world["studs"][1])
        lab.move_member(world["ia"], s.pk, m1.pk, banks[1].pk)
        lab.assign_role(world["ia"], s.pk, m1.pk, "teller")
        _, _, bank, _ = self.view()(self.req(world["studs"][1]), session_id=s.pk)
        assert bank.pk == banks[1].pk
        m2 = SessionMember.objects.get(session=s, user=world["studs"][2])
        assert m2.bank_id is None  # per-group: unplaced -> denied even with a role
        lab.assign_role(world["ia"], s.pk, m2.pk, "teller")
        with pytest.raises(HttpError):
            self.view()(self.req(world["studs"][2]), session_id=s.pk)


@pytest.mark.django_db
class TestAuditScoping:
    def test_instructor_sees_only_own_sessions(self, world):
        sa = active_session(world)
        sb = lab.create_session(world["ib"], world["cb"].pk, "B session")
        a = api(world["ia"]).get("/api/audit").json()
        assert a["count"] > 0 and all(r["session_id"] == str(sa.pk) for r in a["items"])
        b = api(world["ib"]).get("/api/audit").json()
        assert b["count"] > 0 and all(r["session_id"] == str(sb.pk) for r in b["items"])
        assert api(world["ib"]).get("/api/audit", {"session_id": str(sa.pk)}).json()["count"] == 0
        items = api(world["admin"]).get("/api/audit").json()["items"]
        assert {r["session_id"] for r in items} >= {str(sa.pk), str(sb.pk)}

    def test_student_manager_own_bank_only(self, world):
        s, member = student_session(world, "manager", structure="per_group")
        banks = list(Bank.objects.filter(session=s).order_by("group_no"))
        lab.move_member(world["ia"], s.pk, member.pk, banks[0].pk)
        inst = world["ia"].institution_id
        audit.record("x.b1", session_id=s.pk, bank_id=banks[0].pk, institution_id=inst)
        audit.record("x.b2", session_id=s.pk, bank_id=banks[1].pk, institution_id=inst)
        audit.record("x.nobank", session_id=s.pk, institution_id=inst)
        rows = api(world["studs"][0]).get("/api/audit").json()["items"]
        actions = {r["action"] for r in rows}
        assert "x.b1" in actions and "x.b2" not in actions and "x.nobank" not in actions
        assert all(r["bank_id"] == str(banks[0].pk) for r in rows)
        assert api(world["studs"][1]).get("/api/audit").status_code == 403
        lab.set_permission_override(world["ia"], s.pk, "manager", "audit.view", False)
        assert api(world["studs"][0]).get("/api/audit").status_code == 403

    def test_manager_of_other_session_cannot_see(self, world):
        student_session(world, "manager")
        s2 = lab.create_session(world["ia"], world["ca"].pk, "S2")
        lab.open_session(world["ia"], s2.pk)
        inst = world["ia"].institution_id
        audit.record("x.s2", session_id=s2.pk, bank_id=Bank.objects.get(session=s2).pk, institution_id=inst)
        rows = api(world["studs"][0]).get("/api/audit").json()["items"]
        assert "x.s2" not in {r["action"] for r in rows}

    def test_fk_integrity(self, world):
        s = active_session(world)
        row = audit.record("x", session_id=s.pk)
        assert row.session == s
        assert Session.objects.filter(pk=row.session_id).exists()
