"""Exam business rules: set-up (instructor), timing, seed, submit + auto-check, grading.

Instructor functions take the acting `User` (class ownership is checked through
`lab.get_session`); student functions take the acting `SessionMember`. Exam rows are
editable only while the exam is `draft`; archived sessions are read-only. Checks are reads
only, so submitting never moves money.
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.banking import cheques
from apps.banking.models import Approval, ApprovalStatus, Transaction, TxnStatus
from apps.lab import services as lab
from apps.lab.models import Session, SessionKind, SessionMember, SessionStatus
from apps.lab.services import Conflict, NotFound, ValidationFailed
from apps.ledger.services import LedgerError

from . import checks, seed
from .models import Exam, ExamAttempt, ExamStatus, ExamTask, ExamTaskResult

ZERO = Decimal("0.00")
MAX_TASKS = 50
MAX_DURATION = 24 * 60


# --------------------------------------------------------------------------- helpers


def _audit(actor, role, action, session, entity, *, before=None, after=None, bank_id=None):
    audit.record(
        action,
        actor=actor,
        actor_role=role,
        entity=entity,
        before=before,
        after=after,
        session_id=session.pk,
        bank_id=bank_id,
        institution_id=session.lab_class.institution_id,
    )


def _exam_dict(exam: Exam) -> dict:
    return {
        "starts_at": exam.starts_at.isoformat(),
        "ends_at": exam.ends_at.isoformat(),
        "duration_minutes": exam.duration_minutes,
        "status": exam.status,
        "results_published": exam.results_published,
        "seed_accounts": len(exam.seed or []),
    }


def _task_dict(t: ExamTask) -> dict:
    return {
        "position": t.position,
        "title": t.title,
        "check_type": t.check_type,
        "check_params": t.check_params,
        "points": str(t.points),
    }


def _points(value, what: str = "Points", *, allow_zero: bool = False) -> Decimal:
    try:
        d = Decimal(str(value)).quantize(ZERO)
    except (InvalidOperation, ValueError):
        raise ValidationFailed(f"{what} must be a number") from None
    if d < 0 or (d == 0 and not allow_zero) or d > Decimal("100000"):
        raise ValidationFailed(f"{what} must be greater than zero")
    return d


def _aware(value, what: str):
    if value is None or timezone.is_naive(value):
        raise ValidationFailed(f"{what} must include a time zone")
    return value


def _text(value, what: str, max_len: int, *, required: bool = False) -> str:
    value = (value or "").strip()
    if required and not value:
        raise ValidationFailed(f"{what} is required")
    if len(value) > max_len:
        raise ValidationFailed(f"{what} is too long")
    return value


def _exam_session(actor, session_id, *, write: bool):
    session = (
        lab.get_writable_session(actor, session_id) if write else lab.get_session(actor, session_id)
    )
    if session.kind != SessionKind.EXAM:
        raise ValidationFailed("Only exam sessions can have an exam")
    return session


def _exam_of(session, *, lock: bool = False) -> Exam:
    qs = Exam.objects.select_for_update(of=("self",)) if lock else Exam.objects
    exam = qs.filter(session=session).first()
    if exam is None:
        raise NotFound("This session has no exam set up yet")
    return exam


def _draft(exam: Exam) -> None:
    if exam.status != ExamStatus.DRAFT:
        raise Conflict("The exam is published and can no longer be edited")


def _clean_window(starts_at, ends_at, duration) -> None:
    _aware(starts_at, "starts_at")
    _aware(ends_at, "ends_at")
    if ends_at <= starts_at:
        raise ValidationFailed("The exam must end after it starts")
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise ValidationFailed("duration_minutes must be a whole number")
    if not 1 <= duration <= MAX_DURATION:
        raise ValidationFailed(f"duration_minutes must be between 1 and {MAX_DURATION}")


# --------------------------------------------------------------------------- instructor: set-up


def get_exam(actor, session_id) -> Exam | None:
    session = _exam_session(actor, session_id, write=False)
    return Exam.objects.filter(session=session).prefetch_related("tasks").first()


@transaction.atomic
def save_exam(
    actor, session_id, *, starts_at, ends_at, duration_minutes, instructions="", seed_config=None
) -> Exam:
    session = _exam_session(actor, session_id, write=True)
    _clean_window(starts_at, ends_at, duration_minutes)
    try:
        seed_clean = seed.clean_seed(seed_config)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from None
    exam = Exam.objects.select_for_update(of=("self",)).filter(session=session).first()
    before = None
    if exam is None:
        exam = Exam(session=session)
    else:
        _draft(exam)
        before = _exam_dict(exam)
    exam.starts_at, exam.ends_at = starts_at, ends_at
    exam.duration_minutes = duration_minutes
    exam.instructions = _text(instructions, "Instructions", 10_000)
    exam.seed = seed_clean
    exam.save()
    _audit(
        actor,
        actor.platform_role,
        "exam.saved",
        session,
        ("exam", exam.pk),
        before=before,
        after=_exam_dict(exam),
    )
    return exam


def _clean_task(check_type, check_params, points, title, instructions) -> dict:
    try:
        params = checks.validate_params(check_type, check_params)
    except checks.CheckConfigError as exc:
        raise ValidationFailed(str(exc)) from None
    return {
        "title": _text(title, "Title", 200, required=True),
        "instructions": _text(instructions, "Instructions", 5_000),
        "check_type": check_type,
        "check_params": params,
        "points": _points(points),
    }


@transaction.atomic
def add_task(
    actor, session_id, *, title, check_type, check_params, points, instructions=""
) -> ExamTask:
    session = _exam_session(actor, session_id, write=True)
    exam = _exam_of(session, lock=True)
    _draft(exam)
    if exam.tasks.count() >= MAX_TASKS:
        raise ValidationFailed(f"An exam can have at most {MAX_TASKS} tasks")
    data = _clean_task(check_type, check_params, points, title, instructions)
    last = exam.tasks.order_by("-position").first()
    task = ExamTask.objects.create(exam=exam, position=(last.position + 1) if last else 1, **data)
    _audit(actor, actor.platform_role, "exam.task_added", session, ("exam_task", task.pk),
           after=_task_dict(task))  # fmt: skip
    return task


def _task_of(exam: Exam, task_id) -> ExamTask:
    task = exam.tasks.select_for_update(of=("self",)).filter(pk=task_id).first()
    if task is None:
        raise NotFound("Task not found")
    return task


@transaction.atomic
def update_task(actor, session_id, task_id, **fields) -> ExamTask:
    session = _exam_session(actor, session_id, write=True)
    exam = _exam_of(session, lock=True)
    _draft(exam)
    task = _task_of(exam, task_id)
    before = _task_dict(task)
    merged = {
        "title": fields.get("title", task.title),
        "instructions": fields.get("instructions", task.instructions),
        "check_type": fields.get("check_type", task.check_type),
        "check_params": fields.get("check_params", task.check_params),
        "points": fields.get("points", task.points),
    }
    for key, value in _clean_task(**merged).items():
        setattr(task, key, value)
    task.save()
    _audit(actor, actor.platform_role, "exam.task_updated", session, ("exam_task", task.pk),
           before=before, after=_task_dict(task))  # fmt: skip
    return task


@transaction.atomic
def delete_task(actor, session_id, task_id) -> None:
    """Tasks are set-up config (a draft exam has no results), so they may be removed."""
    session = _exam_session(actor, session_id, write=True)
    exam = _exam_of(session, lock=True)
    _draft(exam)
    task = _task_of(exam, task_id)
    before = _task_dict(task)
    task.delete()
    _audit(actor, actor.platform_role, "exam.task_removed", session, ("exam_task", task_id),
           before=before)  # fmt: skip


@transaction.atomic
def reorder_tasks(actor, session_id, task_ids) -> list[ExamTask]:
    session = _exam_session(actor, session_id, write=True)
    exam = _exam_of(session, lock=True)
    _draft(exam)
    tasks = {t.pk: t for t in exam.tasks.select_for_update(of=("self",))}
    wanted = [t for t in task_ids]
    if len(wanted) != len(set(wanted)) or set(wanted) != set(tasks):
        raise ValidationFailed("Give every task of the exam exactly once")
    for position, tid in enumerate(wanted, start=1):
        if tasks[tid].position != position:
            tasks[tid].position = position
            tasks[tid].save(update_fields=["position", "updated_at"])
    _audit(actor, actor.platform_role, "exam.tasks_reordered", session, ("exam", exam.pk),
           after={"order": [str(t) for t in wanted]})  # fmt: skip
    return [tasks[t] for t in wanted]


@transaction.atomic
def publish_exam(actor, session_id) -> Exam:
    """draft -> published; seeds every placed student when the session is already active."""
    session = _exam_session(actor, session_id, write=True)
    exam = _exam_of(session, lock=True)
    _draft(exam)
    if not exam.tasks.exists():
        raise ValidationFailed("Add at least one task before publishing")
    if exam.ends_at <= timezone.now():
        raise ValidationFailed("The exam end time is already in the past")
    exam.status, exam.published_at = ExamStatus.PUBLISHED, timezone.now()
    exam.save(update_fields=["status", "published_at", "updated_at"])
    _audit(actor, actor.platform_role, "exam.published", session, ("exam", exam.pk),
           before={"status": "draft"}, after=_exam_dict(exam))  # fmt: skip
    _, exam.seed_failures = seed_all(exam, actor=actor)
    return exam


def seed_all(exam: Exam, *, actor=None) -> tuple[int, list]:
    """Seed every student member placed in a bank (idempotent). A member whose seed cannot
    be created is reported (and audited) instead of failing the whole publish; that student
    gets a clear 409 at Start until it is fixed. Returns (created, failed member ids)."""
    total, failed = 0, []
    members = SessionMember.objects.filter(session=exam.session, bank__isnull=False)
    for member in members.order_by("created_at"):
        try:
            total += seed.ensure_member_seed(exam, member, actor=actor)
        except LedgerError as exc:
            failed.append(member.pk)
            _audit(
                actor,
                "instructor",
                "exam.seed_failed",
                exam.session,
                ("session_member", member.pk),
                after={"code": exc.code},
                bank_id=member.bank_id,
            )
    return total, failed


# --------------------------------------------------------------------------- attempts


def _final_score(attempt: ExamAttempt) -> Decimal:
    return sum((r.final_points for r in attempt.results.all()), ZERO)


def _reject_pending_approvals(member: SessionMember) -> None:
    """The student's time is over: limit approvals still waiting for a manager must not post
    later, so they are rejected (the money never moved)."""
    pending = Approval.objects.select_for_update(of=("self",)).filter(
        bank_id=member.bank_id,
        requested_by=member,
        status=ApprovalStatus.PENDING,
        subject_type="transaction",
    )
    for approval in pending:
        txn = (
            Transaction.objects.select_for_update(of=("self",))
            .filter(pk=approval.subject_id, status=TxnStatus.PENDING_APPROVAL)
            .first()
        )
        if txn is not None:
            txn.status = TxnStatus.REJECTED
            txn.save(update_fields=["status", "updated_at"])
            cheques.release(txn)
        approval.status = ApprovalStatus.REJECTED
        approval.decided_at = timezone.now()
        approval.note = "Auto-rejected: exam time is over"
        approval.save(update_fields=["status", "decided_at", "note", "updated_at"])
        _audit(
            None,
            "system",
            "exam.approval_auto_rejected",
            member.session,
            ("approval", approval.pk),
            after={"status": "rejected"},
            bank_id=member.bank_id,
        )


def _finalize(attempt: ExamAttempt, *, auto: bool, actor=None, role: str = "") -> ExamAttempt:
    """Run every task check on the member's own rows and store the results + score."""
    with transaction.atomic():
        # Lock order: session -> attempt (same as start_exam and the posting service).
        Session.objects.select_for_update(no_key=True).get(
            pk=SessionMember.objects.values_list("session_id", flat=True).get(
                pk=attempt.session_member_id
            )
        )
        attempt = ExamAttempt.objects.select_for_update(of=("self",)).get(pk=attempt.pk)
        if attempt.submitted_at is not None:
            return attempt
        member = SessionMember.objects.select_related("session__lab_class").get(
            pk=attempt.session_member_id
        )
        score = ZERO
        for task in attempt.exam.tasks.all():
            check = checks.CHECKS[task.check_type]
            passed, details = check.run(member, task.check_params, attempt.started_at)
            earned = task.points if passed else ZERO
            score += earned
            ExamTaskResult.objects.create(
                attempt=attempt, task=task, passed=passed, points=earned, details=details
            )
        _reject_pending_approvals(member)
        attempt.submitted_at = timezone.now()
        attempt.auto_submitted = auto
        attempt.score = score
        attempt.save(update_fields=["submitted_at", "auto_submitted", "score", "updated_at"])
        _audit(
            actor,
            role or "system",
            "exam.auto_submitted" if auto else "exam.submitted",
            member.session,
            ("exam_attempt", attempt.pk),
            after={"score": str(score)},
            bank_id=member.bank_id,
        )
        return attempt


