"""Lab business rules: classes, students, templates, sessions, banks, members, roles.

Every write runs in one transaction, checks that the actor may act on the class/session,
rejects archived sessions and writes an audit row.
"""

import csv
import io
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts import services as accounts
from apps.accounts.models import PlatformRole, User
from apps.audit import services as audit
from apps.banking.models import BusinessDay
from apps.banking.provisioning import provision_bank_cash
from apps.ledger import services as ledger
from apps.rbac import services as rbac
from apps.rbac.models import BankRole, Permission

from .models import (
    Bank,
    Class,
    Enrollment,
    PermissionOverride,
    RoleAssignment,
    Session,
    SessionKind,
    SessionMember,
    SessionStatus,
    SessionStructure,
    SessionTemplate,
    Visibility,
)

MAX_GROUPS = 50
MAX_CSV_ROWS = 500
MAX_CSV_BYTES = 1_000_000
CSV_COLUMNS = ("username", "full_name", "phone")
USERNAME_UNAVAILABLE = "Username is not available"


class LabError(Exception):
    """Domain error; `status` is the HTTP status the API maps it to."""

    status = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationFailed(LabError):
    status = 400


class PermissionDenied(LabError):
    status = 403


class NotFound(LabError):
    status = 404


class Conflict(LabError):
    status = 409


@contextmanager
def _conflict_guard():
    """Run a create in a savepoint; a concurrent unique-constraint hit becomes a 409."""
    try:
        with transaction.atomic():
            yield
    except IntegrityError:
        raise Conflict("Conflicting concurrent change, please retry") from None


# --------------------------------------------------------------------------- access


def _require_staff(actor: User) -> None:
    if actor.platform_role not in (PlatformRole.ADMIN, PlatformRole.INSTRUCTOR):
        raise PermissionDenied("Not allowed")


def _can_manage(actor: User, lab_class: Class) -> bool:
    if actor.institution_id != lab_class.institution_id:
        return False
    if actor.platform_role == PlatformRole.ADMIN:
        return True
    return actor.platform_role == PlatformRole.INSTRUCTOR and lab_class.instructor_id == actor.id


def get_class(actor: User, class_id, *, lock: bool = False) -> Class:
    """Class the actor may manage; foreign classes look like they do not exist."""
    _require_staff(actor)
    qs = Class.objects.select_related("instructor")
    if lock:
        qs = qs.select_for_update(of=("self",))
    lab_class = qs.filter(pk=class_id).first()
    if lab_class is None or not _can_manage(actor, lab_class):
        raise NotFound("Class not found")
    return lab_class


def get_session(actor: User, session_id, *, lock: bool = False) -> Session:
    """Session (of a class the actor may manage) for reading."""
    _require_staff(actor)
    qs = Session.objects.select_related("lab_class", "template")
    if lock:
        qs = qs.select_for_update(of=("self",))
    session = qs.filter(pk=session_id).first()
    if session is None or not _can_manage(actor, session.lab_class):
        raise NotFound("Session not found")
    return session


def get_writable_session(actor: User, session_id) -> Session:
    """Locked session for writing; archived sessions are read-only."""
    session = get_session(actor, session_id, lock=True)
    if session.status == SessionStatus.ARCHIVED:
        raise Conflict("Session is archived (read-only)")
    return session


def _audit(actor, action, entity, *, before=None, after=None, session=None, bank=None):
    audit.record(
        action,
        actor=actor,
        actor_role=actor.platform_role,
        entity=entity,
        before=before,
        after=after,
        session_id=session.pk if session is not None else None,
        bank_id=bank.pk if bank is not None else None,
    )


# --------------------------------------------------------------------------- serializers


def _class_dict(c: Class) -> dict:
    return {"name": c.name, "code": c.code, "instructor_id": str(c.instructor_id)}


def _session_dict(s: Session) -> dict:
    return {
        "name": s.name,
        "kind": s.kind,
        "structure": s.structure,
        "status": s.status,
        "allowed_roles": s.allowed_roles,
        "default_visibility": s.default_visibility,
        "learning_panel": s.learning_panel,
        "seed_profile": s.seed_profile,
        "opening_capital_usd": str(s.opening_capital_usd),
        "opening_capital_sos": str(s.opening_capital_sos),
    }


# --------------------------------------------------------------------------- classes


