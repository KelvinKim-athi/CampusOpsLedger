from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from campusops.imports.jobs import ImportJobRunner
from campusops.ledger.transactions import StudentLedger
from campusops.reports.summary import fee_balance_report, student_registry_summary
from campusops.rooms.allocation import RoomDirectory
from campusops.students.registry import StudentRegistry


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _split_csv_values(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    output: list[str] = []
    for value in values:
        for part in str(value).split(","):
            cleaned = part.strip()
            if cleaned:
                output.append(cleaned)
    return tuple(output)


def cmd_import_students(args: argparse.Namespace) -> int:
    registry = StudentRegistry()
    if args.existing and Path(args.existing).exists():
        registry = StudentRegistry.load_json(args.existing)

    result = ImportJobRunner().import_students(
        args.csv,
        registry,
        actor=args.actor,
        reject_path=args.rejects,
    )
    registry.save_json(args.output)
    _print_json(result.to_dict())
    return 0


def cmd_students_summary(args: argparse.Namespace) -> int:
    registry = StudentRegistry.load_json(args.students)
    _print_json(student_registry_summary(registry))
    return 0


def cmd_fee_balances(args: argparse.Namespace) -> int:
    ledger = StudentLedger.load_json(args.ledger)
    _print_json(fee_balance_report(ledger, args.student_ids))
    return 0


def cmd_rooms_available(args: argparse.Namespace) -> int:
    directory = RoomDirectory.load_json(args.rooms)
    rooms = directory.available_rooms(
        starts_at=args.starts_at,
        ends_at=args.ends_at,
        size=args.size,
        equipment=_split_csv_values(args.equipment),
        kind=args.kind,
    )
    _print_json(
        {
            "room_count": len(rooms),
            "rooms": [room.to_dict() for room in rooms],
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="campusops",
        description="Offline campus operations ledger tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_students = subparsers.add_parser("import-students", help="Import students from a CSV file.")
    import_students.add_argument("--csv", required=True, help="Path to the source CSV file.")
    import_students.add_argument("--output", required=True, help="Path where the registry JSON should be written.")
    import_students.add_argument("--existing", help="Optional existing registry JSON to update.")
    import_students.add_argument("--rejects", help="Optional path for reject report JSON or CSV.")
    import_students.add_argument("--actor", default="importer", help="Audit actor name.")
    import_students.set_defaults(func=cmd_import_students)

    students_summary = subparsers.add_parser("students-summary", help="Print a student registry summary.")
    students_summary.add_argument("--students", required=True, help="Path to student registry JSON.")
    students_summary.set_defaults(func=cmd_students_summary)

    fee_balances = subparsers.add_parser("fee-balances", help="Print student fee balances.")
    fee_balances.add_argument("--ledger", required=True, help="Path to student ledger JSON.")
    fee_balances.add_argument("--student-ids", nargs="+", required=True, help="Student IDs to include.")
    fee_balances.set_defaults(func=cmd_fee_balances)

    rooms_available = subparsers.add_parser("rooms-available", help="List rooms available in a time window.")
    rooms_available.add_argument("--rooms", required=True, help="Path to room directory JSON.")
    rooms_available.add_argument("--starts-at", required=True, help="Availability window start time.")
    rooms_available.add_argument("--ends-at", required=True, help="Availability window end time.")
    rooms_available.add_argument("--size", type=int, default=1, help="Expected room size.")
    rooms_available.add_argument("--equipment", nargs="*", help="Required equipment values.")
    rooms_available.add_argument("--kind", help="Optional room kind filter.")
    rooms_available.set_defaults(func=cmd_rooms_available)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
