"""Admin console API (1.12b). Everything under /admin is Admin-only; the institution
logo and name are readable by any signed-in user of that institution."""

from decimal import Decimal
from uuid import UUID

from django.http import FileResponse
from ninja import File, Router, Schema, UploadedFile
from ninja.errors import HttpError

from apps.lab.api import ClassOut

from . import services

router = Router(tags=["admin"])
institution_router = Router(tags=["institution"])


class InstructorIn(Schema):
    username: str
    full_name: str
    phone: str


class InstructorOut(Schema):
    id: UUID
    username: str
    full_name: str
    phone: str
    is_active: bool
    must_change_password: bool


class ActiveIn(Schema):
    is_active: bool


class ClassInstructorIn(Schema):
    instructor_id: UUID


class InstitutionNameIn(Schema):
    name: str


class InstitutionOut(Schema):
    id: UUID
    name: str
    has_logo: bool
    logo_url: str | None = None

    @staticmethod
    def resolve_has_logo(obj):
        return bool(obj.logo)

    @staticmethod
    def resolve_logo_url(obj):
        return "/api/institution/logo" if obj.logo else None


class CoaTemplateIn(Schema):
    name: str
    copy_from_id: UUID | None = None


class CoaLineIn(Schema):
    code: str
    name: str
    type: str
    parent_code: str = ""
    postable: bool = False


class CoaLinePatch(Schema):
    name: str | None = None
    is_active: bool | None = None


class CoaLineOut(Schema):
    id: UUID
    code: str
    name: str
    type: str
    parent_code: str
    postable: bool
    system_tag: str
    is_active: bool
    allow_negative: bool


class CoaTemplateRow(Schema):
    id: UUID
    name: str
    is_default: bool
    line_count: int
    session_template_count: int

    @staticmethod
    def resolve_is_default(obj):
        from apps.ledger.coa import DEFAULT_COA_NAME

        return obj.name == DEFAULT_COA_NAME


class CoaTemplateDetail(Schema):
    id: UUID
    name: str
    is_default: bool
    lines: list[CoaLineOut]

    @staticmethod
    def resolve_is_default(obj):
        from apps.ledger.coa import DEFAULT_COA_NAME

        return obj.name == DEFAULT_COA_NAME

    @staticmethod
    def resolve_lines(obj):
        return list(obj.lines.all().order_by("code"))


class SessionTemplateIn(Schema):
    name: str
    kind: str
    structure: str
    allowed_roles: list[str]
    default_visibility: str
    learning_panel: bool = True
    seed_profile: str = ""
    opening_capital_usd: Decimal = Decimal("1000000.00")
    opening_capital_sos: Decimal = Decimal("5000000000.00")
    coa_template_id: UUID | None = None


class SessionTemplateOut(Schema):
    id: UUID
    name: str
    kind: str
    structure: str
    allowed_roles: list[str]
    default_visibility: str
    learning_panel: bool
    seed_profile: str
    opening_capital_usd: Decimal
    opening_capital_sos: Decimal
    coa_template_id: UUID | None = None


def _admin(request):
    services.require_admin(request.user)
    return request.user


# ----------------------------------------------------------------------- instructors


@router.get("/instructors", response=list[InstructorOut], operation_id="admin_instructors_list")
def instructors_list(request):
    return services.list_instructors(_admin(request))


@router.post("/instructors", response=InstructorOut, operation_id="admin_instructors_create")
def instructors_create(request, payload: InstructorIn):
    return services.create_instructor(
        _admin(request), payload.username, payload.full_name, payload.phone, request=request
    )


@router.put(
    "/instructors/{user_id}/active",
    response=InstructorOut,
    operation_id="admin_instructors_set_active",
)
def instructors_set_active(request, user_id: UUID, payload: ActiveIn):
    return services.set_instructor_active(
        _admin(request), user_id, payload.is_active, request=request
    )


@router.post(
    "/instructors/{user_id}/reset-password",
    response={204: None},
    operation_id="admin_instructors_reset_password",
)
def instructors_reset_password(request, user_id: UUID):
    services.reset_instructor_password(_admin(request), user_id, request=request)
    return 204, None