def list_classes(actor: User):
    _require_staff(actor)
    qs = Class.objects.select_related("instructor").filter(institution_id=actor.institution_id)
    if actor.platform_role == PlatformRole.INSTRUCTOR:
        qs = qs.filter(instructor=actor)
    return qs


@transaction.atomic
def create_class(actor: User, name: str, code: str, instructor_id=None) -> Class:
    _require_staff(actor)
    name, code = (name or "").strip(), (code or "").strip()
    if not name or not code:
        raise ValidationFailed("Name and code are required")
    if actor.platform_role == PlatformRole.INSTRUCTOR:
        if instructor_id not in (None, actor.id):
            raise PermissionDenied("Instructors can only create classes for themselves")
        instructor = actor
    else:
        if instructor_id is None:
            raise ValidationFailed("instructor_id is required")
        instructor = User.objects.filter(
            pk=instructor_id,
            institution_id=actor.institution_id,
            platform_role=PlatformRole.INSTRUCTOR,
            is_active=True,
        ).first()
        if instructor is None:
            raise ValidationFailed("Instructor not found")
    if Class.objects.filter(institution_id=actor.institution_id, code=code).exists():
        raise ValidationFailed("A class with this code already exists")
    with _conflict_guard():
        lab_class = Class.objects.create(
            institution_id=actor.institution_id, instructor=instructor, name=name, code=code
        )
    _audit(actor, "lab.class_created", ("class", lab_class.pk), after=_class_dict(lab_class))
    return lab_class


# --------------------------------------------------------------------------- students


def list_students(actor: User, class_id):
    lab_class = get_class(actor, class_id)
    return (
        Enrollment.objects.select_related("user")
        .filter(lab_class=lab_class)
        .order_by("user__username")
    )


def _enroll(actor: User, lab_class: Class, user: User) -> Enrollment:
    enrollment = Enrollment.objects.create(lab_class=lab_class, user=user)
    _audit(
        actor,
        "lab.student_enrolled",
        ("enrollment", enrollment.pk),
        after={"class_id": str(lab_class.pk), "user_id": str(user.pk), "username": user.username},
    )
    return enrollment


def _add_student(actor, lab_class, username, full_name, phone) -> tuple[User, bool]:
    """Create-or-reuse the user and enroll. Returns (user, created)."""
    username = (username or "").strip()
    if not username:
        raise ValidationFailed("username is required")
    user = User.objects.filter(username=username).first()
    created = False
    if user is not None and user.institution_id != lab_class.institution_id:
        raise ValidationFailed(USERNAME_UNAVAILABLE)  # never reveal other institutions
    with _conflict_guard():
        if user is None:
            if not (full_name or "").strip():
                raise ValidationFailed("full_name is required for a new student")
            try:
                user = accounts.create_user(
                    username,
                    full_name.strip(),
                    (phone or "").strip(),
                    PlatformRole.STUDENT,
                    institution=lab_class.institution,
                )
            except accounts.AccountsError as exc:
                raise ValidationFailed(exc.message) from None
            created = True
            _audit(
                actor,
                "lab.student_created",
                ("user", user.pk),
                after={"username": user.username, "full_name": user.full_name},
            )
        else:
            if user.platform_role != PlatformRole.STUDENT:
                raise ValidationFailed("This username belongs to a non-student account")
        if Enrollment.objects.filter(lab_class=lab_class, user=user).exists():
            raise ValidationFailed("Student is already enrolled in this class")
        _enroll(actor, lab_class, user)
    return user, created


@transaction.atomic
def add_student(actor: User, class_id, username, full_name="", phone="") -> tuple[User, bool]:
    lab_class = get_class(actor, class_id, lock=True)
    return _add_student(actor, lab_class, username, full_name, phone)


