from datetime import date, datetime
from uuid import UUID

from ninja import Router, Schema

from apps.accounts.models import User
from apps.rbac import context as rbac_context
from apps.rbac import services as rbac
from apps.rbac.models import Permission

from . import services
from .models import SessionMember

router = Router(tags=["lab"])
student_router = Router(tags=["lab-student"])


# ----------------------------------------------------------------------- schemas


class ClassIn(Schema):
    name: str
    code: str
    instructor_id: UUID | None = None  # admin only


class ClassOut(Schema):
    id: UUID
    name: str
    code: str
    instructor_id: UUID
    instructor_name: str

    @staticmethod
    def resolve_instructor_name(obj):
        return obj.instructor.full_name or obj.instructor.username


class StudentOut(Schema):
    id: UUID
    username: str
    full_name: str
    phone: str
    is_active: bool
    must_change_password: bool


class AddStudentIn(Schema):
    username: str
    full_name: str = ""
    phone: str = ""


class AddStudentOut(Schema):
    student: StudentOut
    created: bool


class UpdateStudentIn(Schema):
    full_name: str | None = None
    phone: str | None = None
    is_active: bool | None = None


class CsvIn(Schema):
    csv_text: str


class CsvRowOut(Schema):
    line: int
    username: str
    full_name: str
    phone: str
    action: str  # create | enroll | error
    error: str


class CsvResultOut(Schema):
    rows: list[CsvRowOut]
    ok_count: int
    error_count: int
    imported: bool


class TemplateIn(Schema):
    name: str
    kind: str
    structure: str
    allowed_roles: list[str]
    default_visibility: str
    learning_panel: bool = True
    seed_profile: str = ""
    class_id: UUID | None = None


class TemplateOut(Schema):
    id: UUID
    class_id: UUID | None = None
    name: str
    kind: str
    structure: str
    allowed_roles: list[str]
    default_visibility: str
    learning_panel: bool
    seed_profile: str

    @staticmethod
    def resolve_class_id(obj):
        return obj.lab_class_id


class SessionIn(Schema):
    class_id: UUID
    name: str
    template_id: UUID | None = None
    kind: str | None = None
    structure: str | None = None
    allowed_roles: list[str] | None = None
    default_visibility: str | None = None
    learning_panel: bool | None = None
    seed_profile: str | None = None


class SessionOut(Schema):
    id: UUID
    class_id: UUID
    class_name: str
    template_id: UUID | None = None
    name: str
    kind: str
    structure: str
    status: str
    allowed_roles: list[str]
    default_visibility: str
    learning_panel: bool
    seed_profile: str
    opened_at: datetime | None = None
    archived_at: datetime | None = None

    @staticmethod
    def resolve_class_id(obj):
        return obj.lab_class_id

    @staticmethod
    def resolve_class_name(obj):
        return obj.lab_class.name


class OpenSessionIn(Schema):
    group_count: int | None = None  # required for per-group sessions


class BankOut(Schema):
    id: UUID
    session_id: UUID
    name: str
    group_no: int | None = None


class BusinessDayOut(Schema):
    bank_id: UUID
    bank_name: str
    date: date
    status: str

    @staticmethod
    def resolve_bank_name(obj):
        return obj.bank.name


class MemberOut(Schema):
    id: UUID
    user_id: UUID
    username: str
    full_name: str
    bank_id: UUID | None = None
    bank_name: str | None = None
    visibility_override: str | None = None
    role: str | None = None

    @staticmethod
    def resolve_username(obj):
        return obj.user.username

    @staticmethod
    def resolve_full_name(obj):
        return obj.user.full_name

    @staticmethod
    def resolve_bank_name(obj):
        return obj.bank.name if obj.bank_id else None

    @staticmethod
    def resolve_role(obj):
        assignment = services.active_assignment(obj)
        return assignment.role if assignment else None


class AddMembersIn(Schema):
    user_ids: list[UUID] = []
    all_enrolled: bool = False
    bank_id: UUID | None = None


class MoveMemberIn(Schema):
    bank_id: UUID


class VisibilityIn(Schema):
    visibility: str | None = None  # own | all | null clears the override


class RoleIn(Schema):
    role: str


class AssignmentOut(Schema):
    id: UUID
    session_member_id: UUID
    role: str
    active_from: datetime
    active_to: datetime | None = None


class PermissionCellOut(Schema):
    role: str
    permission_code: str
    description: str
    category: str
    default_scope: str | None = None
    override: bool | None = None
    effective_scope: str | None = None


class OverrideIn(Schema):
    role: str
    permission_code: str
    allowed: bool


class OverrideKeyIn(Schema):
    role: str
    permission_code: str


class OverrideOut(Schema):
    role: str
    permission_code: str
    allowed: bool

    @staticmethod
    def resolve_permission_code(obj):
        return obj.permission_id


# ----------------------------------------------------------------------- classes & students


@router.get("/classes", response=list[ClassOut], operation_id="lab_classes_list")
def classes_list(request):
    return services.list_classes(request.user)


