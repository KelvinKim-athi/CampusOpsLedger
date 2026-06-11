import json

from campusops.cli import build_parser, main
from campusops.ledger.transactions import StudentLedger
from campusops.rooms.allocation import RoomDirectory
from campusops.rooms.models import LAB, LECTURE, Room, RoomBooking
from campusops.students.models import Student
from campusops.students.registry import StudentRegistry


def test_build_parser_registers_expected_commands():
    parser = build_parser()
    help_text = parser.format_help()

    assert "import-students" in help_text
    assert "students-summary" in help_text
    assert "fee-balances" in help_text
    assert "rooms-available" in help_text


def test_students_summary_command_prints_registry_summary(tmp_path, capsys):
    registry = StudentRegistry()
    registry.add(Student("S001", "Ann Wanjiku", "BIT-2026", "Information Technology", 2))
    registry.add(Student("S002", "Brian Otieno", "BIT-2026", "Information Technology", 2))

    path = tmp_path / "students.json"
    registry.save_json(path)

    exit_code = main(["students-summary", "--students", str(path)])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["student_count"] == 2
    assert output["by_cohort"] == {"BIT-2026": 2}


def test_import_students_command_writes_registry_and_reject_report(tmp_path, capsys):
    csv_path = tmp_path / "students.csv"
    output_path = tmp_path / "registry.json"
    rejects_path = tmp_path / "rejects.json"
    csv_path.write_text(
        "student id,full name,cohort,programme,year\n"
        "s001,Ann Wanjiku,BIT-2026,Information Technology,2\n"
        "s002,,BIT-2026,Information Technology,2\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "import-students",
            "--csv",
            str(csv_path),
            "--output",
            str(output_path),
            "--rejects",
            str(rejects_path),
            "--actor",
            "registrar",
        ]
    )
    result = json.loads(capsys.readouterr().out)
    loaded = StudentRegistry.load_json(output_path)

    assert exit_code == 0
    assert result["accepted"] == 1
    assert result["rejected"] == 1
    assert len(loaded) == 1
    assert json.loads(rejects_path.read_text(encoding="utf-8"))[0]["code"] == "missing_required_field"


def test_fee_balances_command_prints_balance_report(tmp_path, capsys):
    ledger = StudentLedger()
    ledger.charge_fee(student_id="S001", account_code="tuition", term="2026-T1", amount="1000", description="Tuition")
    ledger.record_payment(student_id="S001", term="2026-T1", amount="250", description="Payment")

    path = tmp_path / "ledger.json"
    ledger.save_json(path)

    exit_code = main(["fee-balances", "--ledger", str(path), "--student-ids", "S001", "S002"])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["total_balance"] == "750.00"
    assert output["rows"][0] == {"student_id": "S001", "balance": "750.00", "status": "owing"}
    assert output["rows"][1] == {"student_id": "S002", "balance": "0.00", "status": "clear"}


def test_rooms_available_command_filters_busy_rooms(tmp_path, capsys):
    directory = RoomDirectory(
        rooms=[
            Room("LAB-2", "Computer Lab Two", 40, kind=LAB, equipment=("projector", "computers")),
            Room("LH-1", "Lecture Hall One", 120, kind=LECTURE, equipment=("projector",)),
        ]
    )
    directory.book(
        RoomBooking(
            "B1",
            "LAB-2",
            "Morning Lab",
            "2026-02-01T08:00:00Z",
            "2026-02-01T10:00:00Z",
            30,
            "Dr Maina",
        )
    )

    path = tmp_path / "rooms.json"
    directory.save_json(path)

    exit_code = main(
        [
            "rooms-available",
            "--rooms",
            str(path),
            "--starts-at",
            "2026-02-01T08:30:00Z",
            "--ends-at",
            "2026-02-01T09:00:00Z",
            "--size",
            "20",
            "--equipment",
            "projector",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["room_count"] == 1
    assert output["rooms"][0]["room_code"] == "LH_1"


def test_rooms_available_command_accepts_comma_separated_equipment(tmp_path, capsys):
    directory = RoomDirectory(
        rooms=[
            Room("LAB-2", "Computer Lab Two", 40, kind=LAB, equipment=("projector", "computers")),
            Room("LH-1", "Lecture Hall One", 120, kind=LECTURE, equipment=("projector",)),
        ]
    )
    path = tmp_path / "rooms.json"
    directory.save_json(path)

    exit_code = main(
        [
            "rooms-available",
            "--rooms",
            str(path),
            "--starts-at",
            "2026-02-01T08:30:00Z",
            "--ends-at",
            "2026-02-01T09:00:00Z",
            "--size",
            "20",
            "--equipment",
            "projector,computers",
            "--kind",
            "lab",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["room_count"] == 1
    assert output["rooms"][0]["room_code"] == "LAB_2"