@transaction.atomic
def update_student(
    actor: User, class_id, user_id, *, full_name=None, phone=None, is_active=None
) -> User:
    """Edit a student account. Instructors: only when every class of the student is theirs."""
    lab_class = get_class(actor, class_id)
    if not Enrollment.objects.filter(lab_class=lab_class, user_id=user_id).exists():
        raise NotFound("Student not found")
    user = User.objects.select_for_update().get(pk=user_id)
    if user.platform_role != PlatformRole.STUDENT:
        raise NotFound("Student not found")
    if actor.platform_role != PlatformRole.ADMIN and (
        Enrollment.objects.filter(user=user).exclude(lab_class__instructor=actor).exists()
    ):
        raise PermissionDenied("This student is also enrolled in another instructor's class")
    before = {"full_name": user.full_name, "phone": user.phone, "is_active": user.is_active}
    if full_name is not None:
        if not full_name.strip():
            raise ValidationFailed("full_name cannot be empty")
        user.full_name = full_name.strip()
    if phone is not None:
        phone = phone.strip()
        try:
            accounts.validate_student_phone(phone)  # same rule as creation (login credential)
        except accounts.AccountsError as exc:
            raise ValidationFailed(exc.message) from None
        user.phone = phone
    if is_active is not None:
        user.is_active = is_active
    user.save(update_fields=["full_name", "phone", "is_active"])
    after = {"full_name": user.full_name, "phone": user.phone, "is_active": user.is_active}
    _audit(actor, "lab.student_updated", ("user", user.pk), before=before, after=after)
    return user


@dataclass
class CsvRow:
    line: int
    username: str
    full_name: str
    phone: str
    action: str = ""  # create | enroll | error
    error: str = ""


@dataclass
class CsvResult:
    rows: list[CsvRow] = field(default_factory=list)
    fatal: str = ""

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.rows if r.action != "error")

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.rows if r.action == "error")


def _validate_csv(lab_class: Class, text: str) -> CsvResult:
    result = CsvResult()
    if len(text.encode("utf-8")) > MAX_CSV_BYTES:
        result.fatal = "File is too large"
        return result
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    header = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in CSV_COLUMNS if c not in header]
    if missing:
        result.fatal = "Missing column(s): " + ", ".join(missing)
        return result
    reader.fieldnames = header
    seen: set[str] = set()
    for line, raw in enumerate(reader, start=2):
        if len(result.rows) >= MAX_CSV_ROWS:
            result.fatal = f"Too many rows (maximum {MAX_CSV_ROWS})"
            result.rows = []
            return result
        row = CsvRow(
            line=line,
            username=(raw.get("username") or "").strip(),
            full_name=(raw.get("full_name") or "").strip(),
            phone=(raw.get("phone") or "").strip(),
        )
        result.rows.append(row)
        if not any((row.username, row.full_name, row.phone)):
            result.rows.pop()
            continue
        if not row.username:
            row.action, row.error = "error", "username is required"
        elif row.username.lower() in seen:
            row.action, row.error = "error", "duplicate username in file"
        else:
            seen.add(row.username.lower())
            user = User.objects.filter(username=row.username).first()
            if user is None:
                if not row.full_name:
                    row.action, row.error = "error", "full_name is required"
                elif len(re.sub(r"\D", "", row.phone)) < 4:
                    row.action, row.error = "error", "phone must contain at least 4 digits"
                else:
                    row.action = "create"
            elif user.institution_id != lab_class.institution_id:
                row.action, row.error = "error", USERNAME_UNAVAILABLE
            elif user.platform_role != PlatformRole.STUDENT:
                row.action, row.error = "error", "username belongs to a non-student account"
            elif Enrollment.objects.filter(lab_class=lab_class, user=user).exists():
                row.action, row.error = "error", "already enrolled in this class"
            else:
                row.action = "enroll"
    return result


def preview_students_csv(actor: User, class_id, text: str) -> CsvResult:
    lab_class = get_class(actor, class_id)
    return _validate_csv(lab_class, text)


@transaction.atomic
def confirm_students_csv(actor: User, class_id, text: str) -> CsvResult:
    """Re-validate server-side, import the valid rows, report the rejected ones."""
    lab_class = get_class(actor, class_id, lock=True)
    result = _validate_csv(lab_class, text)
    if result.fatal:
        raise ValidationFailed(result.fatal)
    imported = 0
    for row in result.rows:
        if row.action == "error":
            continue
        _add_student(actor, lab_class, row.username, row.full_name, row.phone)
        imported += 1
    _audit(
        actor,
        "lab.students_imported",
        ("class", lab_class.pk),
        after={"imported": imported, "rejected": result.error_count},
    )
    return result


# --------------------------------------------------------------------------- templates


def _check_roles(roles) -> list[str]:
    roles = list(dict.fromkeys(roles or []))
    if not roles:
        raise ValidationFailed("At least one allowed role is required")
    if any(r not in BankRole.values for r in roles):
        raise ValidationFailed("Invalid bank role")
    return roles


