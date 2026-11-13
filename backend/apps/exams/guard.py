"""Exam write guard: the one place that blocks student writes outside the exam window.

Called from the central write guards (`banking.services._lock_session`, which every member
write service uses, and `rbac.context.lock_writable_session`). It raises a 409 `LedgerError`
with an `exam_*` code when, in an exam session with a configured exam, the student

- writes before the exam is published or before `starts_at`   (exam_not_open)
- has not pressed Start                                       (exam_not_started)
- is past their personal deadline                             (exam_time_over)
- already submitted                                           (exam_submitted)

Instructors never reach it (they do not post). An exam session with no Exam row rejects
student writes too (fail closed).
Must stay import-light: it is imported by `apps.banking.services`.
"""

from django.utils import timezone

from apps.ledger.services import LedgerError

from .models import Exam, ExamAttempt, ExamStatus


def _deny(code: str, message: str) -> LedgerError:
    return LedgerError(code, message, status=409)


def check_write_allowed(session, member, now=None) -> None:
    if session.kind != "exam":
        return
    exam = Exam.objects.filter(session_id=session.pk).first()
    if exam is None:  # fail closed: an exam session without an exam accepts no student writes
        raise _deny("exam_not_open", "The exam has not opened yet")
    now = now or timezone.now()
    if exam.status != ExamStatus.PUBLISHED or now < exam.starts_at:
        raise _deny("exam_not_open", "The exam has not opened yet")
    attempt = ExamAttempt.objects.filter(exam=exam, session_member_id=member.pk).first()
    if attempt is None:
        raise _deny("exam_not_started", "Press Start on the exam page before working")
    if attempt.submitted_at is not None:
        raise _deny("exam_submitted", "You already submitted the exam (read-only)")
    if now >= attempt.deadline_at:
        raise _deny("exam_time_over", "Your exam time is over (read-only)")
