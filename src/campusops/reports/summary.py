from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable


def _money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _sorted_dict(counter: dict[str, int]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: item[0]))


def student_registry_summary(registry: object) -> dict[str, Any]:
    records = list(registry.to_records())

    by_status: dict[str, int] = defaultdict(int)
    by_cohort: dict[str, int] = defaultdict(int)
    by_programme: dict[str, int] = defaultdict(int)
    by_year: dict[str, int] = defaultdict(int)

    for row in records:
        by_status[str(row["status"])] += 1
        by_cohort[str(row["cohort"])] += 1
        by_programme[str(row["programme"])] += 1
        by_year[str(row["year"])] += 1

    return {
        "student_count": len(records),
        "by_status": _sorted_dict(dict(by_status)),
        "by_cohort": _sorted_dict(dict(by_cohort)),
        "by_programme": _sorted_dict(dict(by_programme)),
        "by_year": _sorted_dict(dict(by_year)),
    }


def assessment_score_report(book: object, assessment_id: object, *, policy: object | None = None) -> dict[str, Any]:
    rows = book.leaderboard(assessment_id, policy=policy)
    exported = [row.to_dict() for row in rows]

    passed = sum(1 for row in exported if row["passed"])
    total = len(exported)
    average_fraction = sum(float(row["fraction"]) for row in exported) / total if total else 0.0

    return {
        "assessment_id": str(assessment_id).strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_"),
        "attempt_count": total,
        "passed_count": passed,
        "failed_count": total - passed,
        "average_fraction": round(average_fraction, 6),
        "rows": exported,
    }


def fee_balance_report(ledger: object, student_ids: Iterable[object]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_balance = Decimal("0.00")

    for student_id in sorted({str(value).strip().upper().replace(" ", "") for value in student_ids}):
        balance = _money(ledger.balance_for_student(student_id))
        total_balance += balance
        rows.append(
            {
                "student_id": student_id,
                "balance": str(balance),
                "status": "clear" if balance <= 0 else "owing",
            }
        )

    return {
        "student_count": len(rows),
        "total_balance": str(_money(total_balance)),
        "rows": rows,
    }


def attendance_risk_report(tracker: object, student_ids: Iterable[object]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    for student_id in sorted({str(value).strip().upper().replace(" ", "") for value in student_ids}):
        summary = tracker.student_summary(student_id)
        fraction = float(summary["attendance_fraction"])
        risk = "ok"
        if summary["total_sessions"] == 0:
            risk = "no_records"
        elif fraction < 0.5:
            risk = "high"
        elif not summary["meets_requirement"]:
            risk = "watch"

        rows.append(
            {
                "student_id": student_id,
                "attendance_fraction": summary["attendance_fraction"],
                "total_sessions": summary["total_sessions"],
                "risk": risk,
                "counts": summary["counts"],
            }
        )

    return {
        "student_count": len(rows),
        "high_risk_count": sum(1 for row in rows if row["risk"] == "high"),
        "watch_count": sum(1 for row in rows if row["risk"] == "watch"),
        "rows": rows,
    }


def combined_student_dashboard(
    *,
    registry: object,
    ledger: object,
    tracker: object,
    student_ids: Iterable[object] | None = None,
) -> dict[str, Any]:
    records = registry.to_records()
    selected_ids = list(student_ids or [row["student_id"] for row in records])

    registry_rows = {str(row["student_id"]): row for row in records}
    fee_report = fee_balance_report(ledger, selected_ids)
    attendance_report = attendance_risk_report(tracker, selected_ids)

    fees_by_student = {row["student_id"]: row for row in fee_report["rows"]}
    attendance_by_student = {row["student_id"]: row for row in attendance_report["rows"]}

    rows: list[dict[str, Any]] = []
    for student_id in sorted({str(value).strip().upper().replace(" ", "") for value in selected_ids}):
        student = registry_rows.get(student_id, {})
        fee = fees_by_student.get(student_id, {"balance": "0.00", "status": "clear"})
        attendance = attendance_by_student.get(
            student_id,
            {"attendance_fraction": 0.0, "risk": "no_records", "total_sessions": 0},
        )
        rows.append(
            {
                "student_id": student_id,
                "full_name": student.get("full_name", ""),
                "cohort": student.get("cohort", ""),
                "programme": student.get("programme", ""),
                "status": student.get("status", ""),
                "fee_balance": fee["balance"],
                "fee_status": fee["status"],
                "attendance_fraction": attendance["attendance_fraction"],
                "attendance_risk": attendance["risk"],
                "attendance_sessions": attendance["total_sessions"],
            }
        )

    return {
        "student_count": len(rows),
        "rows": rows,
    }


def write_json_report(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_csv_report(path: str | Path, rows: Iterable[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    materialized = [dict(row) for row in rows]

    if fieldnames is None:
        fieldnames = []
        for row in materialized:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in materialized:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