@router.put(
    "/classes/{class_id}/instructor",
    response=ClassOut,
    operation_id="admin_class_set_instructor",
)
def class_set_instructor(request, class_id: UUID, payload: ClassInstructorIn):
    return services.set_class_instructor(
        _admin(request), class_id, payload.instructor_id, request=request
    )


# ----------------------------------------------------------------------- institution


@router.get("/institution", response=InstitutionOut, operation_id="admin_institution_get")
def institution_get(request):
    return services.get_institution(_admin(request))


@router.put("/institution", response=InstitutionOut, operation_id="admin_institution_put")
def institution_put(request, payload: InstitutionNameIn):
    return services.update_institution_name(_admin(request), payload.name, request=request)


@router.post(
    "/institution/logo", response=InstitutionOut, operation_id="admin_institution_logo_put"
)
def institution_logo_put(request, file: File[UploadedFile]):
    """PNG or JPG, max 1 MB."""
    return services.set_institution_logo(_admin(request), file, request=request)


@router.delete(
    "/institution/logo", response=InstitutionOut, operation_id="admin_institution_logo_delete"
)
def institution_logo_delete(request):
    return services.delete_institution_logo(_admin(request), request=request)


@institution_router.get("/institution", response=InstitutionOut, operation_id="institution_get")
def institution_public_get(request):
    return services.get_institution(request.user)


@institution_router.get("/institution/logo", operation_id="institution_logo_get")
def institution_logo(request):
    inst = services.get_institution(request.user)
    if not inst.logo:
        raise HttpError(404, "No logo")
    ctype = "image/png" if inst.logo.name.lower().endswith(".png") else "image/jpeg"
    response = FileResponse(inst.logo.open("rb"), content_type=ctype)
    response["Cache-Control"] = "private, max-age=300"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# ----------------------------------------------------------------------- CoA templates


@router.get("/coa-templates", response=list[CoaTemplateRow], operation_id="admin_coa_list")
def coa_list(request):
    return services.list_coa_templates(_admin(request))


@router.post("/coa-templates", response=CoaTemplateDetail, operation_id="admin_coa_create")
def coa_create(request, payload: CoaTemplateIn):
    return services.create_coa_template(
        _admin(request), payload.name, payload.copy_from_id, request=request
    )


@router.get(
    "/coa-templates/{template_id}", response=CoaTemplateDetail, operation_id="admin_coa_detail"
)
def coa_detail(request, template_id: UUID):
    return services.get_coa_template(_admin(request), template_id)


@router.delete(
    "/coa-templates/{template_id}", response={204: None}, operation_id="admin_coa_delete"
)
def coa_delete(request, template_id: UUID):
    services.delete_coa_template(_admin(request), template_id, request=request)
    return 204, None


@router.post(
    "/coa-templates/{template_id}/lines", response=CoaLineOut, operation_id="admin_coa_line_add"
)
def coa_line_add(request, template_id: UUID, payload: CoaLineIn):
    return services.add_coa_line(_admin(request), template_id, request=request, **payload.dict())


@router.patch(
    "/coa-templates/{template_id}/lines/{line_id}",
    response=CoaLineOut,
    operation_id="admin_coa_line_update",
)
def coa_line_update(request, template_id: UUID, line_id: UUID, payload: CoaLinePatch):
    return services.update_coa_line(
        _admin(request), template_id, line_id, request=request, **payload.dict()
    )


# ----------------------------------------------------------------------- session templates


@router.get(
    "/session-templates",
    response=list[SessionTemplateOut],
    operation_id="admin_session_templates_list",
)
def session_templates_list(request):
    return services.list_session_templates(_admin(request))


@router.post(
    "/session-templates", response=SessionTemplateOut, operation_id="admin_session_templates_create"
)
def session_templates_create(request, payload: SessionTemplateIn):
    return services.create_session_template(_admin(request), **payload.dict())


@router.put(
    "/session-templates/{template_id}",
    response=SessionTemplateOut,
    operation_id="admin_session_templates_update",
)
def session_templates_update(request, template_id: UUID, payload: SessionTemplateIn):
    return services.update_session_template(
        _admin(request), template_id, request=request, **payload.dict()
    )


@router.delete(
    "/session-templates/{template_id}",
    response={204: None},
    operation_id="admin_session_templates_delete",
)
def session_templates_delete(request, template_id: UUID):
    services.delete_session_template(_admin(request), template_id, request=request)
    return 204, None
