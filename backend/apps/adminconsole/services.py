"""Admin console business rules (1.12b): instructors, institution settings, CoA and
session templates. Every function takes the acting admin, scopes to the admin's
institution, runs atomically and writes an audit row."""

import re

from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower

from apps.accounts import services as accounts
from apps.accounts.models import Institution, PlatformRole, User
from apps.accounts.services import AccountsError
from apps.audit import services as audit
from apps.lab import services as lab
from apps.lab.models import Class, Session, SessionTemplate
from apps.ledger import services as ledger
from apps.ledger.coa import DEFAULT_COA_NAME
from apps.ledger.models import AccountType, CoaTemplate, CoaTemplateLine

STUDENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,29}$")
MAX_STUDENT_ROWS = 200
MAX_LOGO_BYTES = 1024 * 1024
LOGO_TYPES = {b"\xff\xd8\xff": "jpg", b"\x89PNG\r\n\x1a\n": "png"}


class ConsoleError(AccountsError):
    status = 400


class Forbidden(ConsoleError):
    status = 403


class NotFound(ConsoleError):
    status = 404


class Conflict(ConsoleError):
    status = 409


def require_admin(actor: User) -> None:
    if actor.platform_role != PlatformRole.ADMIN:
        raise Forbidden("Admin only")


def _audit(actor, action, entity, *, before=None, after=None, request=None):
    audit.record(
        action,
        actor=actor,
        actor_role=actor.platform_role,
        entity=entity,
        before=before,
        after=after,
        request=request,
    )


# --------------------------------------------------------------------------- instructors


def list_instructors(actor: User):
    require_admin(actor)
    return User.objects.filter(
        institution_id=actor.institution_id, platform_role=PlatformRole.INSTRUCTOR
    ).order_by("full_name", "username")


def _get_instructor(actor: User, user_id, *, lock=False) -> User:
    qs = User.objects.filter(
        pk=user_id, institution_id=actor.institution_id, platform_role=PlatformRole.INSTRUCTOR
    )
    if lock:
        qs = qs.select_for_update()
    user = qs.first()
    if user is None:
        raise NotFound("Instructor not found")
    return user


@transaction.atomic
def create_instructor(actor: User, username, full_name, phone, request=None) -> User:
    require_admin(actor)
    username = (username or "").strip()
    full_name = (full_name or "").strip()
    if not username:
        raise ConsoleError("Username is required")
    if not full_name:
        raise ConsoleError("Full name is required")
    try:
        with transaction.atomic():
            user = accounts.create_user(
                username,
                full_name,
                (phone or "").strip(),
                PlatformRole.INSTRUCTOR,
                institution=actor.institution,
            )
    except IntegrityError:
        raise Conflict("Username already exists") from None
    _audit(
        actor,
        "admin.instructor_created",
        ("user", user.pk),
        after={"username": user.username, "full_name": user.full_name},
        request=request,
    )
    return user


@transaction.atomic
def set_instructor_active(actor: User, user_id, active: bool, request=None) -> User:
    require_admin(actor)
    user = _get_instructor(actor, user_id, lock=True)
    if user.pk == actor.pk:
        raise ConsoleError("You cannot deactivate yourself")
    before = {"is_active": user.is_active}
    user.is_active = active
    user.save(update_fields=["is_active"])
    _audit(
        actor,
        "admin.instructor_reactivated" if active else "admin.instructor_deactivated",
        ("user", user.pk),
        before=before,
        after={"is_active": active},
        request=request,
    )
    return user


@transaction.atomic
def reset_instructor_password(actor: User, user_id, request=None) -> None:
    require_admin(actor)
    target = _get_instructor(actor, user_id)
    accounts.reset_password(actor, target)
    _audit(actor, "auth.password_reset", ("user", target.pk), request=request)


# ----------------------------------------------------------------------- students


