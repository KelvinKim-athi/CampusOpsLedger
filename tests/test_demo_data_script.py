import json
import runpy
from pathlib import Path

from campusops.attendance.tracker import AttendanceTracker
from campusops.ledger.transactions import StudentLedger
from campusops.rooms.allocation import RoomDirectory
from campusops.security.access import AccessManager
from campusops.students.registry import StudentRegistry


def load_demo_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_demo_data.py"
    return runpy.run_path(str(path))


def test_generate_demo_data_writes_expected_files(tmp_path):
    module = load_demo_module()
    paths = module["generate_demo_data"](tmp_path)

    assert sorted(paths) == ["access", "attendance", "dashboard", "ledger", "manifest", "rooms", "students"]
    for file_path in paths.values():
        assert Path(file_path).exists()

    manifest = json.loads(Path(paths["manifest"]).read_text(encoding="utf-8"))
    assert manifest["dataset"] == "campusops-demo"
    assert manifest["student_count"] == 3
    assert manifest["room_count"] == 3
    assert manifest["staff_count"] == 2


def test_generated_demo_files_load_back_into_domain_objects(tmp_path):
    module = load_demo_module()
    paths = module["generate_demo_data"](tmp_path)

    registry = StudentRegistry.load_json(paths["students"])
    ledger = StudentLedger.load_json(paths["ledger"])
    tracker = AttendanceTracker.load_json(paths["attendance"])
    rooms = RoomDirectory.load_json(paths["rooms"])
    access = AccessManager.load_json(paths["access"])

    assert len(registry) == 3
    assert str(ledger.balance_for_student("S001")) == "7000.00"
    assert tracker.student_summary("S002")["attendance_fraction"] == 0.0
    assert rooms.bookings_for_room("LAB-2")[0].course_code == "ICT101"
    assert access.can("bob.finance", "ledger.write") is True


def test_demo_script_main_prints_generated_manifest_path(tmp_path, capsys):
    module = load_demo_module()

    exit_code = module["main"](["--output-dir", str(tmp_path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert Path(output["manifest"]).exists()
    assert Path(output["dashboard"]).exists()
