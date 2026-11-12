"""Test helper: give an exam session an open exam so student writes pass the exam guard."""

from datetime import timedelta

from django.utils import timezone

from apps.exams.models import Exam, ExamAttempt
from apps.lab.models import SessionMember


def open_exam_window(session):
    now = timezone.now()
    exam = Exam.objects.create(
        session=session,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=8),
        duration_minutes=480,
        status="published",
        published_at=now,
    )
    for m in SessionMember.objects.filter(session=session):
        ExamAttempt.objects.create(
            exam=exam,
            session_member=m,
            started_at=now - timedelta(minutes=30),
            deadline_at=now + timedelta(hours=8),
        )
    return exam
