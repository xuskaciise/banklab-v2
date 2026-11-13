"""1.12b Admin console: instructors, institution settings, CoA and session templates."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts import services as acc
from apps.accounts.models import Institution, PlatformRole, User
from apps.adminconsole import services as svc
from apps.audit.models import AuditLog
from apps.lab import services as lab
from apps.lab.models import Bank, Session
from apps.ledger import services as ledger
from apps.ledger.models import CoaTemplate, GLAccount
from tests.test_lab import PHONE, _reset_rbac, api, j, mk, world  # noqa: F401

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 30
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 30 + b"\xff\xd9"
TPL = {
    "name": "Std",
    "kind": "practice",
    "structure": "single_bank",
    "allowed_roles": ["teller"],
    "default_visibility": "all",
}


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def adm(world):  # noqa: F811
    return api(world["admin"])


def other_inst_admin():
    inst = Institution.objects.create(name="Other Uni")
    u = acc.create_user("oadm", "O Admin", PHONE, PlatformRole.ADMIN, institution=inst)
    u.must_change_password = False
    u.save(update_fields=["must_change_password"])
    return u, inst


def upload(client, url, data, name="l.png", ctype="image/png"):
    return client.post(url, {"file": SimpleUploadedFile(name, data, content_type=ctype)})


@pytest.mark.django_db
class TestPermissions:
    def test_non_admin_forbidden_everywhere(self, world):  # noqa: F811
        tid = ledger.get_default_template(world["admin"].institution).pk
        uid = world["ia"].pk
        calls = [
            ("get", "/api/admin/instructors", None),
            ("post", "/api/admin/instructors", {"username": "x", "full_name": "x", "phone": PHONE}),
            ("put", f"/api/admin/instructors/{uid}/active", {"is_active": False}),
            ("post", f"/api/admin/instructors/{uid}/reset-password", None),
            ("get", "/api/admin/institution", None),
            ("put", "/api/admin/institution", {"name": "Z"}),
            ("delete", "/api/admin/institution/logo", None),
            ("get", "/api/admin/coa-templates", None),
            ("post", "/api/admin/coa-templates", {"name": "N"}),
            ("get", f"/api/admin/coa-templates/{tid}", None),
            ("delete", f"/api/admin/coa-templates/{tid}", None),
            (
                "post",
                f"/api/admin/coa-templates/{tid}/lines",
                {"code": "9", "name": "n", "type": "asset"},
            ),
            ("patch", f"/api/admin/coa-templates/{tid}/lines/{uid}", {"name": "n"}),
            ("get", "/api/admin/session-templates", None),
            ("post", "/api/admin/session-templates", TPL),
            ("put", f"/api/admin/session-templates/{tid}", TPL),
            ("delete", f"/api/admin/session-templates/{tid}", None),
        ]
        for user in (world["ia"], world["studs"][0]):
            c = api(user)
            for method, url, data in calls:
                r = j(c, method, url, data)
                assert r.status_code == 403, (user.username, method, url, r.status_code)
        c = api(world["ia"])
        assert upload(c, "/api/admin/institution/logo", PNG).status_code == 403
        assert AuditLog.objects.filter(action__startswith="admin.").count() == 0


@pytest.mark.django_db
class TestInstructors:
    def test_create_list_login_flow(self, world, adm):  # noqa: F811
        r = j(
            adm,
            "post",
            "/api/admin/instructors",
            {"username": "newi", "full_name": "New I", "phone": "+252 61 999 4321"},
        )
        assert r.status_code == 200, r.content
        u = User.objects.get(username="newi")
        assert u.platform_role == PlatformRole.INSTRUCTOR and u.must_change_password
        assert u.check_password("4321")
        assert u.institution_id == world["admin"].institution_id
        assert AuditLog.objects.filter(action="admin.instructor_created").exists()
        names = [x["username"] for x in adm.get("/api/admin/instructors").json()]
        assert "newi" in names and "ia" in names and "s0" not in names and "adm" not in names

    def test_duplicate_and_bad_phone(self, world, adm):  # noqa: F811
        body = {"username": "ia", "full_name": "Dup", "phone": PHONE}
        assert j(adm, "post", "/api/admin/instructors", body).status_code == 400
        body = {"username": "n2", "full_name": "Dup", "phone": "12"}
        assert j(adm, "post", "/api/admin/instructors", body).status_code == 400

    def test_deactivate_reactivate_blocks_login(self, world, adm):  # noqa: F811
        ia = world["ia"]
        ia.set_password("pw12345")
        ia.must_change_password = False
        ia.save()
        url = f"/api/admin/instructors/{ia.pk}/active"
        assert j(adm, "put", url, {"is_active": False}).status_code == 200
        from django.test import Client

        c = Client()
        tok = c.get("/api/auth/csrf").json()["csrf_token"]
        r = c.post(
            "/api/auth/staff-login",
            {"username": "ia", "password": "pw12345"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=tok,
        )
        assert r.status_code == 401
        assert AuditLog.objects.filter(action="admin.instructor_deactivated").exists()
        assert j(adm, "put", url, {"is_active": True}).status_code == 200
        assert AuditLog.objects.filter(action="admin.instructor_reactivated").exists()

    def test_cannot_deactivate_self_or_non_instructor(self, world, adm, monkeypatch):  # noqa: F811
        admin = world["admin"]
        r = j(adm, "put", f"/api/admin/instructors/{admin.pk}/active", {"is_active": False})
        assert r.status_code == 404  # admin is not an instructor target
        stud = world["studs"][0]
        r = j(adm, "put", f"/api/admin/instructors/{stud.pk}/active", {"is_active": False})
        assert r.status_code == 404
        # Defence in depth: even if the lookup returned the actor, the guard refuses.
        monkeypatch.setattr(svc, "_get_instructor", lambda a, uid, lock=False: admin)
        with pytest.raises(svc.ConsoleError, match="yourself"):
            svc.set_instructor_active(admin, admin.pk, False)
        admin.refresh_from_db()
        assert admin.is_active

    def test_reset_password(self, world, adm):  # noqa: F811
        ia = world["ia"]
        ia.set_password("other-pw")
        ia.must_change_password = False
        ia.save()
        r = j(adm, "post", f"/api/admin/instructors/{ia.pk}/reset-password")
        assert r.status_code == 204
        ia.refresh_from_db()
        assert ia.must_change_password and ia.check_password("1234")
        assert AuditLog.objects.filter(action="auth.password_reset", entity_id=str(ia.pk)).exists()

    def test_cross_institution(self, world, adm):  # noqa: F811
        oadm, inst = other_inst_admin()
        oi = acc.create_user("oi", "O I", PHONE, PlatformRole.INSTRUCTOR, institution=inst)
        assert [x["username"] for x in api(oadm).get("/api/admin/instructors").json()] == ["oi"]
        assert (
            j(
                adm, "put", f"/api/admin/instructors/{oi.pk}/active", {"is_active": False}
            ).status_code
            == 404
        )
        assert j(adm, "post", f"/api/admin/instructors/{oi.pk}/reset-password").status_code == 404
        oi.refresh_from_db()
        assert oi.is_active


@pytest.mark.django_db
class TestInstitution:
    def test_name_update_and_validation(self, world, adm):  # noqa: F811
        r = j(adm, "put", "/api/admin/institution", {"name": "  Simad  "})
        assert r.status_code == 200 and r.json()["name"] == "Simad"
        assert j(adm, "put", "/api/admin/institution", {"name": "   "}).status_code == 400
        Institution.objects.create(name="Taken")
        assert j(adm, "put", "/api/admin/institution", {"name": "taken"}).status_code == 409
        row = AuditLog.objects.get(action="admin.institution_updated")
        assert row.after == {"name": "Simad"}

    def test_logo_upload_serve_delete(self, world, adm):  # noqa: F811
        assert adm.get("/api/institution/logo").status_code == 404
        r = upload(adm, "/api/admin/institution/logo", PNG)
        assert r.status_code == 200 and r.json()["logo_url"] == "/api/institution/logo"
        # any signed-in user of the institution can view it; me exposes the url
        s = api(world["studs"][0])
        got = s.get("/api/institution/logo")
        assert got.status_code == 200 and got["Content-Type"] == "image/png"
        assert b"".join(got.streaming_content).startswith(b"\x89PNG")
        assert s.get("/api/auth/me").json()["logo_url"] == "/api/institution/logo"
        assert s.get("/api/auth/me").json()["institution_name"] == "SIU"
        # replace with JPG
        assert (
            upload(adm, "/api/admin/institution/logo", JPG, "l.jpg", "image/jpeg").status_code
            == 200
        )
        assert api(world["ia"]).get("/api/institution/logo")["Content-Type"] == "image/jpeg"
        assert adm.delete("/api/admin/institution/logo").status_code == 200
        assert adm.get("/api/institution/logo").status_code == 404
        assert adm.delete("/api/admin/institution/logo").status_code == 404
        actions = set(AuditLog.objects.values_list("action", flat=True))
        assert {"admin.institution_logo_set", "admin.institution_logo_removed"} <= actions

    def test_logo_validation(self, world, adm):  # noqa: F811
        url = "/api/admin/institution/logo"
        assert upload(adm, url, b"GIF89a" + b"0" * 50, "l.png").status_code == 400
        assert upload(adm, url, b"<svg></svg>", "l.png").status_code == 400
        assert upload(adm, url, b"%PDF-1.4 hello", "l.png").status_code == 400
        assert upload(adm, url, PNG + b"\x00" * (1024 * 1024)).status_code == 400
        assert upload(adm, url, PNG[:8]).status_code == 400  # signature only

    def test_logo_isolated_per_institution(self, world, adm):  # noqa: F811
        oadm, _ = other_inst_admin()
        upload(adm, "/api/admin/institution/logo", PNG)
        assert api(oadm).get("/api/institution/logo").status_code == 404


@pytest.mark.django_db
class TestCoaTemplates:
    def test_list_create_copy_detail(self, world, adm):  # noqa: F811
        rows = adm.get("/api/admin/coa-templates").json()
        assert len(rows) == 1 and rows[0]["is_default"] and rows[0]["line_count"] > 10
        r = j(adm, "post", "/api/admin/coa-templates", {"name": "Mine"})
        assert r.status_code == 200
        body = r.json()
        assert len(body["lines"]) == rows[0]["line_count"] and not body["is_default"]
        r2 = j(
            adm, "post", "/api/admin/coa-templates", {"name": "Mine2", "copy_from_id": body["id"]}
        )
        assert r2.status_code == 200
        assert j(adm, "post", "/api/admin/coa-templates", {"name": "mine"}).status_code == 409
        assert j(adm, "post", "/api/admin/coa-templates", {"name": " "}).status_code == 400
        assert adm.get(f"/api/admin/coa-templates/{body['id']}").json()["name"] == "Mine"
        assert AuditLog.objects.filter(action="admin.coa_template_created").count() == 2

    def test_line_rules(self, world, adm):  # noqa: F811
        tid = j(adm, "post", "/api/admin/coa-templates", {"name": "T"}).json()["id"]
        base = f"/api/admin/coa-templates/{tid}/lines"
        tpl = CoaTemplate.objects.get(pk=tid)
        header = tpl.lines.filter(
            postable=False, system_tag="", is_active=True, parent_code=""
        ).first()
        new = {
            "code": "1999",
            "name": "Petty",
            "type": header.type,
            "parent_code": header.code,
            "postable": True,
        }
        r = j(adm, "post", base, new)
        assert r.status_code == 200, r.content
        lid = r.json()["id"]
        assert r.json()["system_tag"] == ""
        assert j(adm, "post", base, new).status_code == 409  # duplicate code
        assert (
            j(adm, "post", base, {**new, "code": "1998", "parent_code": "nope"}).status_code == 400
        )
        assert (
            j(adm, "post", base, {**new, "code": "1997", "parent_code": "1999"}).status_code == 400
        )
        assert j(adm, "post", base, {**new, "code": "1996", "type": "bogus"}).status_code == 400
        # rename + toggle
        r = adm.patch(
            f"{base}/{lid}",
            {"name": "Petty Cash", "is_active": False},
            content_type="application/json",
        )
        assert (
            r.status_code == 200 and r.json()["name"] == "Petty Cash" and not r.json()["is_active"]
        )
        assert AuditLog.objects.filter(action="admin.coa_line_updated").exists()
        # system line locked
        sys_line = tpl.lines.exclude(system_tag="").first()
        r = adm.patch(f"{base}/{sys_line.pk}", {"name": "X"}, content_type="application/json")
        assert r.status_code == 409
        r = adm.patch(
            f"{base}/{sys_line.pk}", {"is_active": False}, content_type="application/json"
        )
        assert r.status_code == 409
        sys_line.refresh_from_db()
        assert sys_line.is_active

    def test_delete_rules(self, world, adm):  # noqa: F811
        default = ledger.get_default_template(world["admin"].institution)
        assert adm.delete(f"/api/admin/coa-templates/{default.pk}").status_code == 409
        tid = j(adm, "post", "/api/admin/coa-templates", {"name": "Used"}).json()["id"]
        st = j(adm, "post", "/api/admin/session-templates", {**TPL, "coa_template_id": tid})
        assert st.status_code == 200, st.content
        assert adm.delete(f"/api/admin/coa-templates/{tid}").status_code == 409
        assert adm.delete(f"/api/admin/session-templates/{st.json()['id']}").status_code == 204
        assert adm.delete(f"/api/admin/coa-templates/{tid}").status_code == 204
        assert not CoaTemplate.objects.filter(pk=tid).exists()
        assert AuditLog.objects.filter(action="admin.coa_template_deleted").exists()

    def test_cross_institution(self, world, adm):  # noqa: F811
        oadm, inst = other_inst_admin()
        mine = ledger.get_default_template(inst)
        assert [r["id"] for r in api(oadm).get("/api/admin/coa-templates").json()] == [str(mine.pk)]
        mine_id = ledger.get_default_template(world["admin"].institution).pk
        assert api(oadm).get(f"/api/admin/coa-templates/{mine_id}").status_code == 404
        assert (
            j(
                api(oadm),
                "post",
                "/api/admin/coa-templates",
                {"name": "x", "copy_from_id": str(mine_id)},
            ).status_code
            == 404
        )
        assert api(oadm).delete(f"/api/admin/coa-templates/{mine_id}").status_code == 404
        base = f"/api/admin/coa-templates/{mine_id}/lines"
        assert (
            j(api(oadm), "post", base, {"code": "9", "name": "n", "type": "asset"}).status_code
            == 404
        )

    def test_edits_do_not_affect_existing_sessions(self, world, adm):  # noqa: F811
        tid = j(adm, "post", "/api/admin/coa-templates", {"name": "Snap"}).json()["id"]
        stid = j(
            adm, "post", "/api/admin/session-templates", {**TPL, "coa_template_id": tid}
        ).json()["id"]
        s = lab.create_session(world["ia"], world["ca"].pk, "L1", template_id=stid)
        lab.add_members(world["ia"], s.pk, all_enrolled=True)
        lab.open_session(world["ia"], s.pk, None)
        bank = Bank.objects.get(session=s)
        before = GLAccount.objects.filter(bank=bank).count()
        assert before > 0
        base = f"/api/admin/coa-templates/{tid}/lines"
        tpl = CoaTemplate.objects.get(pk=tid)
        line = tpl.lines.filter(system_tag="", is_active=True).first()
        adm.patch(
            f"{base}/{line.pk}",
            {"name": "Renamed later", "is_active": False},
            content_type="application/json",
        )
        j(adm, "post", base, {"code": "1998", "name": "New", "type": "asset", "postable": False})
        assert GLAccount.objects.filter(bank=bank).count() == before
        gl = GLAccount.objects.get(bank=bank, code=line.code)
        assert gl.name != "Renamed later" and gl.is_active


@pytest.mark.django_db
class TestSessionTemplates:
    def test_crud(self, world, adm):  # noqa: F811
        r = j(adm, "post", "/api/admin/session-templates", TPL)
        assert r.status_code == 200, r.content
        tid = r.json()["id"]
        assert r.json()["coa_template_id"] is None
        r = j(
            adm,
            "put",
            f"/api/admin/session-templates/{tid}",
            {**TPL, "name": "Std2", "allowed_roles": ["teller", "cso"]},
        )
        assert r.status_code == 200 and r.json()["name"] == "Std2"
        assert [t["name"] for t in adm.get("/api/admin/session-templates").json()] == ["Std2"]
        assert AuditLog.objects.filter(action="admin.session_template_updated").exists()
        # class-owned templates are not in the console list
        lab.create_template(world["ia"], class_id=world["ca"].pk, **TPL)
        assert len(adm.get("/api/admin/session-templates").json()) == 1
        assert adm.delete(f"/api/admin/session-templates/{tid}").status_code == 204
        assert AuditLog.objects.filter(action="admin.session_template_deleted").exists()

    def test_validation(self, world, adm):  # noqa: F811
        assert (
            j(adm, "post", "/api/admin/session-templates", {**TPL, "allowed_roles": []}).status_code
            == 400
        )
        assert (
            j(adm, "post", "/api/admin/session-templates", {**TPL, "kind": "x"}).status_code == 400
        )

    def test_delete_blocked_when_session_uses_it(self, world, adm):  # noqa: F811
        tid = j(adm, "post", "/api/admin/session-templates", TPL).json()["id"]
        lab.create_session(world["ia"], world["ca"].pk, "Uses", template_id=tid)
        assert adm.delete(f"/api/admin/session-templates/{tid}").status_code == 409
        assert Session.objects.filter(template_id=tid).exists()

    def test_coa_swap_blocked_when_session_uses_it(self, world, adm):  # noqa: F811
        tid = j(adm, "post", "/api/admin/session-templates", TPL).json()["id"]
        lab.create_session(world["ia"], world["ca"].pk, "Uses", template_id=tid)
        coa = j(adm, "post", "/api/admin/coa-templates", {"name": "Alt"}).json()["id"]
        r = j(adm, "put", f"/api/admin/session-templates/{tid}", {**TPL, "coa_template_id": coa})
        assert r.status_code == 409
        # Other fields can still change.
        r = j(adm, "put", f"/api/admin/session-templates/{tid}", {**TPL, "name": "Renamed"})
        assert r.status_code == 200

    def test_cross_institution(self, world, adm):  # noqa: F811
        oadm, inst = other_inst_admin()
        foreign_coa = ledger.get_default_template(inst)
        # cannot attach another institution's CoA template
        r = j(
            adm,
            "post",
            "/api/admin/session-templates",
            {**TPL, "coa_template_id": str(foreign_coa.pk)},
        )
        assert r.status_code == 404
        tid = j(adm, "post", "/api/admin/session-templates", TPL).json()["id"]
        assert api(oadm).get("/api/admin/session-templates").json() == []
        assert j(api(oadm), "put", f"/api/admin/session-templates/{tid}", TPL).status_code == 404
        assert api(oadm).delete(f"/api/admin/session-templates/{tid}").status_code == 404
        r = j(
            adm,
            "put",
            f"/api/admin/session-templates/{tid}",
            {**TPL, "coa_template_id": str(foreign_coa.pk)},
        )
        assert r.status_code == 404


@pytest.mark.django_db
class TestReassignClass:
    def url(self, w):
        return f"/api/admin/classes/{w['ca'].pk}/instructor"

    def test_admin_reassigns_and_access_moves(self, world, adm):  # noqa: F811
        w = world
        r = j(adm, "put", self.url(w), {"instructor_id": str(w["ib"].pk)})
        assert r.status_code == 200, r.content
        assert r.json()["instructor_id"] == str(w["ib"].pk)
        assert r.json()["instructor_name"]
        row = AuditLog.objects.get(action="admin.class_instructor_changed")
        assert row.actor_id == w["admin"].pk and row.entity_id == str(w["ca"].pk)
        assert row.before["instructor_id"] == str(w["ia"].pk)
        assert row.after["instructor_id"] == str(w["ib"].pk)
        assert api(w["ia"]).get(f"/api/classes/{w['ca'].pk}").status_code in (403, 404)
        assert api(w["ib"]).get(f"/api/classes/{w['ca'].pk}").status_code == 200

    def test_non_admin_forbidden(self, world):  # noqa: F811
        w = world
        body = {"instructor_id": str(w["ib"].pk)}
        assert j(api(w["ia"]), "put", self.url(w), body).status_code == 403
        assert j(api(w["studs"][0]), "put", self.url(w), body).status_code == 403

    def test_cross_institution_404(self, world, adm):  # noqa: F811
        w = world
        oadm, inst = other_inst_admin()
        oi = acc.create_user("oins", "O Ins", PHONE, PlatformRole.INSTRUCTOR, institution=inst)
        assert j(api(oadm), "put", self.url(w), {"instructor_id": str(oi.pk)}).status_code == 404
        assert j(adm, "put", self.url(w), {"instructor_id": str(oi.pk)}).status_code == 404

    def test_invalid_targets_rejected(self, world, adm):  # noqa: F811
        w = world
        w["ib"].is_active = False
        w["ib"].save(update_fields=["is_active"])
        assert j(adm, "put", self.url(w), {"instructor_id": str(w["ib"].pk)}).status_code == 400
        stud = {"instructor_id": str(w["studs"][0].pk)}
        assert j(adm, "put", self.url(w), stud).status_code in (400, 404)
        same = {"instructor_id": str(w["ia"].pk)}
        assert j(adm, "put", self.url(w), same).status_code == 400
        assert not AuditLog.objects.filter(action="admin.class_instructor_changed").exists()

    def test_create_class_validates_instructor(self, world):  # noqa: F811
        w = world
        w["ib"].is_active = False
        w["ib"].save(update_fields=["is_active"])
        with pytest.raises(lab.ValidationFailed):
            lab.create_class(w["admin"], "N", "N1", instructor_id=w["ib"].pk)
        with pytest.raises(lab.ValidationFailed):
            lab.create_class(w["admin"], "N", "N2", instructor_id=w["studs"][0].pk)


@pytest.mark.django_db
class TestRenameStudent:
    def _rename(self, client, user, new):
        return j(client, "put", f"/api/admin/students/{user.pk}/username", {"username": new})

    def test_forbidden_for_non_admin(self, world):  # noqa: F811
        stu = world["studs"][1]
        for user in (world["ia"], world["studs"][0]):
            c = api(user)
            assert c.get("/api/admin/students").status_code == 403
            assert self._rename(c, stu, "newid1").status_code == 403
        stu.refresh_from_db()
        assert stu.username == "s1"
        assert not AuditLog.objects.filter(action="admin.student_renamed").exists()

    def test_other_institution_and_non_student_404(self, world, adm):  # noqa: F811
        oadm, _ = other_inst_admin()
        assert self._rename(api(oadm), world["studs"][0], "newid1").status_code == 404
        assert self._rename(adm, world["ia"], "newid1").status_code == 404
        assert api(oadm).get("/api/admin/students").json() == []

    def test_bad_format_400(self, world, adm):  # noqa: F811
        stu = world["studs"][0]
        for bad in ("ab", "", "  ", "-abc", "a b c", "x" * 31, "abéc"):
            assert self._rename(adm, stu, bad).status_code == 400, bad
        assert self._rename(adm, stu, "s0").status_code == 400  # same as current
        stu.refresh_from_db()
        assert stu.username == "s0"

    def test_duplicates_409(self, world, adm):  # noqa: F811
        stu = world["studs"][0]
        User.objects.filter(username="s1").update(username="stud1")
        assert self._rename(adm, stu, "stud1").status_code == 409
        assert self._rename(adm, stu, "STUD1").status_code == 409
        assert self._rename(adm, stu, "ADM").status_code == 409  # staff username too
        User.objects.filter(username="o1").update(username="other1")
        assert self._rename(adm, stu, "OTHER1").status_code == 409  # other instructor student
        stu.refresh_from_db()
        assert stu.username == "s0"

    def test_case_only_change_of_own_id_allowed(self, world, adm):  # noqa: F811
        stu = world["studs"][0]
        User.objects.filter(pk=stu.pk).update(username="stud0")
        stu.refresh_from_db()
        r = self._rename(adm, stu, "STUD0")
        assert r.status_code == 200
        assert r.json()["username"] == "STUD0"

    def test_rename_audit_login_and_history_kept(self, world, adm):  # noqa: F811
        from apps.lab.models import Enrollment, SessionMember
        from tests.test_auth import student_login
        from tests.test_lab import active_session

        stu = world["studs"][0]
        active_session(world)
        enr = Enrollment.objects.filter(user=stu).count()
        mem = SessionMember.objects.filter(user=stu).count()
        assert enr == 1 and mem == 1
        r = self._rename(adm, stu, " 2024.Stu-01 ")
        assert r.status_code == 200
        assert r.json()["username"] == "2024.Stu-01"
        row = AuditLog.objects.get(action="admin.student_renamed", entity_id=str(stu.pk))
        assert row.actor_id == world["admin"].id
        assert row.before == {"username": "s0"}
        assert row.after == {"username": "2024.Stu-01"}
        assert Enrollment.objects.filter(user_id=stu.pk).count() == enr
        assert SessionMember.objects.filter(user_id=stu.pk).count() == mem
        assert student_login("2024.Stu-01", "0111")[2].status_code == 200
        assert student_login("s0", "0111")[2].status_code != 200

    def test_list_search_and_scope(self, world, adm):  # noqa: F811
        names = [s["username"] for s in adm.get("/api/admin/students").json()]
        assert names == ["o1", "s0", "s1", "s2"]
        assert [s["username"] for s in adm.get("/api/admin/students?q=stud 1").json()] == ["s1"]
        assert [s["username"] for s in adm.get("/api/admin/students?q=O1").json()] == ["o1"]
        oadm, _ = other_inst_admin()
        assert api(oadm).get("/api/admin/students?q=s0").json() == []

    def test_instructor_patch_cannot_change_username(self, world):  # noqa: F811
        stu = world["studs"][0]
        c = api(world["ia"])
        r = j(
            c,
            "patch",
            f"/api/classes/{world['ca'].pk}/students/{stu.pk}",
            {"username": "hacked1", "full_name": "New Name"},
        )
        assert r.status_code == 200
        stu.refresh_from_db()
        assert stu.username == "s0"
        assert stu.full_name == "New Name"
