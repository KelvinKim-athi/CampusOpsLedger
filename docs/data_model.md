# CampusOpsLedger Data Model Notes

The project uses small Python domain objects with JSON serialization. Each module owns one operational boundary.

## Main domains

- students: student identity, cohort, programme, year, status, and tags.
- ledger: fee charges, payments, waivers, refunds, schedules, balances, and statements.
- attendance: class sessions, present, late, absent, excused marks, late policies, and attendance risk.
- rooms: room inventory, equipment, capacity checks, booking conflicts, and availability recommendations.
- imports: CSV normalization, validation issues, reject reports, and import job summaries.
- reports: registry summaries, fee balances, attendance risks, combined dashboards, JSON and CSV exports.
- security: staff users, roles, permission checks, and access audit events.
- audit: append-only audit events used by the other modules.

## Normalization conventions

Identifiers are normalized at module boundaries. Spaces, dashes, dots, and repeated separators become underscores. Student IDs are stored uppercase. Money values are quantized to cents. Timestamps are stored in UTC ISO format.

## Storage convention

The core package does not require a database. JSON files are enough for local operation, tests, and demo usage. CSV is used for imports and reject reports.
