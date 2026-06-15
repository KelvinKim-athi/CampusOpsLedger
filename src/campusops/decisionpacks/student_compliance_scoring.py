from __future__ import annotations

import csv
import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


DRAFT = "draft"
OPEN = "open"
PENDING = "pending"
IN_REVIEW = "in_review"
WAITING = "waiting"
ESCALATED = "escalated"
APPROVED = "approved"
REJECTED = "rejected"
RESOLVED = "resolved"
CLOSED = "closed"
VOID = "void"

OPEN_STATUSES = {DRAFT, OPEN, PENDING, IN_REVIEW, WAITING, ESCALATED}
FINAL_STATUSES = {APPROVED, REJECTED, RESOLVED, CLOSED, VOID}
ALL_STATUSES = OPEN_STATUSES | FINAL_STATUSES

LOW = "low"
NORMAL = "normal"
HIGH = "high"
URGENT = "urgent"
SEVERITY_WEIGHT = {LOW: 1, NORMAL: 2, HIGH: 3, URGENT: 4}
CENT = Decimal("0.01")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_key(value: object) -> str:
    text = clean_text(value).lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def clean_status(value: object) -> str:
    status = clean_key(value)
    if status not in ALL_STATUSES:
        raise ValueError(f"unsupported status: {value}")
    return status


def clean_severity(value: object) -> str:
    severity = clean_key(value) or NORMAL
    if severity not in SEVERITY_WEIGHT:
        raise ValueError(f"unsupported severity: {value}")
    return severity


def money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_iso(value: object) -> datetime:
    text = clean_text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def days_between(start: object, end: object) -> int:
    return max((parse_iso(end) - parse_iso(start)).days, 0)


@dataclass(frozen=True)
class StudentComplianceScoringRule:
    rule_id: str
    title: str
    field: str
    operator: str
    expected: str = ""
    score: int = 0
    required: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        rule_id = clean_key(self.rule_id)
        title = clean_text(self.title)
        field_name = clean_key(self.field)
        operator = clean_key(self.operator)
        expected = clean_text(self.expected)
        score = int(self.score)
        tags = tuple(sorted({clean_key(tag) for tag in self.tags if clean_key(tag)}))

        if not rule_id:
            raise ValueError("rule id is required")
        if not title:
            raise ValueError("rule title is required")
        if not field_name:
            raise ValueError("rule field is required")
        if operator not in {"equals", "not_equals", "contains", "gte", "gt", "lte", "lt", "exists", "missing"}:
            raise ValueError(f"unsupported rule operator: {self.operator}")

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "field", field_name)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "tags", tags)

    def matches(self, payload: dict[str, object]) -> bool:
        normalized = {clean_key(key): value for key, value in payload.items()}
        value = normalized.get(self.field)

        if self.operator == "exists":
            return self.field in normalized and value not in {None, ""}
        if self.operator == "missing":
            return self.field not in normalized or value in {None, ""}
        if value is None:
            return False

        actual = clean_text(value)
        expected = self.expected

        if self.operator == "equals":
            return actual == expected
        if self.operator == "not_equals":
            return actual != expected
        if self.operator == "contains":
            return expected.lower() in actual.lower()

        actual_number = Decimal(str(actual))
        expected_number = Decimal(str(expected))

        if self.operator == "gte":
            return actual_number >= expected_number
        if self.operator == "gt":
            return actual_number > expected_number
        if self.operator == "lte":
            return actual_number <= expected_number
        if self.operator == "lt":
            return actual_number < expected_number

        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "field": self.field,
            "operator": self.operator,
            "expected": self.expected,
            "score": self.score,
            "required": self.required,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StudentComplianceScoringRule":
        return cls(
            rule_id=payload["rule_id"],
            title=payload["title"],
            field=payload["field"],
            operator=payload["operator"],
            expected=payload.get("expected", ""),
            score=int(payload.get("score", 0)),
            required=bool(payload.get("required", False)),
            tags=tuple(payload.get("tags") or ()),
        )


