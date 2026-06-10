import json
from decimal import Decimal

import pytest

from campusops.imports.csv_loader import normalize_header, read_csv_rows, required_fields, write_csv_rows
from campusops.imports.jobs import ImportJobRunner
from campusops.imports.validation import ImportIssue, ImportResult
from campusops.students.registry import StudentRegistry


def test_normalize_header_handles_messy_export_names():
    assert normalize_header(" Student ID ") == "student_id"
    assert normalize_header("Full-Name") == "full_name"
    assert normalize_header("Programme.Name") == "programme_name"
    assert normalize_header("Fee/Account") == "fee_account"


def test_read_csv_rows_normalizes_headers_and_trims_values():
    csv_text = """ Student ID , Full Name , Programme , Year
 s001 , Ann Wanjiku , Information Technology , 2
"""

    rows = read_csv_rows(csv_text)

    assert rows == [
        {
            "student_id": "s001",
            "full_name": "Ann Wanjiku",
            "programme": "Information Technology",
            "year": "2",
        }
    ]


def test_required_fields_returns_missing_normalized_names():
    row = {"student_id": "S001", "full_name": "", "year": "2"}

    assert required_fields(row, ["student id", "full name", "programme"]) == ["full_name", "programme"]


def test_write_csv_rows_roundtrip(tmp_path):
    path = tmp_path / "out.csv"

    write_csv_rows(path, [{"student_id": "S001", "amount": "100"}, {"student_id": "S002", "amount": "200"}])
    rows = read_csv_rows(path)

    assert rows == [
        {"student_id": "S001", "amount": "100"},
        {"student_id": "S002", "amount": "200"},
    ]


def test_import_issue_and_result_summary_are_serializable():
    issue = ImportIssue(
        row_number=2,
        code=" Missing.Required ",
        message=" Missing name ",
        row={"student_id": "S001"},
    )
    result = ImportResult(job_name=" Student Import ")
    result.add_accept()
    result.add_issue(issue)

    assert result.to_dict() == {
        "job_name": "student_import",
        "accepted": 1,
        "rejected": 1,
        "total_rows": 2,
        "ok": False,
        "issues": [
            {
                "row_number": 2,
                "code": "missing_required",
                "message": "Missing name",
                "row": {"student_id": "S001"},
            }
        ],
        "metadata": {},
    }


def test_student_import_accepts_valid_rows_and_rejects_bad_rows(tmp_path):
    csv_text = """student id,full name,cohort,programme,year,status,tags
s001,Ann Wanjiku,BIT-2026,Information Technology,2,active,boarder|scholarship
s002,,BIT-2026,Information Technology,2,active,
s001,Duplicate Student,BIT-2026,Information Technology,2,active,
"""
    registry = StudentRegistry()
    reject_path = tmp_path / "student_rejects.json"

    result = ImportJobRunner().import_students(csv_text, registry, actor="registrar", reject_path=reject_path)

    assert result.accepted == 1
    assert result.rejected == 2
    assert len(registry) == 1
    assert registry.get("S001").tags == ("boarder", "scholarship")
    assert [issue.code for issue in result.issues] == ["missing_required_field", "valueerror"]

    rejects = json.loads(reject_path.read_text(encoding="utf-8"))
    assert rejects[0]["row_number"] == 3
    assert rejects[1]["message"] == "student already exists: S001"


def test_student_import_audits_each_accepted_student():
    csv_text = """student_id,full_name,cohort,programme,year
s001,Ann Wanjiku,BIT-2026,Information Technology,2
s002,Brian Otieno,BIT-2026,Information Technology,2
"""
    registry = StudentRegistry()

    result = ImportJobRunner().import_students(csv_text, registry, actor="registrar")

    assert result.ok is True
    assert result.accepted == 2
    assert [event.event_type for event in registry.audit.all_events()] == ["student_created", "student_created"]


def test_fee_schedule_import_builds_items_and_rejects_invalid_amount(tmp_path):
    csv_text = """item code,description,amount,account code,years,programmes,required
tuition,Tuition Fee,12000,tuition,1|2|3,Information Technology,true
lab-fee,Lab Fee,bad,lab,2,Information Technology,true
library,Library Fee,500,library,,,false
"""
    reject_path = tmp_path / "fee_rejects.csv"

    schedule, result = ImportJobRunner().build_fee_schedule(
        csv_text,
        schedule_id="regular.2026",
        title="Regular 2026",
        reject_path=reject_path,
    )

    assert result.accepted == 2
    assert result.rejected == 1
    assert [item.item_code for item in schedule.items] == ["tuition", "library"]
    assert schedule.total_for(type("StudentLike", (), {"year": 2, "programme": "Information Technology"})()) == Decimal("12500.00")

    rejects = read_csv_rows(reject_path)
    assert rejects[0]["code"] == "invalidoperation"


def test_fee_schedule_import_rejects_missing_required_columns():
    csv_text = """item_code,description,amount
tuition,Tuition Fee,12000
"""
    schedule, result = ImportJobRunner().build_fee_schedule(
        csv_text,
        schedule_id="regular",
        title="Regular Fees",
    )

    assert result.accepted == 0
    assert result.rejected == 1
    assert result.issues[0].message == "Missing required field(s): account_code"
    assert schedule.items == ()


def test_fee_schedule_import_rejects_duplicate_item_codes():
    csv_text = """item_code,description,amount,account_code
lab-fee,Lab Fee,100,lab
lab.fee,Lab Fee Duplicate,200,lab
"""

    with pytest.raises(ValueError, match="duplicate item codes"):
        ImportJobRunner().build_fee_schedule(
            csv_text,
            schedule_id="regular",
            title="Regular Fees",
        )