def auto_submit_due(exam: Exam | None = None, *, member: SessionMember | None = None) -> int:
    """Submit attempts whose personal deadline has passed. Called lazily on reads and by
    `auto_submit_overdue` (a periodic job)."""
    qs = ExamAttempt.objects.filter(submitted_at__isnull=True, deadline_at__lte=timezone.now())
    if exam is not None:
        qs = qs.filter(exam=exam)
    if member is not None:
        qs = qs.filter(session_member=member)
    done = 0
    for attempt in qs.select_related("exam"):
        _finalize(attempt, auto=True)
        done += 1
    return done


def auto_submit_overdue() -> int:
    """Entry point for a django-q2 schedule: auto-submit every overdue attempt."""
    return auto_submit_due()


def _published_exam(member: SessionMember) -> Exam:
    exam = Exam.objects.filter(session_id=member.session_id, status=ExamStatus.PUBLISHED).first()
    if exam is None:
        raise NotFound("No exam is available")
    return exam


def _attempt_of(exam: Exam, member: SessionMember) -> ExamAttempt | None:
    return ExamAttempt.objects.filter(exam=exam, session_member=member).first()


def _state(exam: Exam, attempt: ExamAttempt | None, now) -> str:
    if attempt is not None:
        return "submitted" if attempt.submitted_at else "in_progress"
    if now < exam.starts_at:
        return "not_open"
    if now >= exam.ends_at:
        return "missed"
    return "ready"


