# ruff: noqa: F811
"""1.15f Edit a session after creating it: editability by status, locking, exam rules."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts import services as acc
from apps.accounts.models import Institution, PlatformRole
from apps.audit.models import AuditLog
from apps.exams.models import Exam
from apps.lab import services as lab
from apps.lab.models import RoleAssignment, SessionMember
from tests.test_lab import _reset_rbac, active_session, api, j, world  # noqa: F401

D = Decimal
PHONE = "+252 61 555 1234"
ALL_ROLES = ["teller", "cso", "manager", "vault_custodian", "accountant"]


def draft(world, name="Draft", **kw):
    return lab.create_session(world["ia"], world["ca"].pk, name, **kw)


def patch(user, session, body):
    return j(api(user), "patch", f"/api/sessions/{session.pk}", body)


def updated_rows(session):
    return AuditLog.objects.filter(action="lab.session_updated", session_id=session.pk)


def mk_template(user, name="T", **kw):
    args = {
        "name": name,
        "kind": "practice",
        "structure": "single_bank",
        "allowed_roles": ["teller"],
        "default_visibility": "own",
    }
    args.update(kw)
    return lab.create_template(user, **args)


@pytest.mark.django_db
class TestDraft:
    def test_full_edit_and_audit_only_changed_keys(self, world):
        s = draft(world)
        tpl = mk_template(world["admin"])
        r = patch(
            world["ia"],
            s,
            {
                "name": "  Renamed ",
                "kind": "practice",
                "structure": "per_group",
                "allowed_roles": ["teller", "cso"],
                "default_visibility": "all",
                "learning_panel": False,
                "seed_profile": " seed1 ",
                "opening_capital_usd": "500.50",
                "opening_capital_sos": "7000",
                "template_id": str(tpl.pk),
            },
        )
        assert r.status_code == 200, r.content
        body = r.json()
        assert body["name"] == "Renamed"
        assert body["structure"] == "per_group"
        assert body["allowed_roles"] == ["teller", "cso"]
        assert body["seed_profile"] == "seed1"
        assert body["template_id"] == str(tpl.pk)
        assert D(body["opening_capital_usd"]) == D("500.50")
        assert body["locked_fields"] == {}
        row = updated_rows(s).get()
        assert row.before["name"] == "Draft" and row.after["name"] == "Renamed"
        assert "kind" not in row.after  # unchanged value is not logged
        assert row.after["template_id"] == str(tpl.pk) and row.before["template_id"] is None
        assert row.after["opening_capital_usd"] == "500.50"

    def test_noop_writes_no_audit(self, world):
        s = draft(world)
        r = patch(world["ia"], s, {"name": s.name, "kind": s.kind, "learning_panel": True})
        assert r.status_code == 200
        assert patch(world["ia"], s, {}).status_code == 200
        assert not updated_rows(s).exists()

    def test_validation(self, world):
        s = draft(world)
        for body in (
            {"name": "  "},
            {"allowed_roles": []},
            {"allowed_roles": ["king"]},
            {"seed_profile": "x" * 81},
            {"opening_capital_usd": "-1"},
            {"opening_capital_sos": "1.234"},
            {"kind": "bogus"},
        ):
            assert patch(world["ia"], s, body).status_code == 400, body
        assert patch(world["ia"], s, {"template_id": "x"}).status_code == 422

    def test_clear_template(self, world):
        tpl = mk_template(world["admin"])
        s = draft(world, template_id=tpl.pk, allowed_roles=ALL_ROLES)
        assert s.template_id == tpl.pk
        r = patch(world["ia"], s, {"clear_template": True})
        assert r.status_code == 200 and r.json()["template_id"] is None
        row = updated_rows(s).get()
        assert row.before == {"template_id": str(tpl.pk)} and row.after == {"template_id": None}
        # linking a template only changes the link, it does not copy its values
        r = patch(world["ia"], s, {"template_id": str(tpl.pk)})
        assert r.status_code == 200 and r.json()["allowed_roles"] == ALL_ROLES
        both = patch(world["ia"], s, {"template_id": str(tpl.pk), "clear_template": True})
        assert both.status_code == 400

    def test_template_scoping(self, world):
        s = draft(world)
        other_class_tpl = mk_template(world["ib"], "B", class_id=world["cb"].pk)
        assert patch(world["ia"], s, {"template_id": str(other_class_tpl.pk)}).status_code == 404
        inst = Institution.objects.create(name="Other Uni")
        oadm = acc.create_user("oadm", "O", PHONE, PlatformRole.ADMIN, institution=inst)
        foreign = mk_template(oadm, "F")
        assert patch(world["ia"], s, {"template_id": str(foreign.pk)}).status_code == 404
        own_class = mk_template(world["ia"], "A", class_id=world["ca"].pk)
        assert patch(world["ia"], s, {"template_id": str(own_class.pk)}).status_code == 200


@pytest.mark.django_db
class TestActive:
    def test_editable_fields(self, world):
        s = active_session(world)
        r = patch(
            world["ia"],
            s,
            {
                "name": "New name",
                "allowed_roles": ALL_ROLES,
                "default_visibility": "all",
                "learning_panel": False,
            },
        )
        assert r.status_code == 200, r.content
        b = r.json()
        assert b["name"] == "New name" and b["default_visibility"] == "all"
        assert b["learning_panel"] is False
        assert set(b["locked_fields"]) >= {"kind", "structure", "opening_capital_usd"}
        row = updated_rows(s).get()
        assert set(row.after) <= {"name", "allowed_roles", "default_visibility", "learning_panel"}
        assert "name" in row.after

    @pytest.mark.parametrize(
        "body",
        [
            {"kind": "exam"},
            {"structure": "per_group"},
            {"opening_capital_usd": "1.00"},
            {"opening_capital_sos": "1.00"},
            {"seed_profile": "other"},
        ],
    )
    def test_locked_change_is_409(self, world, body):
        s = active_session(world)
        r = patch(world["ia"], s, body)
        assert r.status_code == 409, r.content
        assert next(iter(body)) in r.json()["detail"]
        assert not updated_rows(s).exists()

    def test_template_change_is_409(self, world):
        s = active_session(world)
        tpl = mk_template(world["admin"])
        assert patch(world["ia"], s, {"template_id": str(tpl.pk)}).status_code == 409

    def test_template_clear_is_409_when_linked(self, world):
        tpl = mk_template(world["admin"])
        s = active_session(world, template_id=tpl.pk)
        assert patch(world["ia"], s, {"clear_template": True}).status_code == 409
        # sending the same template back is fine
        assert patch(world["ia"], s, {"template_id": str(tpl.pk)}).status_code == 200

    def test_same_value_locked_fields_accepted(self, world):
        s = active_session(world)
        r = patch(
            world["ia"],
            s,
            {
                "name": "Renamed",
                "kind": s.kind,
                "structure": s.structure,
                "opening_capital_usd": str(s.opening_capital_usd),
                "opening_capital_sos": str(s.opening_capital_sos),
                "seed_profile": s.seed_profile,
                "clear_template": True,
            },
        )
        assert r.status_code == 200, r.content
        assert set(updated_rows(s).get().after) == {"name"}

    def test_equal_capital_in_other_format_accepted(self, world):
        s = active_session(world)
        cap = s.opening_capital_usd.normalize()  # e.g. 1E+6 / "1000000" style
        r = patch(world["ia"], s, {"opening_capital_usd": f"{cap:f}"})
        assert r.status_code == 200, r.content
        assert not updated_rows(s).exists()

    def test_rejected_patch_leaves_session_unchanged(self, world):
        s = active_session(world)
        before = lab._session_dict(s)
        r = patch(world["ia"], s, {"name": "New", "opening_capital_usd": "1.00"})
        assert r.status_code == 409
        s.refresh_from_db()
        assert lab._session_dict(s) == before

    def test_cannot_remove_assigned_role(self, world):
        s = active_session(world)
        member = SessionMember.objects.get(session=s, user=world["studs"][0])
        lab.assign_role(world["ia"], s.pk, member.pk, "teller")
        r = patch(world["ia"], s, {"allowed_roles": ["cso"]})
        assert r.status_code == 409 and "teller" in r.json()["detail"]
        assert patch(world["ia"], s, {"allowed_roles": ["teller", "cso"]}).status_code == 200
        # an ended assignment no longer blocks
        RoleAssignment.objects.filter(session_member=member).update(active_to=timezone.now())
        assert patch(world["ia"], s, {"allowed_roles": ["cso"]}).status_code == 200

    def test_no_ledger_change(self, world):
        from apps.ledger.models import JournalEntry

        s = active_session(world)
        n = JournalEntry.objects.count()
        patch(world["ia"], s, {"name": "Z"})
        assert JournalEntry.objects.count() == n


@pytest.mark.django_db
class TestArchived:
    def test_read_only(self, world):
        s = active_session(world)
        lab.archive_session(world["ia"], s.pk)
        for body in ({"name": "x"}, {"learning_panel": False}, {"allowed_roles": ["teller"]}, {}):
            r = patch(world["ia"], s, body)
            assert r.status_code == 409 and "read-only" in r.json()["detail"]
        assert not updated_rows(s).exists()


@pytest.mark.django_db
class TestExam:
    def test_switch_to_exam_normalizes(self, world):
        s = draft(world, structure="per_group", default_visibility="all", learning_panel=True)
        r = patch(world["ia"], s, {"kind": "exam"})
        assert r.status_code == 200, r.content
        b = r.json()
        assert (b["structure"], b["default_visibility"], b["learning_panel"]) == (
            "single_bank",
            "own",
            False,
        )
        after = updated_rows(s).get().after
        assert after["kind"] == "exam" and after["structure"] == "single_bank"
        assert set(b["locked_fields"]) == {"structure", "default_visibility", "learning_panel"}

    def test_explicit_conflicting_values_rejected(self, world):
        s = draft(world, kind="exam")
        for body in (
            {"learning_panel": True},
            {"default_visibility": "all"},
            {"structure": "per_group"},
        ):
            assert patch(world["ia"], s, body).status_code == 400, body
        # the forced values themselves are fine
        ok = {"learning_panel": False, "default_visibility": "own", "structure": "single_bank"}
        assert patch(world["ia"], s, ok).status_code == 200
        assert not updated_rows(s).exists()

    def test_active_exam_rejects_panel_on(self, world):
        s = active_session(world, kind="exam")
        assert patch(world["ia"], s, {"learning_panel": True}).status_code == 400
        assert patch(world["ia"], s, {"learning_panel": False, "name": "E"}).status_code == 200

    def test_exam_to_practice_blocked_when_exam_exists(self, world):
        s = draft(world, kind="exam")
        now = timezone.now()
        Exam.objects.create(
            session=s, starts_at=now, ends_at=now + timedelta(hours=1), duration_minutes=30
        )
        r = patch(world["ia"], s, {"kind": "practice"})
        assert r.status_code == 409 and "exam set up" in r.json()["detail"]
        s.refresh_from_db()
        assert s.kind == "exam"

    def test_exam_to_practice_ok_without_exam(self, world):
        s = draft(world, kind="exam")
        assert patch(world["ia"], s, {"kind": "practice"}).status_code == 200


@pytest.mark.django_db
class TestAccess:
    def test_other_instructor_same_institution_404(self, world):
        s = draft(world)
        assert patch(world["ib"], s, {"name": "hack"}).status_code == 404

    def test_other_class_404_on_active_and_archived(self, world):
        s = active_session(world)
        assert patch(world["ib"], s, {"name": "hack"}).status_code == 404
        lab.archive_session(world["ia"], s.pk)
        assert patch(world["ib"], s, {"name": "hack"}).status_code == 404
        s.refresh_from_db()
        assert s.name == "Lecture 1"

    def test_audit_actor(self, world):
        s = draft(world)
        assert patch(world["ia"], s, {"name": "Audited"}).status_code == 200
        assert updated_rows(s).get().actor_id == world["ia"].pk

    def test_admin_can_edit(self, world):
        s = draft(world)
        assert patch(world["admin"], s, {"name": "By admin"}).status_code == 200

    def test_other_institution_404(self, world):
        s = draft(world)
        inst = Institution.objects.create(name="Other Uni")
        for i, role in enumerate((PlatformRole.ADMIN, PlatformRole.INSTRUCTOR)):
            u = acc.create_user(f"x{i}", "X", PHONE, role, institution=inst)
            u.must_change_password = False
            u.save(update_fields=["must_change_password"])
            assert patch(u, s, {"name": "hack"}).status_code == 404
        s.refresh_from_db()
        assert s.name == "Draft"

    def test_student_403(self, world):
        s = draft(world)
        assert patch(world["studs"][0], s, {"name": "hack"}).status_code == 403
        with pytest.raises(lab.PermissionDenied):
            lab.update_session(world["studs"][0], s.pk, name="x")


@pytest.mark.django_db
class TestLockedFields:
    def test_shape_per_status(self, world):
        s = draft(world)
        c = api(world["ia"])
        assert c.get(f"/api/sessions/{s.pk}").json()["locked_fields"] == {}
        s2 = active_session(world, "Live")
        lf = c.get(f"/api/sessions/{s2.pk}").json()["locked_fields"]
        assert lf["kind"] == lf["structure"] == "Banks already exist"
        assert lf["opening_capital_usd"] == "Opening capital is already posted to the ledger"
        assert lf["template_id"] == lf["seed_profile"] == "Fixed once the session is open"
        assert "name" not in lf and "allowed_roles" not in lf
        lab.archive_session(world["ia"], s2.pk)
        lf = c.get(f"/api/sessions/{s2.pk}").json()["locked_fields"]
        assert set(lf) == set(lab.SESSION_FIELDS)
        assert set(lf.values()) == {"Archived sessions are read-only"}

    def test_cross_session_isolation(self, world):
        a, b = draft(world, "A"), draft(world, "B")
        patch(world["ia"], a, {"name": "A2"})
        b.refresh_from_db()
        assert b.name == "B"
        assert updated_rows(b).count() == 0