def list_students(actor: User, q: str = ""):
    require_admin(actor)
    qs = User.objects.filter(
        institution_id=actor.institution_id, platform_role=PlatformRole.STUDENT
    )
    q = (q or "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(full_name__icontains=q) | Q(phone__icontains=q))
    return list(qs.order_by("username")[:MAX_STUDENT_ROWS])


@transaction.atomic
def rename_student(actor: User, user_id, new_username, request=None) -> User:
    require_admin(actor)
    user = (
        User.objects.select_for_update()
        .filter(pk=user_id, institution_id=actor.institution_id, platform_role=PlatformRole.STUDENT)
        .first()
    )
    if user is None:
        raise NotFound("Student not found")
    new = (new_username or "").strip()
    if not STUDENT_ID_RE.match(new):
        raise ConsoleError(
            "Student ID must be 3–30 letters, digits, '.', '_' or '-', "
            "starting with a letter or digit"
        )
    old = user.username
    if new == old:
        raise ConsoleError("The new Student ID is the same as the current one")
    # Serialize concurrent renames to case-variants of the same ID (the DB unique index
    # is case-sensitive), then check uniqueness across ALL users, case-insensitively;
    # never reveal which institution owns it.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"username:{new.lower()}"])
    if (
        User.objects.annotate(_ulower=Lower("username"))
        .filter(_ulower=new.lower())
        .exclude(pk=user.pk)
        .exists()
    ):
        raise Conflict("Student ID is not available")
    user.username = new
    try:
        with transaction.atomic():
            user.save(update_fields=["username"])
    except IntegrityError:
        raise Conflict("Student ID is not available") from None
    _audit(
        actor,
        "admin.student_renamed",
        ("user", user.pk),
        before={"username": old},
        after={"username": new},
        request=request,
    )
    return user


@transaction.atomic
def set_class_instructor(actor: User, class_id, instructor_id, request=None) -> Class:
    """Reassign a class to another active instructor of the same institution."""
    require_admin(actor)
    lab_class = (
        Class.objects.select_related("instructor")
        .select_for_update(of=("self",))
        .filter(pk=class_id, institution_id=actor.institution_id)
        .first()
    )
    if lab_class is None:
        raise NotFound("Class not found")
    target = User.objects.filter(
        pk=instructor_id,
        institution_id=actor.institution_id,
        platform_role=PlatformRole.INSTRUCTOR,
    ).first()
    if target is None:
        raise NotFound("Instructor not found")
    if not target.is_active:
        raise ConsoleError("Instructor is deactivated")
    if target.pk == lab_class.instructor_id:
        raise ConsoleError("Class already belongs to this instructor")
    before = {"instructor_id": str(lab_class.instructor_id)}
    lab_class.instructor = target
    lab_class.save(update_fields=["instructor"])
    _audit(
        actor,
        "admin.class_instructor_changed",
        ("class", lab_class.pk),
        before=before,
        after={"instructor_id": str(target.pk)},
        request=request,
    )
    return lab_class


# --------------------------------------------------------------------------- institution


def get_institution(actor: User) -> Institution:
    return Institution.objects.get(pk=actor.institution_id)


def _sniff_logo(upload) -> str:
    if upload.size > MAX_LOGO_BYTES:
        raise ConsoleError("Logo must be 1 MB or smaller")
    upload.seek(0)
    data = upload.read()
    upload.seek(0)
    for signature, ext in LOGO_TYPES.items():
        if data.startswith(signature):
            # Minimal structural check so a bare signature is not accepted.
            if ext == "png" and b"IHDR" not in data[:32]:
                break
            if ext == "jpg" and not data.rstrip(b"\x00").endswith(b"\xff\xd9"):
                break
            return ext
    raise ConsoleError("Logo must be a PNG or JPG image")


@transaction.atomic
def update_institution_name(actor: User, name, request=None) -> Institution:
    require_admin(actor)
    name = (name or "").strip()
    if not name:
        raise ConsoleError("Name is required")
    if len(name) > 200:
        raise ConsoleError("Name is too long")
    inst = Institution.objects.select_for_update().get(pk=actor.institution_id)
    if Institution.objects.filter(name__iexact=name).exclude(pk=inst.pk).exists():
        raise Conflict("Institution name already exists")
    before = {"name": inst.name}
    inst.name = name
    inst.save(update_fields=["name"])
    _audit(
        actor,
        "admin.institution_updated",
        ("institution", inst.pk),
        before=before,
        after={"name": name},
        request=request,
    )
    return inst


@transaction.atomic
def set_institution_logo(actor: User, upload, request=None) -> Institution:
    require_admin(actor)
    ext = _sniff_logo(upload)
    inst = Institution.objects.select_for_update().get(pk=actor.institution_id)
    had_logo = bool(inst.logo)
    old_name = inst.logo.name if had_logo else None
    inst.logo.save(f"{inst.pk}.{ext}", upload, save=False)
    inst.save(update_fields=["logo"])
    if old_name and old_name != inst.logo.name:
        storage = inst.logo.storage
        transaction.on_commit(lambda: storage.delete(old_name))
    _audit(
        actor,
        "admin.institution_logo_set",
        ("institution", inst.pk),
        before={"had_logo": had_logo},
        after={"size": upload.size, "type": ext},
        request=request,
    )
    return inst


@transaction.atomic
def delete_institution_logo(actor: User, request=None) -> Institution:
    require_admin(actor)
    inst = Institution.objects.select_for_update().get(pk=actor.institution_id)
    if not inst.logo:
        raise NotFound("No logo set")
    inst.logo.delete(save=False)
    inst.logo = ""
    inst.save(update_fields=["logo"])
    _audit(actor, "admin.institution_logo_removed", ("institution", inst.pk), request=request)
    return inst


# --------------------------------------------------------------------------- CoA templates


def _get_coa(actor: User, template_id, *, lock=False) -> CoaTemplate:
    qs = CoaTemplate.objects.filter(pk=template_id, institution_id=actor.institution_id)
    if lock:
        qs = qs.select_for_update()
    obj = qs.first()
    if obj is None:
        raise NotFound("CoA template not found")
    return obj


def list_coa_templates(actor: User):
    require_admin(actor)
    ledger.get_default_template(actor.institution)  # make sure the default exists
    return CoaTemplate.objects.filter(institution_id=actor.institution_id).annotate(
        line_count=Count("lines", distinct=True),
        session_template_count=Count("session_templates", distinct=True),
    )


def get_coa_template(actor: User, template_id) -> CoaTemplate:
    require_admin(actor)
    return _get_coa(actor, template_id)


def _clean_name(name, what="Name") -> str:
    name = (name or "").strip()
    if not name:
        raise ConsoleError(f"{what} is required")
    if len(name) > 200:
        raise ConsoleError(f"{what} is too long")
    return name


@transaction.atomic
def create_coa_template(actor: User, name, copy_from_id=None, request=None) -> CoaTemplate:
    require_admin(actor)
    name = _clean_name(name)
    source = (
        _get_coa(actor, copy_from_id)
        if copy_from_id is not None
        else ledger.get_default_template(actor.institution)
    )
    if CoaTemplate.objects.filter(institution_id=actor.institution_id, name__iexact=name).exists():
        raise Conflict("A CoA template with this name already exists")
    new = CoaTemplate.objects.create(institution_id=actor.institution_id, name=name)
    CoaTemplateLine.objects.bulk_create(
        CoaTemplateLine(
            template=new,
            code=ln.code,
            name=ln.name,
            type=ln.type,
            parent_code=ln.parent_code,
            postable=ln.postable,
            system_tag=ln.system_tag,
            is_active=ln.is_active,
            allow_negative=ln.allow_negative,
        )
        for ln in source.lines.all()
    )
    _audit(
        actor,
        "admin.coa_template_created",
        ("coa_template", new.pk),
        after={"name": name, "copied_from": str(source.pk)},
        request=request,
    )
    return new


@transaction.atomic
def delete_coa_template(actor: User, template_id, request=None) -> None:
    require_admin(actor)
    tpl = _get_coa(actor, template_id, lock=True)
    if tpl.name == DEFAULT_COA_NAME:
        raise Conflict("The default CoA template cannot be deleted")
    if SessionTemplate.objects.filter(coa_template=tpl).exists():
        raise Conflict("This CoA template is used by a session template")
    _audit(
        actor,
        "admin.coa_template_deleted",
        ("coa_template", tpl.pk),
        before={"name": tpl.name},
        request=request,
    )
    tpl.delete()


@transaction.atomic
def add_coa_line(
    actor: User, template_id, *, code, name, type, parent_code="", postable=False, request=None
) -> CoaTemplateLine:
    require_admin(actor)
    tpl = _get_coa(actor, template_id, lock=True)
    code = (code or "").strip()
    if not code or len(code) > 10:
        raise ConsoleError("Code is required (max 10 characters)")
    name = _clean_name(name)
    if type not in AccountType.values:
        raise ConsoleError("Invalid account type")
    if tpl.lines.filter(code=code).exists():
        raise Conflict("Account code already exists in this template")
    parent_code = (parent_code or "").strip()
    if parent_code:
        parent = tpl.lines.filter(code=parent_code).first()
        if parent is None:
            raise ConsoleError("Parent code does not exist in this template")
        if parent.postable:
            raise ConsoleError("A postable account cannot be a parent")
        if parent.type != type:
            raise ConsoleError("Account type must match the parent's type")
    line = CoaTemplateLine.objects.create(
        template=tpl,
        code=code,
        name=name,
        type=type,
        parent_code=parent_code,
        postable=bool(postable),
        system_tag="",
        is_active=True,
        allow_negative=False,
    )
    _audit(
        actor,
        "admin.coa_line_added",
        ("coa_template_line", line.pk),
        after={"template_id": str(tpl.pk), "code": code, "name": name, "type": type},
        request=request,
    )
    return line


@transaction.atomic
def update_coa_line(
    actor: User, template_id, line_id, *, name=None, is_active=None, request=None
) -> CoaTemplateLine:
    require_admin(actor)
    tpl = _get_coa(actor, template_id, lock=True)
    line = tpl.lines.select_for_update().filter(pk=line_id).first()
    if line is None:
        raise NotFound("Line not found")
    if line.system_tag:
        raise Conflict("System accounts cannot be renamed or deactivated")
    before = {"name": line.name, "is_active": line.is_active}
    if name is not None:
        line.name = _clean_name(name)
    if is_active is not None:
        line.is_active = bool(is_active)
    line.save(update_fields=["name", "is_active", "updated_at"])
    _audit(
        actor,
        "admin.coa_line_updated",
        ("coa_template_line", line.pk),
        before=before,
        after={"name": line.name, "is_active": line.is_active, "template_id": str(tpl.pk)},
        request=request,
    )
    return line


# --------------------------------------------------------------------------- session templates


def list_session_templates(actor: User):
    require_admin(actor)
    return SessionTemplate.objects.filter(
        institution_id=actor.institution_id, lab_class__isnull=True
    )


def _get_session_template(actor: User, template_id, *, lock=False) -> SessionTemplate:
    qs = SessionTemplate.objects.filter(
        pk=template_id, institution_id=actor.institution_id, lab_class__isnull=True
    )
    if lock:
        qs = qs.select_for_update()
    obj = qs.first()
    if obj is None:
        raise NotFound("Template not found")
    return obj


@transaction.atomic
def create_session_template(actor: User, **data) -> SessionTemplate:
    require_admin(actor)
    data.pop("class_id", None)  # console templates are always institution-wide
    return lab.create_template(actor, **data)


@transaction.atomic
def update_session_template(
    actor: User,
    template_id,
    *,
    name,
    kind,
    structure,
    allowed_roles,
    default_visibility,
    learning_panel=True,
    seed_profile="",
    opening_capital_usd=lab.DEFAULT_CAPITAL_USD,
    opening_capital_sos=lab.DEFAULT_CAPITAL_SOS,
    coa_template_id=None,
    request=None,
) -> SessionTemplate:
    require_admin(actor)
    tpl = _get_session_template(actor, template_id, lock=True)
    name = (name or "").strip()
    if not name:
        raise ConsoleError("Name is required")
    kind, structure, visibility, panel = lab._normalize_settings(
        kind, structure, default_visibility, learning_panel
    )
    before = {"name": tpl.name, "kind": tpl.kind, "coa_template_id": str(tpl.coa_template_id)}
    tpl.name = name
    tpl.kind = kind
    tpl.structure = structure
    tpl.allowed_roles = lab._check_roles(allowed_roles)
    tpl.default_visibility = visibility
    tpl.learning_panel = panel
    tpl.seed_profile = (seed_profile or "").strip()
    tpl.opening_capital_usd = lab._check_capital(opening_capital_usd, "Opening capital USD")
    tpl.opening_capital_sos = lab._check_capital(opening_capital_sos, "Opening capital SOS")
    new_coa = lab._coa_template_or_none(actor, coa_template_id)
    if new_coa != tpl.coa_template and Session.objects.filter(template=tpl).exists():
        # Banks provisioned later in those sessions would get a different chart.
        raise Conflict("Chart of accounts cannot change on a template used by a session")
    tpl.coa_template = new_coa
    tpl.save()
    _audit(
        actor,
        "admin.session_template_updated",
        ("session_template", tpl.pk),
        before=before,
        after={"name": name, "kind": kind, "coa_template_id": str(tpl.coa_template_id)},
        request=request,
    )
    return tpl


@transaction.atomic
def delete_session_template(actor: User, template_id, request=None) -> None:
    require_admin(actor)
    tpl = _get_session_template(actor, template_id, lock=True)
    if Session.objects.filter(template=tpl).exists():
        raise Conflict("This template is used by a session")
    _audit(
        actor,
        "admin.session_template_deleted",
        ("session_template", tpl.pk),
        before={"name": tpl.name},
        request=request,
    )
    tpl.delete()