@dataclass(frozen=True)
class StudentComplianceScoringEvidence:
    evidence_id: str
    submitted_by: str
    description: str
    captured_at: str = field(default_factory=utc_now_iso)
    verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        evidence_id = clean_key(self.evidence_id)
        submitted_by = clean_key(self.submitted_by)
        description = clean_text(self.description)

        if not evidence_id:
            raise ValueError("evidence id is required")
        if not submitted_by:
            raise ValueError("evidence submitter is required")
        if not description:
            raise ValueError("evidence description is required")

        object.__setattr__(self, "evidence_id", evidence_id)
        object.__setattr__(self, "submitted_by", submitted_by)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "captured_at", parse_iso(self.captured_at).isoformat())
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "submitted_by": self.submitted_by,
            "description": self.description,
            "captured_at": self.captured_at,
            "verified": self.verified,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StudentComplianceScoringEvidence":
        return cls(
            evidence_id=payload["evidence_id"],
            submitted_by=payload["submitted_by"],
            description=payload["description"],
            captured_at=payload.get("captured_at", utc_now_iso()),
            verified=bool(payload.get("verified", False)),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class StudentComplianceScoringEvent:
    event_id: str
    actor: str
    event_type: str
    message: str
    occurred_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        event_id = clean_key(self.event_id)
        actor = clean_key(self.actor)
        event_type = clean_key(self.event_type)
        message = clean_text(self.message)

        if not event_id:
            raise ValueError("event id is required")
        if not actor:
            raise ValueError("event actor is required")
        if not event_type:
            raise ValueError("event type is required")
        if not message:
            raise ValueError("event message is required")

        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "occurred_at", parse_iso(self.occurred_at).isoformat())
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "actor": self.actor,
            "event_type": self.event_type,
            "message": self.message,
            "occurred_at": self.occurred_at,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StudentComplianceScoringEvent":
        return cls(
            event_id=payload["event_id"],
            actor=payload["actor"],
            event_type=payload["event_type"],
            message=payload["message"],
            occurred_at=payload.get("occurred_at", utc_now_iso()),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class StudentComplianceScoringRecord:
    record_id: str
    subject_id: str
    title: str
    owner: str
    category: str
    severity: str = NORMAL
    status: str = OPEN
    value: Decimal | str | int | float = Decimal("0.00")
    opened_at: str = field(default_factory=utc_now_iso)
    due_at: str | None = None
    closed_at: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    matched_rules: tuple[str, ...] = field(default_factory=tuple)
    evidence: tuple[StudentComplianceScoringEvidence, ...] = field(default_factory=tuple)
    events: tuple[StudentComplianceScoringEvent, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        record_id = clean_key(self.record_id)
        subject_id = clean_key(self.subject_id).upper()
        title = clean_text(self.title)
        owner = clean_key(self.owner)
        category = clean_key(self.category)
        severity = clean_severity(self.severity)
        status = clean_status(self.status)
        value = money(self.value)
        matched_rules = tuple(sorted({clean_key(rule) for rule in self.matched_rules if clean_key(rule)}))
        tags = tuple(sorted({clean_key(tag) for tag in self.tags if clean_key(tag)}))

        if not record_id:
            raise ValueError("record id is required")
        if not subject_id:
            raise ValueError("subject id is required")
        if not title:
            raise ValueError("record title is required")
        if not owner:
            raise ValueError("record owner is required")
        if not category:
            raise ValueError("record category is required")
        if value < 0:
            raise ValueError("record value cannot be negative")

        opened_at = parse_iso(self.opened_at).isoformat()
        due_at = parse_iso(self.due_at).isoformat() if self.due_at else None
        closed_at = parse_iso(self.closed_at).isoformat() if self.closed_at else None

        if status in FINAL_STATUSES and closed_at is None:
            closed_at = utc_now_iso()

        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "opened_at", opened_at)
        object.__setattr__(self, "due_at", due_at)
        object.__setattr__(self, "closed_at", closed_at)
        object.__setattr__(self, "payload", deepcopy(dict(self.payload)))
        object.__setattr__(self, "matched_rules", matched_rules)
        object.__setattr__(self, "tags", tags)

    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def is_due(self, at: object | None = None) -> bool:
        if not self.due_at or not self.is_open():
            return False
        return parse_iso(self.due_at) <= parse_iso(at or utc_now_iso())

    def age_days(self, at: object | None = None) -> int:
        return days_between(self.opened_at, at or utc_now_iso())

    def cycle_days(self) -> int | None:
        if not self.closed_at:
            return None
        return days_between(self.opened_at, self.closed_at)

    def risk_score(self, at: object | None = None) -> int:
        score = SEVERITY_WEIGHT[self.severity] * 10
        score += len(self.matched_rules) * 8
        score += len(self.evidence) * 2
        if self.status == ESCALATED:
            score += 20
        if self.is_due(at):
            score += 15
        return score

    def evaluate_rules(self, rules: Iterable[StudentComplianceScoringRule]) -> "StudentComplianceScoringRecord":
        matched = tuple(sorted(rule.rule_id for rule in rules if rule.matches(self.payload)))
        return StudentComplianceScoringRecord(
            record_id=self.record_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            category=self.category,
            severity=self.severity,
            status=self.status,
            value=self.value,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=self.closed_at,
            payload=self.payload,
            matched_rules=matched,
            evidence=self.evidence,
            events=self.events,
            tags=self.tags,
        )

    def with_status(self, status: object, *, actor: object, message: object = "") -> "StudentComplianceScoringRecord":
        status_key = clean_status(status)
        event = StudentComplianceScoringEvent(
            event_id=f"{self.record_id}-{len(self.events) + 1}-status",
            actor=actor,
            event_type=f"status_{status_key}",
            message=clean_text(message) or f"Status changed to {status_key}",
            metadata={"from_status": self.status, "to_status": status_key},
        )
        return StudentComplianceScoringRecord(
            record_id=self.record_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            category=self.category,
            severity=self.severity,
            status=status_key,
            value=self.value,
            opened_at=self.opened_at,
            due_at=self.due_at,
            payload=self.payload,
            matched_rules=self.matched_rules,
            evidence=self.evidence,
            events=self.events + (event,),
            tags=self.tags,
        )

    def assign_owner(self, owner: object, *, actor: object) -> "StudentComplianceScoringRecord":
        new_owner = clean_key(owner)
        event = StudentComplianceScoringEvent(
            event_id=f"{self.record_id}-{len(self.events) + 1}-owner",
            actor=actor,
            event_type="owner_changed",
            message=f"Owner changed from {self.owner} to {new_owner}",
            metadata={"from_owner": self.owner, "to_owner": new_owner},
        )
        return StudentComplianceScoringRecord(
            record_id=self.record_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=new_owner,
            category=self.category,
            severity=self.severity,
            status=self.status,
            value=self.value,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=self.closed_at,
            payload=self.payload,
            matched_rules=self.matched_rules,
            evidence=self.evidence,
            events=self.events + (event,),
            tags=self.tags,
        )

    def add_evidence(self, evidence: StudentComplianceScoringEvidence) -> "StudentComplianceScoringRecord":
        if any(existing.evidence_id == evidence.evidence_id for existing in self.evidence):
            raise ValueError(f"evidence already exists: {evidence.evidence_id}")
        return StudentComplianceScoringRecord(
            record_id=self.record_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            category=self.category,
            severity=self.severity,
            status=self.status,
            value=self.value,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=self.closed_at,
            payload=self.payload,
            matched_rules=self.matched_rules,
            evidence=self.evidence + (evidence,),
            events=self.events,
            tags=self.tags,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "subject_id": self.subject_id,
            "title": self.title,
            "owner": self.owner,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "value": str(self.value),
            "opened_at": self.opened_at,
            "due_at": self.due_at,
            "closed_at": self.closed_at,
            "payload": deepcopy(self.payload),
            "matched_rules": list(self.matched_rules),
            "evidence": [item.to_dict() for item in self.evidence],
            "events": [event.to_dict() for event in self.events],
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StudentComplianceScoringRecord":
        return cls(
            record_id=payload["record_id"],
            subject_id=payload["subject_id"],
            title=payload["title"],
            owner=payload["owner"],
            category=payload["category"],
            severity=payload.get("severity", NORMAL),
            status=payload.get("status", OPEN),
            value=payload.get("value", "0.00"),
            opened_at=payload.get("opened_at", utc_now_iso()),
            due_at=payload.get("due_at"),
            closed_at=payload.get("closed_at"),
            payload=payload.get("payload") or {},
            matched_rules=tuple(payload.get("matched_rules") or ()),
            evidence=tuple(StudentComplianceScoringEvidence.from_dict(row) for row in payload.get("evidence", ())),
            events=tuple(StudentComplianceScoringEvent.from_dict(row) for row in payload.get("events", ())),
            tags=tuple(payload.get("tags") or ()),
        )


class StudentComplianceScoringRegister:
    domain = "student_compliance_scoring"

    def __init__(
        self,
        records: Iterable[StudentComplianceScoringRecord] | None = None,
        rules: Iterable[StudentComplianceScoringRule] | None = None,
    ) -> None:
        self._records: dict[str, StudentComplianceScoringRecord] = {}
        self._rules: dict[str, StudentComplianceScoringRule] = {}

        for rule in rules or ():
            self.add_rule(rule)
        for record in records or ():
            self.add_record(record, evaluate=False)

    def add_rule(self, rule: StudentComplianceScoringRule) -> StudentComplianceScoringRule:
        if rule.rule_id in self._rules:
            raise ValueError(f"rule already exists: {rule.rule_id}")
        self._rules[rule.rule_id] = rule
        return rule

    def add_record(self, record: StudentComplianceScoringRecord, *, evaluate: bool = True) -> StudentComplianceScoringRecord:
        if record.record_id in self._records:
            raise ValueError(f"record already exists: {record.record_id}")
        stored = record.evaluate_rules(self._rules.values()) if evaluate else record
        self._records[stored.record_id] = stored
        return stored

    def get(self, record_id: object) -> StudentComplianceScoringRecord:
        key = clean_key(record_id)
        try:
            return self._records[key]
        except KeyError as exc:
            raise KeyError(f"unknown record: {key}") from exc

    def update_status(self, record_id: object, status: object, *, actor: object, message: object = "") -> StudentComplianceScoringRecord:
        record = self.get(record_id).with_status(status, actor=actor, message=message)
        self._records[record.record_id] = record
        return record

    def assign_owner(self, record_id: object, owner: object, *, actor: object) -> StudentComplianceScoringRecord:
        record = self.get(record_id).assign_owner(owner, actor=actor)
        self._records[record.record_id] = record
        return record

    def add_evidence(self, record_id: object, evidence: StudentComplianceScoringEvidence) -> StudentComplianceScoringRecord:
        record = self.get(record_id).add_evidence(evidence)
        self._records[record.record_id] = record
        return record

    def reevaluate(self) -> list[StudentComplianceScoringRecord]:
        updated: list[StudentComplianceScoringRecord] = []
        for record in list(self._records.values()):
            refreshed = record.evaluate_rules(self._rules.values())
            self._records[refreshed.record_id] = refreshed
            updated.append(refreshed)
        return sorted(updated, key=lambda item: item.record_id)

    def all_records(self) -> list[StudentComplianceScoringRecord]:
        return sorted(self._records.values(), key=lambda item: item.record_id)

    def open_records(self) -> list[StudentComplianceScoringRecord]:
        return [record for record in self.all_records() if record.is_open()]

    def final_records(self) -> list[StudentComplianceScoringRecord]:
        return [record for record in self.all_records() if not record.is_open()]

    def by_owner(self, owner: object) -> list[StudentComplianceScoringRecord]:
        wanted = clean_key(owner)
        return [record for record in self.all_records() if record.owner == wanted]

    def by_status(self, status: object) -> list[StudentComplianceScoringRecord]:
        wanted = clean_status(status)
        return [record for record in self.all_records() if record.status == wanted]

    def by_category(self, category: object) -> list[StudentComplianceScoringRecord]:
        wanted = clean_key(category)
        return [record for record in self.all_records() if record.category == wanted]

    def by_tag(self, tag: object) -> list[StudentComplianceScoringRecord]:
        wanted = clean_key(tag)
        return [record for record in self.all_records() if wanted in record.tags]

    def due_records(self, at: object | None = None) -> list[StudentComplianceScoringRecord]:
        return [record for record in self.all_records() if record.is_due(at)]

    def high_risk_records(self, minimum_score: int = 40, *, at: object | None = None) -> list[StudentComplianceScoringRecord]:
        return sorted(
            [record for record in self.all_records() if record.risk_score(at) >= minimum_score],
            key=lambda item: (-item.risk_score(at), item.record_id),
        )

    def value_total(self) -> Decimal:
        return sum((record.value for record in self._records.values()), Decimal("0.00")).quantize(CENT)

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in sorted(ALL_STATUSES)}
        for record in self._records.values():
            counts[record.status] += 1
        return counts

    def owner_load(self) -> dict[str, int]:
        load: dict[str, int] = {}
        for record in self.open_records():
            load[record.owner] = load.get(record.owner, 0) + 1
        return dict(sorted(load.items()))

    def category_summary(self) -> dict[str, dict[str, Any]]:
        summary: dict[str, dict[str, Any]] = {}
        for record in self._records.values():
            bucket = summary.setdefault(
                record.category,
                {"record_count": 0, "open_count": 0, "value": Decimal("0.00")},
            )
            bucket["record_count"] += 1
            if record.is_open():
                bucket["open_count"] += 1
            bucket["value"] += record.value

        return {
            category: {
                "record_count": values["record_count"],
                "open_count": values["open_count"],
                "value": str(values["value"].quantize(CENT)),
            }
            for category, values in sorted(summary.items())
        }

    def rule_hit_counts(self) -> dict[str, int]:
        counts = {rule_id: 0 for rule_id in sorted(self._rules)}
        for record in self._records.values():
            for rule_id in record.matched_rules:
                counts[rule_id] = counts.get(rule_id, 0) + 1
        return dict(sorted(counts.items()))

    def snapshot(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "record_count": len(self._records),
            "rule_count": len(self._rules),
            "open_count": len(self.open_records()),
            "final_count": len(self.final_records()),
            "value_total": str(self.value_total()),
            "status_counts": self.status_counts(),
            "owner_load": self.owner_load(),
            "category_summary": self.category_summary(),
            "rule_hit_counts": self.rule_hit_counts(),
        }

    def export_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for record in self.all_records():
            rows.append(
                {
                    "record_id": record.record_id,
                    "subject_id": record.subject_id,
                    "title": record.title,
                    "owner": record.owner,
                    "category": record.category,
                    "severity": record.severity,
                    "status": record.status,
                    "value": str(record.value),
                    "risk_score": record.risk_score(),
                    "matched_rules": "|".join(record.matched_rules),
                    "evidence_count": len(record.evidence),
                    "event_count": len(record.events),
                }
            )
        return rows

    def write_csv(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "record_id",
            "subject_id",
            "title",
            "owner",
            "category",
            "severity",
            "status",
            "value",
            "risk_score",
            "matched_rules",
            "evidence_count",
            "event_count",
        ]

        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.export_rows():
                writer.writerow(row)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "rules": [rule.to_dict() for rule in sorted(self._rules.values(), key=lambda item: item.rule_id)],
            "records": [record.to_dict() for record in self.all_records()],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> "StudentComplianceScoringRegister":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        rules = [StudentComplianceScoringRule.from_dict(row) for row in payload.get("rules", ())]
        records = [StudentComplianceScoringRecord.from_dict(row) for row in payload.get("records", ())]
        return cls(records=records, rules=rules)

    def __len__(self) -> int:
        return len(self._records)


def default_rules() -> tuple[StudentComplianceScoringRule, ...]:
    return (
        StudentComplianceScoringRule("amount-threshold", "Amount threshold", "amount", "gte", "1000", score=25, tags=("finance",)),
        StudentComplianceScoringRule("source-required", "Source required", "source", "exists", "", score=5, required=True),
        StudentComplianceScoringRule("priority-marker", "Urgent marker", "priority", "equals", "urgent", score=10, tags=("risk",)),
    )


def build_record(
    record_id: str,
    subject_id: str,
    title: str,
    owner: str,
    value: object = "0.00",
    **payload: object,
) -> StudentComplianceScoringRecord:
    data = dict(payload)
    data.setdefault("amount", str(value))
    data.setdefault("source", "student_compliance_scoring")
    return StudentComplianceScoringRecord(
        record_id=record_id,
        subject_id=subject_id,
        title=title,
        owner=owner,
        category="student_compliance_scoring",
        severity=NORMAL,
        value=value,
        payload=data,
        tags=("student_compliance_scoring",),
    )


def demo_register() -> StudentComplianceScoringRegister:
    register = StudentComplianceScoringRegister(rules=default_rules())
    register.add_record(build_record("DEMO-1", "S001", "Demo student_compliance_scoring record", "campus.office", "1250", priority="urgent"))
    return register