def _normalize_settings(kind, structure, visibility, learning_panel) -> tuple[str, str, str, bool]:
    if kind not in SessionKind.values:
        raise ValidationFailed("Invalid session kind")
    if structure not in SessionStructure.values:
        raise ValidationFailed("Invalid session structure")
    if visibility not in Visibility.values:
        raise ValidationFailed("Invalid visibility")
    if kind == SessionKind.EXAM:
        # Exams: one bank, own-work visibility, no learning panel (erd section 7).
        structure, visibility, learning_panel = SessionStructure.SINGLE_BANK, Visibility.OWN, False
    return kind, structure, visibility, bool(learning_panel)


DEFAULT_CAPITAL_USD = Decimal("1000000.00")
DEFAULT_CAPITAL_SOS = Decimal("5000000000.00")


def _check_capital(value, what: str) -> Decimal:
    """Opening capital: a Decimal >= 0 with at most 2 decimals (fits NUMERIC(18,2))."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, int, str)):
        raise ValidationFailed(f"{what} must be an amount")
    try:
        amount = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValidationFailed(f"{what} is not a valid amount") from None
    if not amount.is_finite() or amount.as_tuple().exponent < -2:
        raise ValidationFailed(f"{what} must have at most 2 decimal places")
    if amount < 0 or amount >= Decimal("10") ** 16:
        raise ValidationFailed(f"{what} must be between 0 and 9999999999999999.99")
    return amount.quantize(Decimal("0.01"))


def list_templates(actor: User, class_id=None):
    _require_staff(actor)
    qs = SessionTemplate.objects.filter(institution_id=actor.institution_id)
    if class_id is not None:
        get_class(actor, class_id)
        return qs.filter(Q(lab_class_id=class_id) | Q(lab_class__isnull=True))
    if actor.platform_role == PlatformRole.INSTRUCTOR:
        return qs.filter(Q(lab_class__instructor=actor) | Q(lab_class__isnull=True))
    return qs


@transaction.atomic
def create_template(
    actor: User,
    *,
    name,
    kind,
    structure,
    allowed_roles,
    default_visibility,
    learning_panel=True,
    seed_profile="",
    class_id=None,
    opening_capital_usd=DEFAULT_CAPITAL_USD,
    opening_capital_sos=DEFAULT_CAPITAL_SOS,
) -> SessionTemplate:
    _require_staff(actor)
    lab_class = None
    if class_id is not None:
        lab_class = get_class(actor, class_id)
    elif actor.platform_role != PlatformRole.ADMIN:
        raise PermissionDenied("Only an admin can create institution-wide templates")
    name = (name or "").strip()
    if not name:
        raise ValidationFailed("Name is required")
    kind, structure, visibility, panel = _normalize_settings(
        kind, structure, default_visibility, learning_panel
    )
    template = SessionTemplate.objects.create(
        institution_id=actor.institution_id,
        lab_class=lab_class,
        name=name,
        kind=kind,
        structure=structure,
        allowed_roles=_check_roles(allowed_roles),
        default_visibility=visibility,
        learning_panel=panel,
        seed_profile=(seed_profile or "").strip(),
        opening_capital_usd=_check_capital(opening_capital_usd, "Opening capital USD"),
        opening_capital_sos=_check_capital(opening_capital_sos, "Opening capital SOS"),
        created_by=actor,
    )
    _audit(
        actor,
        "lab.template_created",
        ("session_template", template.pk),
        after={"name": name, "class_id": str(class_id) if class_id else None},
    )
    return template


# --------------------------------------------------------------------------- sessions


def list_sessions(actor: User, class_id):
    lab_class = get_class(actor, class_id)
    return Session.objects.select_related("lab_class").filter(lab_class=lab_class)


@transaction.atomic
def create_session(
    actor: User,
    class_id,
    name,
    *,
    template_id=None,
    kind=None,
    structure=None,
    allowed_roles=None,
    default_visibility=None,
    learning_panel=None,
    seed_profile=None,
    opening_capital_usd=None,
    opening_capital_sos=None,
) -> Session:
    """Create a draft session. Explicit values win over the template, which wins over defaults."""
    lab_class = get_class(actor, class_id)
    template = None
    if template_id is not None:
        template = SessionTemplate.objects.filter(
            pk=template_id, institution_id=lab_class.institution_id
        ).first()
        if template is None or template.lab_class_id not in (None, lab_class.pk):
            raise NotFound("Template not found")

    def pick(value, attr, default):
        if value is not None:
            return value
        return getattr(template, attr) if template is not None else default

    name = (name or "").strip()
    if not name:
        raise ValidationFailed("Name is required")
    kind, structure, visibility, panel = _normalize_settings(
        pick(kind, "kind", SessionKind.PRACTICE),
        pick(structure, "structure", SessionStructure.SINGLE_BANK),
        pick(default_visibility, "default_visibility", Visibility.OWN),
        pick(learning_panel, "learning_panel", True),
    )
    session = Session.objects.create(
        lab_class=lab_class,
        template=template,
        name=name,
        kind=kind,
        structure=structure,
        allowed_roles=_check_roles(pick(allowed_roles, "allowed_roles", list(BankRole.values))),
        default_visibility=visibility,
        learning_panel=panel,
        seed_profile=(pick(seed_profile, "seed_profile", "") or "").strip(),
        opening_capital_usd=_check_capital(
            pick(opening_capital_usd, "opening_capital_usd", DEFAULT_CAPITAL_USD),
            "Opening capital USD",
        ),
        opening_capital_sos=_check_capital(
            pick(opening_capital_sos, "opening_capital_sos", DEFAULT_CAPITAL_SOS),
            "Opening capital SOS",
        ),
        created_by=actor,
    )
    _audit(
        actor,
        "lab.session_created",
        ("session", session.pk),
        after=_session_dict(session),
        session=session,
    )
    return session


def _create_bank(actor, session: Session, name: str, group_no, business_date) -> Bank:
    with _conflict_guard():
        bank = Bank.objects.create(session=session, name=name, group_no=group_no)
        BusinessDay.objects.create(bank=bank, date=business_date)
        ledger.provision_bank_coa(bank)
        # A1: main branch + vault + opening capital; posts as the system actor, so the
        # session must already be active (open_session activates it first).
        provision_bank_cash(bank, session)
    _audit(
        actor,
        "lab.bank_created",
        ("bank", bank.pk),
        after={"name": name, "group_no": group_no, "business_date": str(business_date)},
        session=session,
        bank=bank,
    )
    return bank


@transaction.atomic
def open_session(actor: User, session_id, group_count: int | None = None) -> Session:
    """draft -> active: create the bank(s) with their first business day."""
    session = get_session(actor, session_id, lock=True)
    if session.status != SessionStatus.DRAFT:
        raise Conflict("Only a draft session can be opened")
    now = timezone.now()
    today = timezone.localdate(now)
    before = _session_dict(session)
    # Activate first: the opening-capital posting of each new bank requires an active session.
    session.status, session.opened_at = SessionStatus.ACTIVE, now
    session.save(update_fields=["status", "opened_at", "updated_at"])
    if session.structure == SessionStructure.SINGLE_BANK:
        banks = [_create_bank(actor, session, session.name, None, today)]
    else:
        if not group_count or not 1 <= group_count <= MAX_GROUPS:
            raise ValidationFailed(f"group_count must be between 1 and {MAX_GROUPS}")
        banks = [
            _create_bank(actor, session, f"Group {n}", n, today) for n in range(1, group_count + 1)
        ]
    if len(banks) == 1:
        for member in SessionMember.objects.select_for_update().filter(
            session=session, bank__isnull=True
        ):
            member.bank = banks[0]
            member.save(update_fields=["bank", "updated_at"])
            _audit(
                actor,
                "lab.member_moved",
                ("session_member", member.pk),
                before={"bank_id": None},
                after={"bank_id": str(banks[0].pk)},
                session=session,
                bank=banks[0],
            )
    _audit(
        actor,
        "lab.session_opened",
        ("session", session.pk),
        before=before,
        after=_session_dict(session),
        session=session,
    )
    return session


@transaction.atomic
def archive_session(actor: User, session_id) -> Session:
    session = get_session(actor, session_id, lock=True)
    if session.status != SessionStatus.ACTIVE:
        raise Conflict("Only an active session can be archived")
    session.status, session.archived_at = SessionStatus.ARCHIVED, timezone.now()
    session.save(update_fields=["status", "archived_at", "updated_at"])
    _audit(
        actor,
        "lab.session_archived",
        ("session", session.pk),
        before={"status": SessionStatus.ACTIVE},
        after={"status": session.status},
        session=session,
    )
    return session


@transaction.atomic
def reopen_session(actor: User, session_id) -> Session:
    session = get_session(actor, session_id, lock=True)
    if session.status != SessionStatus.ARCHIVED:
        raise Conflict("Only an archived session can be re-opened")
    session.status, session.archived_at = SessionStatus.ACTIVE, None
    session.save(update_fields=["status", "archived_at", "updated_at"])
    _audit(
        actor,
        "lab.session_reopened",
        ("session", session.pk),
        before={"status": SessionStatus.ARCHIVED},
        after={"status": session.status},
        session=session,
    )
    return session


def list_banks(actor: User, session_id):
    session = get_session(actor, session_id)
    return Bank.objects.filter(session=session)


@transaction.atomic
def add_group_bank(actor: User, session_id) -> Bank:
    """Add the next group bank to an active per-group session."""
    session = get_writable_session(actor, session_id)
    if session.structure != SessionStructure.PER_GROUP:
        raise ValidationFailed("Only per-group sessions have several banks")
    if session.status != SessionStatus.ACTIVE:
        raise Conflict("Session is not active")
    last = Bank.objects.filter(session=session).order_by("-group_no").first()
    n = (last.group_no if last else 0) + 1
    if n > MAX_GROUPS:
        raise ValidationFailed(f"At most {MAX_GROUPS} groups")
    return _create_bank(actor, session, f"Group {n}", n, timezone.localdate())


def business_days(actor: User, session_id):
    """Current open business day of each bank in the session."""
    session = get_session(actor, session_id)
    return BusinessDay.objects.select_related("bank").filter(
        bank__session=session, status="open"
    ).order_by("bank__group_no", "bank__created_at")


# --------------------------------------------------------------------------- members


def list_members(actor: User, session_id):
    session = get_session(actor, session_id)
    return SessionMember.objects.select_related("user", "bank").filter(session=session)


def active_assignment(member: SessionMember) -> RoleAssignment | None:
    return RoleAssignment.objects.filter(session_member=member, active_to__isnull=True).first()


@transaction.atomic
def add_members(
    actor: User, session_id, user_ids=(), *, all_enrolled: bool = False, bank_id=None
) -> list[SessionMember]:
    session = get_writable_session(actor, session_id)
    enrolled = {
        e.user_id: e.user
        for e in Enrollment.objects.select_related("user").filter(lab_class=session.lab_class)
    }
    ids = set(enrolled) if all_enrolled else set(user_ids)
    if not ids:
        raise ValidationFailed("No students selected")
    bank = _bank_of(session, bank_id) if bank_id is not None else None
    if bank is None and session.status == SessionStatus.ACTIVE:
        only = list(Bank.objects.filter(session=session)[:2])
        if session.structure == SessionStructure.SINGLE_BANK and len(only) == 1:
            bank = only[0]
    existing = set(
        SessionMember.objects.filter(session=session, user_id__in=ids).values_list(
            "user_id", flat=True
        )
    )
    added = []
    for uid in ids:
        if uid not in enrolled:
            raise ValidationFailed("Every student must be enrolled in the session's class")
        if uid in existing:
            if all_enrolled:
                continue
            raise ValidationFailed("Student is already a member of this session")
        if not enrolled[uid].is_active:
            if all_enrolled:
                continue
            raise ValidationFailed("Student account is inactive")
        with _conflict_guard():
            member = SessionMember.objects.create(session=session, user=enrolled[uid], bank=bank)
        added.append(member)
        _audit(
            actor,
            "lab.member_added",
            ("session_member", member.pk),
            after={"user_id": str(uid), "bank_id": str(bank.pk) if bank else None},
            session=session,
            bank=bank,
        )
    return added


def _bank_of(session: Session, bank_id) -> Bank:
    bank = Bank.objects.filter(pk=bank_id, session=session).first()
    if bank is None:
        raise NotFound("Bank not found in this session")
    return bank


def _locked_member(session: Session, member_id) -> SessionMember:
    member = (
        SessionMember.objects.select_for_update(of=("self",))
        .select_related("user", "bank")
        .filter(pk=member_id, session=session)
        .first()
    )
    if member is None:
        raise NotFound("Member not found")
    return member


@transaction.atomic
def move_member(actor: User, session_id, member_id, bank_id) -> SessionMember:
    session = get_writable_session(actor, session_id)
    member = _locked_member(session, member_id)
    bank = _bank_of(session, bank_id)
    before = {"bank_id": str(member.bank_id) if member.bank_id else None}
    member.bank = bank
    member.save(update_fields=["bank", "updated_at"])
    _audit(
        actor,
        "lab.member_moved",
        ("session_member", member.pk),
        before=before,
        after={"bank_id": str(bank.pk)},
        session=session,
        bank=bank,
    )
    return member


@transaction.atomic
def set_visibility_override(actor: User, session_id, member_id, value) -> SessionMember:
    session = get_writable_session(actor, session_id)
    if value is not None and value not in Visibility.values:
        raise ValidationFailed("Invalid visibility")
    member = _locked_member(session, member_id)
    before = {"visibility_override": member.visibility_override}
    member.visibility_override = value
    member.save(update_fields=["visibility_override", "updated_at"])
    _audit(
        actor,
        "lab.visibility_override_set",
        ("session_member", member.pk),
        before=before,
        after={"visibility_override": value},
        session=session,
        bank=member.bank,
    )
    return member


@transaction.atomic
def assign_role(actor: User, session_id, member_id, role: str) -> RoleAssignment:
    """Close the member's active assignment and open a new one (one active role at a time)."""
    session = get_writable_session(actor, session_id)
    if role not in BankRole.values:
        raise ValidationFailed("Invalid bank role")
    if role not in session.allowed_roles:
        raise ValidationFailed("This role is not allowed in this session")
    member = _locked_member(session, member_id)
    current = active_assignment(member)
    if current is not None and current.role == role:
        return current
    now = timezone.now()
    if current is not None:
        current.active_to = now
        current.save(update_fields=["active_to", "updated_at"])
    with _conflict_guard():
        assignment = RoleAssignment.objects.create(
            session_member=member, role=role, assigned_by=actor, active_from=now
        )
    _audit(
        actor,
        "lab.role_assigned",
        ("session_member", member.pk),
        before={"role": current.role if current else None},
        after={"role": role},
        session=session,
        bank=member.bank,
    )
    return assignment


