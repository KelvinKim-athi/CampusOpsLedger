import csv
import json
from decimal import Decimal

from campusops.assessments.attempts import AssessmentBook
from campusops.assessments.models import Assessment, AssessmentAttempt, Question
from campusops.attendance.records import ClassSession
from campusops.attendance.tracker import AttendanceTracker
from campusops.ledger.transactions import StudentLedger
from campusops.reports.summary import (
    assessment_score_report,
    attendance_risk_report,
    combined_student_dashboard,
    fee_balance_report,
    student_registry_summary,
    write_csv_report,
    write_json_report,
)
from campusops.students.models import Student
from campusops.students.registry import StudentRegistry


def make_registry():
    registry = StudentRegistry()
    registry.add(Student("S002", "Brian Otieno", "BIT-2026", "Information Technology", 2))
    registry.add(Student("S001", "Ann Wanjiku", "BIT-2026", "Information Technology", 2))
    registry.add(Student("S003", "Caleb Mwangi", "BCS-2026", "Computer Science", 1))
    registry.suspend("S003", actor="dean", reason="deferred")
    return registry


def make_assessment_book():
    assessment = Assessment(
        assessment_id="quiz-1",
        title="Quiz One",
        programme="Information Technology",
        published=True,
        questions=(
            Question("Q1", "Two plus two", "math", "4", points=2),
            Question("Q2", "HTTP success", "web", "200", points=1),
        ),
    )
    book = AssessmentBook(assessments=[assessment])
    book.submit_attempt(AssessmentAttempt("A2", "S002", "quiz-1", {"q1": "4", "q2": "200"}))
    book.submit_attempt(AssessmentAttempt("A1", "S001", "quiz-1", {"q1": "4", "q2": "wrong"}))
    return book


def make_ledger():
    ledger = StudentLedger()
    ledger.charge_fee(student_id="S001", account_code="tuition", term="2026-T1", amount="1000", description="Tuition")
    ledger.record_payment(student_id="S001", term="2026-T1", amount="250", description="Payment")
    ledger.charge_fee(student_id="S002", account_code="tuition", term="2026-T1", amount="500", description="Tuition")
    ledger.record_payment(student_id="S003", term="2026-T1", amount="100", description="Overpayment")
    return ledger


def make_tracker():
    tracker = AttendanceTracker()
    tracker.add_session(
        ClassSession(
            session_id="ICT101-W1",
            course_code="ICT101",
            cohort="BIT-2026",
            room_code="LAB2",
            starts_at="2026-02-01T08:00:00+03:00",
            ends_at="2026-02-01T10:00:00+03:00",
            lecturer="Dr Maina",
        )
    )
    tracker.add_session(
        ClassSession(
            session_id="ICT101-W2",
            course_code="ICT101",
            cohort="BIT-2026",
            room_code="LAB2",
            starts_at="2026-02-08T08:00:00+03:00",
            ends_at="2026-02-08T10:00:00+03:00",
            lecturer="Dr Maina",
        )
    )
    tracker.mark_arrival(session_id="ICT101-W1", student_id="S001", arrived_at="2026-02-01T05:00:00+00:00")
    tracker.mark_arrival(session_id="ICT101-W2", student_id="S001", arrived_at="2026-02-08T05:20:00+00:00")
    tracker.fill_absences(session_id="ICT101-W1", enrolled_student_ids=["S001", "S002"])
    tracker.fill_absences(session_id="ICT101-W2", enrolled_student_ids=["S001", "S002"])
    return tracker


def test_student_registry_summary_groups_status_cohort_programme_and_year():
    summary = student_registry_summary(make_registry())

    assert summary == {
        "student_count": 3,
        "by_status": {"active": 2, "suspended": 1},
        "by_cohort": {"BCS-2026": 1, "BIT-2026": 2},
        "by_programme": {"Computer Science": 1, "Information Technology": 2},
        "by_year": {"1": 1, "2": 2},
    }


