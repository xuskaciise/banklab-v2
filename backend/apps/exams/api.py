"""Exam API. Instructor routes `/sessions/{id}/exam...` (class owner / admin of the
institution); student routes `/s/{id}/exam...` (own attempt only). Rules live in
`services`; the write guard for banking endpoints is `guard.check_write_allowed`."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from django.http import HttpResponse
from ninja import Router, Schema

from apps.rbac import context as rbac_context

from . import checks, export, services
from .models import Exam

router = Router(tags=["exams"])
student_router = Router(tags=["exams-student"])

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ----------------------------------------------------------------------- schemas


class SeedSpecIn(Schema):
    product_code: str
    amount: Decimal
    vary: bool = False


class ExamIn(Schema):
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    instructions: str = ""
    seed: list[SeedSpecIn] = []


class TaskIn(Schema):
    title: str
    instructions: str = ""
    check_type: str
    check_params: dict = {}
    points: Decimal


class TaskPatch(Schema):
    title: str | None = None
    instructions: str | None = None
    check_type: str | None = None
    check_params: dict | None = None
    points: Decimal | None = None


class ReorderIn(Schema):
    task_ids: list[UUID]


class AdjustIn(Schema):
    adjusted_points: Decimal | None = None  # null clears the adjustment


class TaskOut(Schema):
    id: UUID
    position: int
    title: str
    instructions: str
    check_type: str
    check_params: dict
    points: Decimal


class ExamOut(Schema):
    id: UUID
    session_id: UUID
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    instructions: str
    seed: list[dict]
    status: str
    published_at: datetime | None = None
    results_published: bool
    total_points: Decimal
    tasks: list[TaskOut]
    seed_failures: list[UUID] = []  # members whose seed could not be created (publish only)


class CheckTypeOut(Schema):
    name: str
    label: str


class OkOut(Schema):
    ok: bool = True


class TaskResultOut(Schema):
    result_id: UUID
    task_id: UUID
    title: str
    max_points: Decimal
    passed: bool
    auto_points: Decimal
    adjusted_points: Decimal | None = None
    points: Decimal
    details: dict


class StudentRowOut(Schema):
    member_id: UUID
    username: str
    full_name: str
    status: str  # not_started | in_progress | submitted
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    auto_submitted: bool
    score: Decimal | None = None
    tasks: list[TaskResultOut]


class ResultsOut(Schema):
    results_published: bool
    max_score: Decimal
    students: list[StudentRowOut]


class StudentTaskOut(Schema):
    id: UUID
    position: int
    title: str
    instructions: str
    points: Decimal
    passed: bool | None = None  # known only after submit


class StudentExamOut(Schema):
    state: str  # not_open | ready | in_progress | submitted | missed
    instructions: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    server_time: datetime
    started_at: datetime | None = None
    deadline_at: datetime | None = None
    submitted_at: datetime | None = None
    auto_submitted: bool
    remaining_seconds: int | None = None
    results_published: bool
    tasks: list[StudentTaskOut]


class MyTaskResultOut(Schema):
    task_id: UUID
    title: str
    max_points: Decimal
    passed: bool
    points: Decimal
    adjusted: bool
    details: dict


class MyResultOut(Schema):
    score: Decimal
    max_score: Decimal
    submitted_at: datetime
    auto_submitted: bool
    tasks: list[MyTaskResultOut]


def _exam_out(exam: Exam) -> dict:
    tasks = list(exam.tasks.all())
    return {
        "id": exam.pk,
        "session_id": exam.session_id,
        "starts_at": exam.starts_at,
        "ends_at": exam.ends_at,
        "duration_minutes": exam.duration_minutes,
        "instructions": exam.instructions,
        "seed": exam.seed,
        "status": exam.status,
        "published_at": exam.published_at,
        "results_published": exam.results_published,
        "total_points": sum((t.points for t in tasks), Decimal("0.00")),
        "tasks": tasks,
    }


def _full(actor, session_id) -> dict:
    return _exam_out(services.get_exam(actor, session_id))


# ----------------------------------------------------------------------- instructor


@router.get("/exam-check-types", response=list[CheckTypeOut], operation_id="exam_check_types")
def check_types(request):
    return [{"name": c.name, "label": c.label} for c in checks.CHECKS.values()]


@router.get("/sessions/{session_id}/exam", response=ExamOut | None, operation_id="exam_get")
def exam_get(request, session_id: UUID):
    exam = services.get_exam(request.user, session_id)
    return _exam_out(exam) if exam else None


@router.put("/sessions/{session_id}/exam", response=ExamOut, operation_id="exam_save")
def exam_save(request, session_id: UUID, data: ExamIn):
    services.save_exam(
        request.user,
        session_id,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        duration_minutes=data.duration_minutes,
        instructions=data.instructions,
        seed_config=[s.dict() for s in data.seed],
    )
    return _full(request.user, session_id)


@router.post("/sessions/{session_id}/exam/tasks", response=ExamOut, operation_id="exam_task_create")
def task_create(request, session_id: UUID, data: TaskIn):
    services.add_task(request.user, session_id, **data.dict())
    return _full(request.user, session_id)


@router.post(
    "/sessions/{session_id}/exam/tasks/reorder", response=ExamOut, operation_id="exam_tasks_reorder"
)
def tasks_reorder(request, session_id: UUID, data: ReorderIn):
    services.reorder_tasks(request.user, session_id, data.task_ids)
    return _full(request.user, session_id)


@router.put(
    "/sessions/{session_id}/exam/tasks/{task_id}",
    response=ExamOut,
    operation_id="exam_task_update",
)
def task_update(request, session_id: UUID, task_id: UUID, data: TaskPatch):
    services.update_task(request.user, session_id, task_id, **data.dict(exclude_unset=True))
    return _full(request.user, session_id)


@router.delete(
    "/sessions/{session_id}/exam/tasks/{task_id}", response=ExamOut, operation_id="exam_task_delete"
)
def task_delete(request, session_id: UUID, task_id: UUID):
    services.delete_task(request.user, session_id, task_id)
    return _full(request.user, session_id)


@router.post("/sessions/{session_id}/exam/publish", response=ExamOut, operation_id="exam_publish")
def exam_publish(request, session_id: UUID):
    exam = services.publish_exam(request.user, session_id)
    return {**_full(request.user, session_id), "seed_failures": exam.seed_failures}


@router.get("/sessions/{session_id}/exam/results", response=ResultsOut, operation_id="exam_results")
def exam_results(request, session_id: UUID):
    return services.results(request.user, session_id)


@router.post(
    "/sessions/{session_id}/exam/results/publish",
    response=ExamOut,
    operation_id="exam_results_publish",
)
def results_publish(request, session_id: UUID):
    services.publish_results(request.user, session_id)
    return _full(request.user, session_id)


@router.post(
    "/sessions/{session_id}/exam/results/{result_id}/adjust",
    response=ResultsOut,
    operation_id="exam_result_adjust",
)
def result_adjust(request, session_id: UUID, result_id: UUID, data: AdjustIn):
    services.adjust_result(request.user, session_id, result_id, data.adjusted_points)
    return services.results(request.user, session_id)


@router.get("/sessions/{session_id}/exam/results.xlsx", operation_id="exam_results_xlsx")
def results_xlsx(request, session_id: UUID):
    body, name = export.xlsx_bytes(request.user, session_id)
    resp = HttpResponse(body, content_type=XLSX_TYPE)
    resp["Content-Disposition"] = f'attachment; filename="{name}.xlsx"'
    return resp


@router.get("/sessions/{session_id}/exam/results.pdf", operation_id="exam_results_pdf")
def results_pdf(request, session_id: UUID):
    body, name = export.pdf_bytes(request.user, session_id)
    resp = HttpResponse(body, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{name}.pdf"'
    return resp


# ----------------------------------------------------------------------- student


def _student_member(request, session_id):
    if request.user.platform_role != "student":
        raise services.lab.PermissionDenied("Not allowed")
    return rbac_context.resolve_bank_context(request, session_id, require_role=False).member


@student_router.get(
    "/s/{session_id}/exam", response=StudentExamOut, operation_id="exam_student_get"
)
def student_get(request, session_id: UUID):
    return services.student_view(_student_member(request, session_id))


@student_router.post(
    "/s/{session_id}/exam/start", response=StudentExamOut, operation_id="exam_student_start"
)
def student_start(request, session_id: UUID):
    return services.start_exam(_student_member(request, session_id))


@student_router.post(
    "/s/{session_id}/exam/submit", response=StudentExamOut, operation_id="exam_student_submit"
)
def student_submit(request, session_id: UUID):
    return services.submit_exam(_student_member(request, session_id))


@student_router.get(
    "/s/{session_id}/exam/result", response=MyResultOut, operation_id="exam_student_result"
)
def student_result(request, session_id: UUID):
    return services.student_result(_student_member(request, session_id))