# --------------------------------------------------------------------------- permissions


def effective_matrix(actor: User, session_id) -> list[dict]:
    """Every (role, code) cell: default scope, override and effective scope."""
    session = get_session(actor, session_id)
    codes = list(Permission.objects.values_list("code", "description", "category"))
    overrides = {
        (o.role, o.permission_id): o.allowed
        for o in PermissionOverride.objects.filter(session=session)
    }
    cells = []
    for role in BankRole.values:
        for code, description, category in codes:
            override = overrides.get((role, code))
            cells.append(
                {
                    "role": role,
                    "permission_code": code,
                    "description": description,
                    "category": category,
                    "default_scope": rbac.default_scope(role, code),
                    "override": override,
                    "effective_scope": rbac.permission_scope(
                        role, code, session=session, overrides=overrides
                    ),
                }
            )
    return cells


@transaction.atomic
def set_permission_override(
    actor: User, session_id, role: str, permission_code: str, allowed: bool
) -> PermissionOverride:
    session = get_writable_session(actor, session_id)
    if role not in BankRole.values:
        raise ValidationFailed("Invalid bank role")
    if not Permission.objects.filter(pk=permission_code).exists():
        raise ValidationFailed("Unknown permission code")
    rbac.assert_override_allowed(role, permission_code, allowed)
    existing = PermissionOverride.objects.filter(
        session=session, role=role, permission_id=permission_code
    ).first()
    before = {"allowed": existing.allowed} if existing else None
    if existing is None:
        with _conflict_guard():
            override = PermissionOverride.objects.create(
                session=session, role=role, permission_id=permission_code, allowed=allowed
            )
    else:
        override = existing
        override.allowed = allowed
        override.save(update_fields=["allowed", "updated_at"])
    _audit(
        actor,
        "lab.permission_override_set",
        ("permission_override", override.pk),
        before=before,
        after={"role": role, "permission_code": permission_code, "allowed": allowed},
        session=session,
    )
    return override


@transaction.atomic
def clear_permission_override(actor: User, session_id, role: str, permission_code: str) -> None:
    session = get_writable_session(actor, session_id)
    override = PermissionOverride.objects.filter(
        session=session, role=role, permission_id=permission_code
    ).first()
    if override is None:
        raise NotFound("No override for this role and permission")
    before = {"role": role, "permission_code": permission_code, "allowed": override.allowed}
    override_id = override.pk
    override.delete()
    _audit(
        actor,
        "lab.permission_override_cleared",
        ("permission_override", override_id),
        before=before,
        session=session,
    )