@router.post("/classes", response=ClassOut, operation_id="lab_classes_create")
def classes_create(request, payload: ClassIn):
    return services.create_class(request.user, payload.name, payload.code, payload.instructor_id)


@router.get("/classes/{class_id}", response=ClassOut, operation_id="lab_classes_get")
def classes_get(request, class_id: UUID):
    return services.get_class(request.user, class_id)


@router.get(
    "/classes/{class_id}/students", response=list[StudentOut], operation_id="lab_students_list"
)
def students_list(request, class_id: UUID):
    return [e.user for e in services.list_students(request.user, class_id)]


@router.post(
    "/classes/{class_id}/students", response=AddStudentOut, operation_id="lab_students_add"
)
def students_add(request, class_id: UUID, payload: AddStudentIn):
    user, created = services.add_student(
        request.user, class_id, payload.username, payload.full_name, payload.phone
    )
    return {"student": user, "created": created}


@router.patch(
    "/classes/{class_id}/students/{user_id}",
    response=StudentOut,
    operation_id="lab_students_update",
)
def students_update(request, class_id: UUID, user_id: UUID, payload: UpdateStudentIn):
    return services.update_student(
        request.user,
        class_id,
        user_id,
        full_name=payload.full_name,
        phone=payload.phone,
        is_active=payload.is_active,
    )


def _csv_out(result, imported: bool) -> dict:
    return {
        "rows": result.rows,
        "ok_count": result.ok_count,
        "error_count": result.error_count,
        "imported": imported,
    }


@router.post(
    "/classes/{class_id}/students/import/preview",
    response=CsvResultOut,
    operation_id="lab_students_import_preview",
)
def students_import_preview(request, class_id: UUID, payload: CsvIn):
    result = services.preview_students_csv(request.user, class_id, payload.csv_text)
    if result.fatal:
        raise services.ValidationFailed(result.fatal)
    return _csv_out(result, False)


@router.post(
    "/classes/{class_id}/students/import/confirm",
    response=CsvResultOut,
    operation_id="lab_students_import_confirm",
)
def students_import_confirm(request, class_id: UUID, payload: CsvIn):
    return _csv_out(services.confirm_students_csv(request.user, class_id, payload.csv_text), True)


# ----------------------------------------------------------------------- templates


@router.get("/templates", response=list[TemplateOut], operation_id="lab_templates_list")
def templates_list(request, class_id: UUID | None = None):
    return services.list_templates(request.user, class_id)


@router.post("/templates", response=TemplateOut, operation_id="lab_templates_create")
def templates_create(request, payload: TemplateIn):
    return services.create_template(request.user, **payload.dict())


# ----------------------------------------------------------------------- sessions


@router.get(
    "/classes/{class_id}/sessions", response=list[SessionOut], operation_id="lab_sessions_list"
)
def sessions_list(request, class_id: UUID):
    return services.list_sessions(request.user, class_id)


@router.post("/sessions", response=SessionOut, operation_id="lab_sessions_create")
def sessions_create(request, payload: SessionIn):
    data = payload.dict()
    return services.create_session(request.user, data.pop("class_id"), data.pop("name"), **data)


@router.get("/sessions/{session_id}", response=SessionOut, operation_id="lab_sessions_get")
def sessions_get(request, session_id: UUID):
    return services.get_session(request.user, session_id)


@router.post("/sessions/{session_id}/open", response=SessionOut, operation_id="lab_sessions_open")
def sessions_open(request, session_id: UUID, payload: OpenSessionIn):
    return services.open_session(request.user, session_id, payload.group_count)


@router.post(
    "/sessions/{session_id}/archive", response=SessionOut, operation_id="lab_sessions_archive"
)
def sessions_archive(request, session_id: UUID):
    return services.archive_session(request.user, session_id)


@router.post(
    "/sessions/{session_id}/reopen", response=SessionOut, operation_id="lab_sessions_reopen"
)
def sessions_reopen(request, session_id: UUID):
    return services.reopen_session(request.user, session_id)


@router.get(
    "/sessions/{session_id}/banks", response=list[BankOut], operation_id="lab_banks_list"
)
def banks_list(request, session_id: UUID):
    return services.list_banks(request.user, session_id)


@router.post("/sessions/{session_id}/banks", response=BankOut, operation_id="lab_banks_add")
def banks_add(request, session_id: UUID):
    return services.add_group_bank(request.user, session_id)


@router.get(
    "/sessions/{session_id}/business-days",
    response=list[BusinessDayOut],
    operation_id="lab_business_days",
)
def business_days(request, session_id: UUID):
    return [
        {"bank_id": d.bank_id, "bank_name": d.bank.name, "date": d.date, "status": d.status}
        for d in services.business_days(request.user, session_id)
    ]


# ----------------------------------------------------------------------- members & roles


@router.get(
    "/sessions/{session_id}/members", response=list[MemberOut], operation_id="lab_members_list"
)
def members_list(request, session_id: UUID):
    return services.list_members(request.user, session_id)