def student_view(member: SessionMember) -> dict:
    """Everything the exam home page shows. Tasks (and check rules never) appear only once
    the student has started; tick status only after submit."""
    exam = _published_exam(member)
    auto_submit_due(exam, member=member)
    now = timezone.now()
    attempt = _attempt_of(exam, member)
    state = _state(exam, attempt, now)
    tasks = []
    if attempt is not None:
        by_task = {r.task_id: r for r in attempt.results.all()} if attempt.submitted_at else {}
        for t in exam.tasks.all():
            row = {
                "id": t.pk,
                "position": t.position,
                "title": t.title,
                "instructions": t.instructions,
                "points": t.points,
                "passed": None,
            }
            if t.pk in by_task:
                row["passed"] = by_task[t.pk].passed
            tasks.append(row)
    deadline = attempt.deadline_at if attempt else None
    remaining = None
    if state == "in_progress":
        remaining = max(0, int((deadline - now).total_seconds()))
    return {
        "state": state,
        "instructions": exam.instructions,
        "starts_at": exam.starts_at,
        "ends_at": exam.ends_at,
        "duration_minutes": exam.duration_minutes,
        "server_time": now,
        "started_at": attempt.started_at if attempt else None,
        "deadline_at": deadline,
        "submitted_at": attempt.submitted_at if attempt else None,
        "auto_submitted": attempt.auto_submitted if attempt else False,
        "remaining_seconds": remaining,
        "results_published": exam.results_published,
        "tasks": tasks,
    }


