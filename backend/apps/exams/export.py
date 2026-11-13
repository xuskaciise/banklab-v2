"""Exam results as a neutral `Report`, rendered by the shared Excel / PDF helpers (1.12)."""

from django.utils import timezone

from apps.lab.models import Bank
from apps.reports.ctx import branch_of
from apps.reports.doc import Column, Report, Section
from apps.reports.pdf import render_report
from apps.reports.xlsx import render_xlsx

from . import services

STATUS = {"not_started": "Not started", "in_progress": "In progress", "submitted": "Submitted"}


def build_report(actor, session_id) -> tuple[Report, object]:
    data = services.results(actor, session_id)
    session = services._exam_session(actor, session_id, write=False)
    bank = Bank.objects.filter(session=session).order_by("group_no").first()
    max_score = data["max_score"]
    students = Section(
        "Scores",
        [
            Column("student", "Student", weight=2),
            Column("username", "Username"),
            Column("status", "Status"),
            Column("submitted_at", "Submitted", weight=1.4),
            Column("score", "Score", "money"),
            Column("max_score", "Out of", "money"),
        ],
    )
    detail = Section(
        "Task details",
        [
            Column("student", "Student", weight=2),
            Column("task", "Task", weight=2),
            Column("passed", "Auto-check"),
            Column("auto_points", "Auto points", "money"),
            Column("points", "Final points", "money"),
            Column("max_points", "Max", "money"),
        ],
    )
    for s in data["students"]:
        students.rows.append(
            {
                "student": s["full_name"],
                "username": s["username"],
                "status": STATUS[s["status"]] + (" (auto)" if s["auto_submitted"] else ""),
                "submitted_at": s["submitted_at"].strftime("%Y-%m-%d %H:%M")
                if s["submitted_at"]
                else "",
                "score": s["score"],
                "max_score": max_score,
            }
        )
        for t in s["tasks"]:
            detail.rows.append(
                {
                    "student": s["full_name"],
                    "task": t["title"],
                    "passed": "Passed" if t["passed"] else "Failed",
                    "auto_points": t["auto_points"],
                    "points": t["points"],
                    "max_points": t["max_points"],
                }
            )
    report = Report(
        slug="exam-results",
        title=f"Exam results - {session.name}",
        bank_name=bank.name if bank else session.name,
        period=f"{session.lab_class.name}",
        generated_at=timezone.now(),
        generated_by=actor.full_name or actor.username,
        summary=[("Students", len(data["students"]), "int"), ("Maximum score", max_score, "money")],
        sections=[students, detail],
        landscape=True,
    )
    return report, bank


def xlsx_bytes(actor, session_id) -> tuple[bytes, str]:
    report, _ = build_report(actor, session_id)
    return render_xlsx(report), report.filename


def pdf_bytes(actor, session_id) -> tuple[bytes, str]:
    report, bank = build_report(actor, session_id)
    return render_report(report, branch_of(bank) if bank else None), report.filename
