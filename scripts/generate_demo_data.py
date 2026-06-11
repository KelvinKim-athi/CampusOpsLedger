from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from campusops.attendance.records import ClassSession
from campusops.attendance.tracker import AttendanceTracker
from campusops.ledger.transactions import StudentLedger
from campusops.reports.summary import combined_student_dashboard, write_json_report
from campusops.rooms.allocation import RoomDirectory
from campusops.rooms.models import LAB, LECTURE, Room, RoomBooking
from campusops.security.access import AccessManager
from campusops.security.identity import Role, StaffUser
from campusops.students.models import Student
from campusops.students.registry import StudentRegistry


def build_students() -> StudentRegistry:
    registry = StudentRegistry()
    registry.add(Student("S001", "Ann Wanjiku", "BIT-2026", "Information Technology", 2, tags=("boarder",)))
    registry.add(Student("S002", "Brian Otieno", "BIT-2026", "Information Technology", 2, tags=("sports",)))
    registry.add(Student("S003", "Caleb Mwangi", "BCS-2026", "Computer Science", 1))
    return registry


def build_ledger() -> StudentLedger:
    ledger = StudentLedger()
    ledger.charge_fee(student_id="S001", account_code="tuition", term="2026-T1", amount="12000", description="Tuition")
    ledger.record_payment(student_id="S001", term="2026-T1", amount="5000", description="Payment")
    ledger.charge_fee(student_id="S002", account_code="tuition", term="2026-T1", amount="12000", description="Tuition")
    ledger.apply_waiver(student_id="S002", term="2026-T1", amount="2000", description="Sports bursary")
    ledger.charge_fee(student_id="S003", account_code="tuition", term="2026-T1", amount="10000", description="Tuition")
    return ledger


def build_attendance() -> AttendanceTracker:
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
    tracker.mark_arrival(session_id="ICT101-W2", student_id="S001", arrived_at="2026-02-08T05:18:00+00:00")
    tracker.fill_absences(session_id="ICT101-W1", enrolled_student_ids=["S001", "S002"])
    tracker.fill_absences(session_id="ICT101-W2", enrolled_student_ids=["S001", "S002"])
    return tracker


def build_rooms() -> RoomDirectory:
    directory = RoomDirectory(
        rooms=[
            Room("LAB-2", "Computer Lab Two", 40, kind=LAB, building="Science Block", equipment=("projector", "computers")),
            Room("LH-1", "Lecture Hall One", 120, kind=LECTURE, building="Main Block", equipment=("projector",)),
            Room("SR-1", "Seminar Room", 25, kind=LECTURE, building="Library", equipment=("whiteboard",)),
        ]
    )
    directory.book(
        RoomBooking(
            "ICT101-W1",
            "LAB-2",
            "ICT 101 Practical",
            "2026-02-01T08:00:00+03:00",
            "2026-02-01T10:00:00+03:00",
            35,
            "Dr Maina",
            course_code="ICT101",
        )
    )
    return directory


def build_access() -> AccessManager:
    manager = AccessManager()
    manager.add_role(Role("registrar", "Registrar", permissions=("students.read", "students.write", "reports.view")))
    manager.add_role(Role("finance-officer", "Finance Officer", permissions=("ledger.read", "ledger.write", "reports.view")))
    manager.add_role(Role("lecturer", "Lecturer", permissions=("attendance.write", "assessments.read")))
    manager.add_user(StaffUser("alice.admin", "Alice Admin", roles=("registrar",), department="Registry"))
    manager.add_user(StaffUser("bob.finance", "Bob Finance", roles=("finance-officer",), department="Accounts"))
    return manager


def generate_demo_data(output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    registry = build_students()
    ledger = build_ledger()
    tracker = build_attendance()
    rooms = build_rooms()
    access = build_access()

    paths = {
        "students": output / "students.json",
        "ledger": output / "ledger.json",
        "attendance": output / "attendance.json",
        "rooms": output / "rooms.json",
        "access": output / "access.json",
        "dashboard": output / "dashboard.json",
        "manifest": output / "manifest.json",
    }

    registry.save_json(paths["students"])
    ledger.save_json(paths["ledger"])
    tracker.save_json(paths["attendance"])
    rooms.save_json(paths["rooms"])
    access.save_json(paths["access"])

    dashboard = combined_student_dashboard(registry=registry, ledger=ledger, tracker=tracker)
    write_json_report(paths["dashboard"], dashboard)

    manifest = {
        "dataset": "campusops-demo",
        "files": {name: path.name for name, path in paths.items() if name != "manifest"},
        "student_count": len(registry),
        "room_count": len(rooms),
        "staff_count": len(access),
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    return {name: str(path) for name, path in paths.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic CampusOps demo data.")
    parser.add_argument("--output-dir", default="data/samples/generated", help="Directory where demo JSON files are written.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = generate_demo_data(args.output_dir)
    print(json.dumps(paths, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
