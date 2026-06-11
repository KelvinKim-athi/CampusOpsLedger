# CampusOpsLedger Operator Runbook

CampusOpsLedger is an offline campus operations ledger for small school administration workflows. It keeps student records, fee transactions, attendance marks, room bookings, staff access roles, CSV imports, and reporting summaries in local JSON and CSV files.

## Typical local workflow

1. Import or maintain student records.
2. Post fee charges, payments, waivers, and refunds.
3. Track attendance by class session.
4. Allocate rooms and check timetable conflicts.
5. Generate dashboards and risk reports.
6. Store generated JSON files under data/samples/ or another private working directory.

## Useful commands

Run the full test suite:

python -m pytest -q

Generate deterministic demo data:

python scripts\generate_demo_data.py --output-dir data\samples\generated

Print a student summary:

python -m campusops.cli students-summary --students data\samples\generated\students.json

Print fee balances:

python -m campusops.cli fee-balances --ledger data\samples\generated\ledger.json --student-ids S001 S002 S003

Find available rooms:

python -m campusops.cli rooms-available --rooms data\samples\generated\rooms.json --starts-at 2026-02-01T08:30:00Z --ends-at 2026-02-01T09:00:00Z --size 20 --equipment projector

## Data safety notes

This project is designed for offline local records. Real deployments should keep generated JSON files private, avoid committing live student data, and rotate staff access exports when roles change.