def clock_for(member: SessionMember) -> dict | None:
    """Small payload for the top bar countdown (session/me)."""
    exam = Exam.objects.filter(session_id=member.session_id, status=ExamStatus.PUBLISHED).first()
    if exam is None:
        return None
    attempt = _attempt_of(exam, member)
    now = timezone.now()
    state = _state(exam, attempt, now)
    if state == "in_progress" and attempt.deadline_at <= now:
        auto_submit_due(exam, member=member)
        attempt = _attempt_of(exam, member)
        state = _state(exam, attempt, now)
    deadline = attempt.deadline_at if attempt else None
    return {
        "state": state,
        "starts_at": exam.starts_at,
        "ends_at": exam.ends_at,
        "deadline_at": deadline,
        "server_time": now,
        "remaining_seconds": (
            max(0, int((deadline - now).total_seconds())) if state == "in_progress" else None
        ),
    }


def start_exam(member: SessionMember) -> dict:
    with transaction.atomic():
        Session.objects.select_for_update(no_key=True).get(pk=member.session_id)
        m = (
            SessionMember.objects.select_for_update(of=("self",))
            .select_related("session__lab_class", "bank", "user")
            .get(pk=member.pk)
        )
        exam = (
            Exam.objects.select_for_update(of=("self",))
            .filter(session_id=m.session_id, status=ExamStatus.PUBLISHED)
            .first()
        )
        if exam is None:
            raise NotFound("No exam is available")
        if m.session.status != SessionStatus.ACTIVE:
            raise Conflict("The session is not active")
        if m.bank_id is None:
            raise Conflict("You are not placed in a bank yet")
        existing = _attempt_of(exam, m)
        if existing is None:
            now = timezone.now()
            if now < exam.starts_at:
                raise Conflict("The exam has not started yet")
            if now >= exam.ends_at:
                raise Conflict("The exam time window is over")
            seed.ensure_member_seed(exam, m)
            deadline = min(exam.ends_at, now + timedelta(minutes=exam.duration_minutes))
            attempt = ExamAttempt.objects.create(
                exam=exam, session_member=m, started_at=now, deadline_at=deadline
            )
            _audit(
                m.user,
                "student",
                "exam.started",
                m.session,
                ("exam_attempt", attempt.pk),
                after={"deadline_at": deadline.isoformat()},
                bank_id=m.bank_id,
            )
    return student_view(member)


