from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from campusops.imports.csv_loader import read_csv_rows, required_fields, write_csv_rows
from campusops.imports.validation import ImportIssue, ImportResult
from campusops.ledger.fees import FeeItem, FeeSchedule
from campusops.students.models import Student
from campusops.students.registry import StudentRegistry


class ImportJobRunner:
    def import_students(
        self,
        source: str | Path,
        registry: StudentRegistry,
        *,
        actor: str = "importer",
        reject_path: str | Path | None = None,
    ) -> ImportResult:
        rows = read_csv_rows(source)
        result = ImportResult(job_name="student_import", metadata={"actor": actor})

        rejects: list[dict[str, Any]] = []

        for offset, row in enumerate(rows, start=2):
            missing = required_fields(row, ["student_id", "full_name", "cohort", "programme", "year"])
            if missing:
                issue = ImportIssue(
                    row_number=offset,
                    code="missing_required_field",
                    message=f"Missing required field(s): {', '.join(missing)}",
                    row=row,
                )
                result.add_issue(issue)
                rejects.append(issue.to_dict())
                continue

            try:
                student = Student(
                    student_id=row["student_id"],
                    full_name=row["full_name"],
                    cohort=row["cohort"],
                    programme=row["programme"],
                    year=int(row["year"]),
                    status=row.get("status") or "active",
                    tags=tuple(part.strip() for part in row.get("tags", "").split("|") if part.strip()),
                )
                registry.add(student, actor=actor)
                result.add_accept()
            except Exception as exc:
                issue = ImportIssue(
                    row_number=offset,
                    code=exc.__class__.__name__,
                    message=str(exc),
                    row=row,
                )
                result.add_issue(issue)
                rejects.append(issue.to_dict())

        if reject_path is not None:
            self.write_reject_report(reject_path, rejects)

        return result

    def build_fee_schedule(
        self,
        source: str | Path,
        *,
        schedule_id: str,
        title: str,
        reject_path: str | Path | None = None,
    ) -> tuple[FeeSchedule, ImportResult]:
        rows = read_csv_rows(source)
        result = ImportResult(job_name="fee_schedule_import", metadata={"schedule_id": schedule_id})
        rejects: list[dict[str, Any]] = []
        items: list[FeeItem] = []

        for offset, row in enumerate(rows, start=2):
            missing = required_fields(row, ["item_code", "description", "amount", "account_code"])
            if missing:
                issue = ImportIssue(
                    row_number=offset,
                    code="missing_required_field",
                    message=f"Missing required field(s): {', '.join(missing)}",
                    row=row,
                )
                result.add_issue(issue)
                rejects.append(issue.to_dict())
                continue

            try:
                years = tuple(int(part.strip()) for part in row.get("years", "").split("|") if part.strip())
                programmes = tuple(part.strip() for part in row.get("programmes", "").split("|") if part.strip())

                item = FeeItem(
                    item_code=row["item_code"],
                    description=row["description"],
                    amount=row["amount"],
                    account_code=row["account_code"],
                    years=years,
                    programmes=programmes,
                    required=(row.get("required", "true").strip().lower() not in {"false", "0", "no"}),
                )
                items.append(item)
                result.add_accept()
            except Exception as exc:
                issue = ImportIssue(
                    row_number=offset,
                    code=exc.__class__.__name__,
                    message=str(exc),
                    row=row,
                )
                result.add_issue(issue)
                rejects.append(issue.to_dict())

        if reject_path is not None:
            self.write_reject_report(reject_path, rejects)

        schedule = FeeSchedule(schedule_id=schedule_id, title=title, items=tuple(items))
        return schedule, result

    def write_reject_report(self, path: str | Path, rejects: list[dict[str, Any]]) -> None:
        output = Path(path)
        if output.suffix.lower() == ".csv":
            flattened = []
            for issue in rejects:
                row = dict(issue.get("row", {}))
                row["_row_number"] = issue["row_number"]
                row["_code"] = issue["code"]
                row["_message"] = issue["message"]
                flattened.append(row)
            write_csv_rows(output, flattened)
            return

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(rejects, indent=2, sort_keys=True), encoding="utf-8")