@router.post(
    "/sessions/{session_id}/members", response=list[MemberOut], operation_id="lab_members_add"
)
def members_add(request, session_id: UUID, payload: AddMembersIn):
    return services.add_members(
        request.user,
        session_id,
        payload.user_ids,
        all_enrolled=payload.all_enrolled,
        bank_id=payload.bank_id,
    )


@router.post(
    "/sessions/{session_id}/members/{member_id}/bank",
    response=MemberOut,
    operation_id="lab_members_move",
)
def members_move(request, session_id: UUID, member_id: UUID, payload: MoveMemberIn):
    return services.move_member(request.user, session_id, member_id, payload.bank_id)


@router.post(
    "/sessions/{session_id}/members/{member_id}/visibility",
    response=MemberOut,
    operation_id="lab_members_visibility",
)
def members_visibility(request, session_id: UUID, member_id: UUID, payload: VisibilityIn):
    return services.set_visibility_override(
        request.user, session_id, member_id, payload.visibility
    )


@router.post(
    "/sessions/{session_id}/members/{member_id}/role",
    response=AssignmentOut,
    operation_id="lab_members_assign_role",
)
def members_assign_role(request, session_id: UUID, member_id: UUID, payload: RoleIn):
    return services.assign_role(request.user, session_id, member_id, payload.role)


# ----------------------------------------------------------------------- permission overrides


@router.get(
    "/sessions/{session_id}/permissions",
    response=list[PermissionCellOut],
    operation_id="lab_permissions_matrix",
)
def permissions_matrix(request, session_id: UUID):
    return services.effective_matrix(request.user, session_id)


@router.put(
    "/sessions/{session_id}/permissions/overrides",
    response=OverrideOut,
    operation_id="lab_permissions_set",
)
def permissions_set(request, session_id: UUID, payload: OverrideIn):
    return services.set_permission_override(
        request.user, session_id, payload.role, payload.permission_code, payload.allowed
    )


@router.post(
    "/sessions/{session_id}/permissions/overrides/clear",
    response={204: None},
    operation_id="lab_permissions_clear",
)
def permissions_clear(request, session_id: UUID, payload: OverrideKeyIn):
    services.clear_permission_override(
        request.user, session_id, payload.role, payload.permission_code
    )
    return 204, None


# ----------------------------------------------------------------------- student side


class MySessionOut(Schema):
    session_id: UUID
    name: str
    kind: str
    class_name: str
    bank_name: str | None = None
    role: str | None = None


class PermissionGrantOut(Schema):
    code: str
    scope: str


class SessionMeOut(Schema):
    session_id: UUID
    session_name: str
    kind: str
    status: str
    class_name: str
    bank_id: UUID | None = None
    bank_name: str | None = None
    business_date: date | None = None
    role: str | None = None
    visibility: str
    learning_panel: bool
    read_only: bool
    permissions: list[PermissionGrantOut]


def _require_student(user: User) -> None:
    if user.platform_role != "student":
        raise services.PermissionDenied("Not allowed")


@student_router.get("/my/sessions", response=list[MySessionOut], operation_id="lab_my_sessions")
def my_sessions(request):
    _require_student(request.user)
    members = (
        SessionMember.objects.select_related("session__lab_class", "bank")
        .filter(user=request.user, session__status="active")
        .order_by("-session__opened_at")
    )
    out = []
    for m in members:
        assignment = services.active_assignment(m)
        out.append(
            {
                "session_id": m.session_id,
                "name": m.session.name,
                "kind": m.session.kind,
                "class_name": m.session.lab_class.name,
                "bank_name": m.bank.name if m.bank_id else None,
                "role": assignment.role if assignment else None,
            }
        )
    return out


@student_router.get(
    "/s/{session_id}/me", response=SessionMeOut, operation_id="lab_session_me"
)
def session_me(request, session_id: UUID):
    _require_student(request.user)
    ctx = rbac_context.resolve_bank_context(request, session_id, require_role=False)
    session, bank, role = ctx.session, ctx.bank, ctx.role
    business_date = None
    if bank is not None:
        day = bank.business_days.filter(status="open").first()
        business_date = day.date if day else None
    permissions = []
    if role:
        overrides = rbac.load_overrides(session)
        for code in Permission.objects.values_list("code", flat=True):
            scope = rbac.permission_scope(role, code, session=session, overrides=overrides)
            if scope:
                permissions.append({"code": code, "scope": scope})
    return {
        "session_id": session.pk,
        "session_name": session.name,
        "kind": session.kind,
        "status": session.status,
        "class_name": session.lab_class.name,
        "bank_id": bank.pk if bank else None,
        "bank_name": bank.name if bank else None,
        "business_date": business_date,
        "role": role,
        "visibility": request.visibility,
        "learning_panel": session.learning_panel,
        "read_only": session.status == "archived",
        "permissions": permissions,
    }