def submit_exam(member: SessionMember) -> dict:
    exam = _published_exam(member)
    attempt = _attempt_of(exam, member)
    if attempt is None:
        raise Conflict("Press Start before submitting")
    if attempt.submitted_at is not None:
        raise Conflict("You already submitted the exam")
    _finalize(attempt, auto=False, actor=member.user, role="student")
    return student_view(member)


def student_result(member: SessionMember) -> dict:
    exam = _published_exam(member)
    auto_submit_due(exam, member=member)
    attempt = _attempt_of(exam, member)
    if attempt is None or attempt.submitted_at is None:
        raise Conflict("Results are available after you submit")
    if not exam.results_published:
        raise Conflict("Results have not been published yet")
    rows = [
        {
            "task_id": r.task_id,
            "title": r.task.title,
            "max_points": r.task.points,
            "passed": r.passed,
            "points": r.final_points,
            "adjusted": r.adjusted_points is not None,
            "details": r.details,
        }
        for r in attempt.results.select_related("task")
    ]
    return {
        "score": attempt.score,
        "max_score": sum((r["max_points"] for r in rows), ZERO),
        "submitted_at": attempt.submitted_at,
        "auto_submitted": attempt.auto_submitted,
        "tasks": rows,
    }


# --------------------------------------------------------------------------- instructor: grading


def _member_status(attempt: ExamAttempt | None) -> str:
    if attempt is None:
        return "not_started"
    return "submitted" if attempt.submitted_at else "in_progress"