def test_assessment_score_report_exports_sorted_leaderboard_and_counts():
    report = assessment_score_report(make_assessment_book(), "quiz-1")

    assert report["assessment_id"] == "quiz_1"
    assert report["attempt_count"] == 2
    assert report["passed_count"] == 2
    assert report["failed_count"] == 0
    assert report["average_fraction"] == 0.833333
    assert [row["student_id"] for row in report["rows"]] == ["S002", "S001"]


def test_fee_balance_report_marks_owing_and_clear_students():
    report = fee_balance_report(make_ledger(), ["S002", "S001", "S003"])

    assert report["student_count"] == 3
    assert report["total_balance"] == "1150.00"
    assert report["rows"] == [
        {"student_id": "S001", "balance": "750.00", "status": "owing"},
        {"student_id": "S002", "balance": "500.00", "status": "owing"},
        {"student_id": "S003", "balance": "-100.00", "status": "clear"},
    ]


def test_attendance_risk_report_classifies_absence_risk():
    report = attendance_risk_report(make_tracker(), ["S001", "S002", "S003"])

    assert report["student_count"] == 3
    assert report["high_risk_count"] == 1
    assert report["watch_count"] == 0
    assert report["rows"][0]["student_id"] == "S001"
    assert report["rows"][0]["risk"] == "ok"
    assert report["rows"][1]["student_id"] == "S002"
    assert report["rows"][1]["risk"] == "high"
    assert report["rows"][2]["student_id"] == "S003"
    assert report["rows"][2]["risk"] == "no_records"


def test_combined_student_dashboard_joins_registry_fee_and_attendance():
    dashboard = combined_student_dashboard(
        registry=make_registry(),
        ledger=make_ledger(),
        tracker=make_tracker(),
    )

    assert dashboard["student_count"] == 3
    assert dashboard["rows"][0] == {
        "student_id": "S001",
        "full_name": "Ann Wanjiku",
        "cohort": "BIT-2026",
        "programme": "Information Technology",
        "status": "active",
        "fee_balance": "750.00",
        "fee_status": "owing",
        "attendance_fraction": 0.75,
        "attendance_risk": "ok",
        "attendance_sessions": 2,
    }


def test_combined_student_dashboard_accepts_selected_students_not_in_registry():
    dashboard = combined_student_dashboard(
        registry=make_registry(),
        ledger=make_ledger(),
        tracker=make_tracker(),
        student_ids=["S004"],
    )

    assert dashboard == {
        "student_count": 1,
        "rows": [
            {
                "student_id": "S004",
                "full_name": "",
                "cohort": "",
                "programme": "",
                "status": "",
                "fee_balance": "0.00",
                "fee_status": "clear",
                "attendance_fraction": 0.0,
                "attendance_risk": "no_records",
                "attendance_sessions": 0,
            }
        ],
    }


def test_write_json_report_roundtrip(tmp_path):
    path = tmp_path / "report.json"
    payload = {"b": 2, "a": {"x": 1}}

    write_json_report(path, payload)

    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert path.read_text(encoding="utf-8").splitlines()[1].strip() == '"a": {'


def test_write_csv_report_uses_discovered_field_order(tmp_path):
    path = tmp_path / "report.csv"
    rows = [{"student_id": "S001", "balance": "750.00"}, {"student_id": "S002", "risk": "high"}]

    write_csv_report(path, rows)

    with path.open(encoding="utf-8", newline="") as handle:
        loaded = list(csv.DictReader(handle))

    assert loaded == [
        {"student_id": "S001", "balance": "750.00", "risk": ""},
        {"student_id": "S002", "balance": "", "risk": "high"},
    ]


def test_write_csv_report_respects_explicit_field_order(tmp_path):
    path = tmp_path / "report.csv"
    rows = [{"student_id": "S001", "balance": Decimal("10.00"), "ignored": "x"}]

    write_csv_report(path, rows, fieldnames=["balance", "student_id"])

    assert path.read_text(encoding="utf-8").splitlines()[0] == "balance,student_id"
    with path.open(encoding="utf-8", newline="") as handle:
        loaded = list(csv.DictReader(handle))
    assert loaded == [{"balance": "10.00", "student_id": "S001"}]
