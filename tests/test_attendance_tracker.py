import pytest

from campusops.attendance.policies import AttendancePolicy
from campusops.attendance.records import ABSENT, EXCUSED, LATE, PRESENT, AttendanceMark, ClassSession
from campusops.attendance.tracker import AttendanceTracker


def make_session():
    return ClassSession(
        session_id=" ICT-101.Week-1 ",
        course_code=" ict 101 ",
        cohort="BIT-2026",
        room_code=" lab-2 ",
        starts_at="2026-02-01T08:00:00+03:00",
        ends_at="2026-02-01T10:00:00+03:00",
        lecturer="Dr Maina",
    )


def test_class_session_normalizes_fields_and_utc_times():
    session = make_session()

    assert session.session_id == "ict_101_week_1"
    assert session.course_code == "ICT_101"
    assert session.room_code == "LAB_2"
    assert session.starts_at == "2026-02-01T05:00:00+00:00"
    assert session.ends_at == "2026-02-01T07:00:00+00:00"


def test_class_session_rejects_end_before_start():
    with pytest.raises(ValueError, match="end must be after start"):
        ClassSession(
            session_id="bad",
            course_code="ICT101",
            cohort="BIT",
            room_code="LAB",
            starts_at="2026-02-01T08:00:00+00:00",
            ends_at="2026-02-01T07:59:00+00:00",
            lecturer="Dr Maina",
        )


def test_attendance_mark_normalizes_and_rejects_invalid_late_minutes():
    mark = AttendanceMark(
        mark_id=" Mark.1 ",
        session_id=" ICT-101.Week-1 ",
        student_id=" s001 ",
        status=" late ",
        marked_at="2026-02-01T05:15:00+00:00",
        minutes_late=15,
        source=" QR Scanner ",
    )

    assert mark.mark_id == "mark_1"
    assert mark.session_id == "ict_101_week_1"
    assert mark.student_id == "S001"
    assert mark.status == LATE
    assert mark.source == "qr_scanner"

    with pytest.raises(ValueError, match="only late marks"):
        AttendanceMark("M2", "S1", "S001", PRESENT, minutes_late=5)


def test_policy_classifies_arrivals_against_session_start():
    session = make_session()
    policy = AttendancePolicy(grace_minutes=10, absent_after_minutes=40)

    assert policy.classify_arrival(session, "2026-02-01T05:09:00+00:00") == (PRESENT, 0)
    assert policy.classify_arrival(session, "2026-02-01T05:20:00+00:00") == (LATE, 20)
    assert policy.classify_arrival(session, "2026-02-01T05:40:00+00:00") == (ABSENT, 0)


def test_tracker_adds_session_and_writes_audit_event():
    tracker = AttendanceTracker()
    tracker.add_session(make_session(), actor="timetable")

    assert len(tracker) == 1
    assert tracker.audit.all_events()[0].event_type == "attendance_session_created"
    assert tracker.audit.all_events()[0].metadata["course_code"] == "ICT_101"


def test_mark_arrival_prevents_duplicate_student_mark_unless_replaced_by_excuse():
    tracker = AttendanceTracker()
    tracker.add_session(make_session())

    tracker.mark_arrival(
        session_id="ict-101.week-1",
        student_id="S001",
        arrived_at="2026-02-01T05:04:00+00:00",
        actor="scanner",
    )

    with pytest.raises(ValueError, match="already marked"):
        tracker.mark_arrival(
            session_id="ict-101.week-1",
            student_id="S001",
            arrived_at="2026-02-01T05:20:00+00:00",
            actor="scanner",
        )

    excused = tracker.excuse_absence(
        session_id="ict-101.week-1",
        student_id="S001",
        reason="medical note",
        actor="office",
    )

    assert excused.status == EXCUSED
    assert tracker.session_marks("ict-101.week-1")[0].reason == "medical note"


def test_missing_students_and_fill_absences_are_sorted():
    tracker = AttendanceTracker()
    tracker.add_session(make_session())
    tracker.mark_arrival(session_id="ict-101.week-1", student_id="S002", arrived_at="2026-02-01T05:02:00+00:00")

    assert tracker.missing_students("ict-101.week-1", ["s003", "s001", "s002"]) == ["S001", "S003"]

    created = tracker.fill_absences(
        session_id="ict-101.week-1",
        enrolled_student_ids=["s003", "s001", "s002"],
        actor="rollcall",
    )

    assert [mark.student_id for mark in created] == ["S001", "S003"]
    assert [mark.status for mark in tracker.session_marks("ict-101.week-1")] == [ABSENT, PRESENT, ABSENT]


def test_student_summary_uses_policy_credit():
    tracker = AttendanceTracker(policy=AttendancePolicy(minimum_required_fraction=0.7))
    session_one = make_session()
    session_two = ClassSession(
        session_id="ICT-101.week-2",
        course_code="ICT101",
        cohort="BIT-2026",
        room_code="LAB2",
        starts_at="2026-02-08T05:00:00+00:00",
        ends_at="2026-02-08T07:00:00+00:00",
        lecturer="Dr Maina",
    )
    tracker.add_session(session_one)
    tracker.add_session(session_two)

    tracker.mark_arrival(session_id="ict-101.week-1", student_id="S001", arrived_at="2026-02-01T05:00:00+00:00")
    tracker.mark_arrival(session_id="ict-101.week-2", student_id="S001", arrived_at="2026-02-08T05:20:00+00:00")

    summary = tracker.student_summary("s001")

    assert summary["counts"] == {"present": 1, "late": 1, "absent": 0, "excused": 0}
    assert summary["attendance_credit"] == 1.5
    assert summary["attendance_fraction"] == 0.75
    assert summary["meets_requirement"] is True


def test_course_summary_counts_sessions_and_marks():
    tracker = AttendanceTracker()
    tracker.add_session(make_session())
    tracker.mark_arrival(session_id="ict-101.week-1", student_id="S001", arrived_at="2026-02-01T05:00:00+00:00")
    tracker.fill_absences(session_id="ict-101.week-1", enrolled_student_ids=["S001", "S002"])

    summary = tracker.course_summary("ict 101")

    assert summary == {
        "course_code": "ICT_101",
        "session_count": 1,
        "mark_count": 2,
        "counts": {"present": 1, "late": 0, "absent": 1, "excused": 0},
    }


def test_attendance_tracker_json_roundtrip(tmp_path):
    tracker = AttendanceTracker()
    tracker.add_session(make_session())
    tracker.mark_arrival(session_id="ict-101.week-1", student_id="S001", arrived_at="2026-02-01T05:20:00+00:00")

    path = tmp_path / "attendance.json"
    tracker.save_json(path)
    loaded = AttendanceTracker.load_json(path)

    assert len(loaded) == 1
    assert loaded.session_marks("ict-101.week-1")[0].status == LATE
    assert loaded.student_summary("S001")["attendance_fraction"] == 0.5