def results(actor, session_id) -> dict:
    session = _exam_session(actor, session_id, write=False)
    exam = _exam_of(session)
    if exam.status != ExamStatus.PUBLISHED:
        raise Conflict("The exam is not published yet")
    auto_submit_due(exam)
    tasks = list(exam.tasks.all())
    max_score = sum((t.points for t in tasks), ZERO)
    attempts = {
        a.session_member_id: a
        for a in ExamAttempt.objects.filter(exam=exam).prefetch_related("results")
    }
    rows = []
    members = SessionMember.objects.filter(session=session).select_related("user")
    for m in members.order_by("user__full_name", "user__username"):
        a = attempts.get(m.pk)
        by_task = {r.task_id: r for r in a.results.all()} if a else {}
        rows.append(
            {
                "member_id": m.pk,
                "username": m.user.username,
                "full_name": m.user.full_name or m.user.username,
                "status": _member_status(a),
                "started_at": a.started_at if a else None,
                "submitted_at": a.submitted_at if a else None,
                "auto_submitted": a.auto_submitted if a else False,
                "score": a.score if a else None,
                "tasks": [
                    {
                        "result_id": by_task[t.pk].pk,
                        "task_id": t.pk,
                        "title": t.title,
                        "max_points": t.points,
                        "passed": by_task[t.pk].passed,
                        "auto_points": by_task[t.pk].points,
                        "adjusted_points": by_task[t.pk].adjusted_points,
                        "points": by_task[t.pk].final_points,
                        "details": by_task[t.pk].details,
                    }
                    for t in tasks
                    if t.pk in by_task
                ],
            }
        )
    return {
        "results_published": exam.results_published,
        "max_score": max_score,
        "students": rows,
    }


@transaction.atomic
def adjust_result(actor, session_id, result_id, adjusted_points) -> ExamTaskResult:
    """Manual grade for one task; `None` clears the adjustment (back to the auto-check)."""
    session = _exam_session(actor, session_id, write=True)
    exam = _exam_of(session)
    result = (
        ExamTaskResult.objects.select_for_update(of=("self",))
        .select_related("task", "attempt")
        .filter(pk=result_id, task__exam=exam)
        .first()
    )
    if result is None:
        raise NotFound("Result not found")
    new = None if adjusted_points is None else _points(adjusted_points, "Points", allow_zero=True)
    if new is not None and new > result.task.points:
        raise ValidationFailed("Points cannot exceed the task's maximum")
    before = {
        "adjusted_points": str(result.adjusted_points)
        if result.adjusted_points is not None
        else None
    }
    result.adjusted_points = new
    result.adjusted_by = actor if new is not None else None
    result.adjusted_at = timezone.now() if new is not None else None
    result.save(update_fields=["adjusted_points", "adjusted_by", "adjusted_at", "updated_at"])
    attempt = ExamAttempt.objects.select_for_update(of=("self",)).get(pk=result.attempt_id)
    attempt.score = _final_score(attempt)
    attempt.save(update_fields=["score", "updated_at"])
    _audit(
        actor,
        actor.platform_role,
        "exam.result_adjusted",
        session,
        ("exam_task_result", result.pk),
        before=before,
        after={
            "adjusted_points": str(new) if new is not None else None,
            "score": str(attempt.score),
        },
    )
    return result


@transaction.atomic
def publish_results(actor, session_id) -> Exam:
    session = _exam_session(actor, session_id, write=True)
    exam = _exam_of(session, lock=True)
    if exam.status != ExamStatus.PUBLISHED:
        raise Conflict("The exam is not published yet")
    if exam.results_published:
        raise Conflict("Results are already published")
    auto_submit_due(exam)
    if ExamAttempt.objects.filter(exam=exam, submitted_at__isnull=True).exists():
        raise Conflict("Some students are still working; publish after they submit")
    exam.results_published, exam.results_published_at = True, timezone.now()
    exam.save(update_fields=["results_published", "results_published_at", "updated_at"])
    _audit(actor, actor.platform_role, "exam.results_published", session, ("exam", exam.pk),
           after={"results_published": True})  # fmt: skip
    return exam
