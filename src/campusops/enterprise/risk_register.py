from __future__ import annotations

import csv
import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


LOW = "low"
NORMAL = "normal"
HIGH = "high"
URGENT = "urgent"

NEW = "new"
TRIAGED = "triaged"
IN_REVIEW = "in_review"
WAITING = "waiting"
ESCALATED = "escalated"
RESOLVED = "resolved"
CLOSED = "closed"
VOID = "void"

OPEN_STATUSES = {NEW, TRIAGED, IN_REVIEW, WAITING, ESCALATED}
FINAL_STATUSES = {RESOLVED, CLOSED, VOID}
ALL_STATUSES = OPEN_STATUSES | FINAL_STATUSES

PRIORITY_WEIGHTS = {LOW: 1, NORMAL: 2, HIGH: 3, URGENT: 4}
CENT = Decimal("0.01")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_code(value: object) -> str:
    text = clean_text(value).lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def clean_status(value: object) -> str:
    status = clean_code(value)
    if status not in ALL_STATUSES:
        raise ValueError(f"unsupported status: {value}")
    return status


def clean_priority(value: object) -> str:
    priority = clean_code(value) or NORMAL
    if priority not in PRIORITY_WEIGHTS:
        raise ValueError(f"unsupported priority: {value}")
    return priority


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
class RiskRegisterRule:
    rule_id: str
    title: str
    field: str
    operator: str
    expected: str
    score: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        rule_id = clean_code(self.rule_id)
        title = clean_text(self.title)
        field_name = clean_code(self.field)
        operator = clean_code(self.operator)
        expected = clean_text(self.expected)
        score = int(self.score)
        tags = tuple(sorted({clean_code(tag) for tag in self.tags if clean_code(tag)}))

        if not rule_id:
            raise ValueError("rule id is required")
        if not title:
            raise ValueError("rule title is required")
        if not field_name:
            raise ValueError("rule field is required")
        if operator not in {"equals", "not_equals", "contains", "gt", "gte", "lt", "lte", "exists", "missing"}:
            raise ValueError(f"unsupported rule operator: {self.operator}")

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "field", field_name)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "score", score)
        object.__setattr__(self, "tags", tags)

    def matches(self, payload: dict[str, object]) -> bool:
        value = payload.get(self.field)
        if self.operator == "exists":
            return self.field in payload and payload.get(self.field) not in {None, ""}
        if self.operator == "missing":
            return self.field not in payload or payload.get(self.field) in {None, ""}
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
        if self.operator in {"gt", "gte", "lt", "lte"}:
            actual_num = Decimal(str(actual))
            expected_num = Decimal(str(expected))
            if self.operator == "gt":
                return actual_num > expected_num
            if self.operator == "gte":
                return actual_num >= expected_num
            if self.operator == "lt":
                return actual_num < expected_num
            return actual_num <= expected_num
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "field": self.field,
            "operator": self.operator,
            "expected": self.expected,
            "score": self.score,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RiskRegisterRule":
        return cls(
            rule_id=payload["rule_id"],
            title=payload["title"],
            field=payload["field"],
            operator=payload["operator"],
            expected=payload.get("expected", ""),
            score=int(payload.get("score", 0)),
            tags=tuple(payload.get("tags") or ()),
        )


@dataclass(frozen=True)
class RiskRegisterAction:
    action_id: str
    actor: str
    action_type: str
    message: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        action_id = clean_code(self.action_id)
        actor = clean_code(self.actor)
        action_type = clean_code(self.action_type)
        message = clean_text(self.message)

        if not action_id:
            raise ValueError("action id is required")
        if not actor:
            raise ValueError("action actor is required")
        if not action_type:
            raise ValueError("action type is required")
        if not message:
            raise ValueError("action message is required")

        object.__setattr__(self, "action_id", action_id)
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "action_type", action_type)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "created_at", parse_iso(self.created_at).isoformat())
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "actor": self.actor,
            "action_type": self.action_type,
            "message": self.message,
            "created_at": self.created_at,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RiskRegisterAction":
        return cls(
            action_id=payload["action_id"],
            actor=payload["actor"],
            action_type=payload["action_type"],
            message=payload["message"],
            created_at=payload.get("created_at", utc_now_iso()),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class RiskRegisterCase:
    case_id: str
    subject_id: str
    summary: str
    owner: str
    unit: str
    status: str = NEW
    priority: str = NORMAL
    value: Decimal | str | int | float = Decimal("0.00")
    opened_at: str = field(default_factory=utc_now_iso)
    due_at: str | None = None
    closed_at: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    matched_rules: tuple[str, ...] = field(default_factory=tuple)
    actions: tuple[RiskRegisterAction, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        case_id = clean_code(self.case_id)
        subject_id = clean_code(self.subject_id).upper()
        summary = clean_text(self.summary)
        owner = clean_code(self.owner)
        unit = clean_text(self.unit)
        status = clean_status(self.status)
        priority = clean_priority(self.priority)
        value = money(self.value)
        matched_rules = tuple(sorted({clean_code(rule) for rule in self.matched_rules if clean_code(rule)}))
        tags = tuple(sorted({clean_code(tag) for tag in self.tags if clean_code(tag)}))

        if not case_id:
            raise ValueError("case id is required")
        if not subject_id:
            raise ValueError("case subject is required")
        if not summary:
            raise ValueError("case summary is required")
        if not owner:
            raise ValueError("case owner is required")
        if not unit:
            raise ValueError("case unit is required")
        if value < 0:
            raise ValueError("case value cannot be negative")

        opened_at = parse_iso(self.opened_at).isoformat()
        due_at = parse_iso(self.due_at).isoformat() if self.due_at else None
        closed_at = parse_iso(self.closed_at).isoformat() if self.closed_at else None

        if status in FINAL_STATUSES and closed_at is None:
            closed_at = utc_now_iso()
        if status in OPEN_STATUSES and closed_at is not None:
            raise ValueError("open case cannot carry closed_at")

        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "priority", priority)
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

    def risk_score(self) -> int:
        score = PRIORITY_WEIGHTS[self.priority] * 10
        score += len(self.matched_rules) * 5
        if self.is_due():
            score += 20
        if self.status == ESCALATED:
            score += 25
        return score

    def with_status(self, status: object, *, actor: object, message: object = "") -> "RiskRegisterCase":
        status_key = clean_status(status)
        action = RiskRegisterAction(
            action_id=f"{self.case_id}-{len(self.actions) + 1}-status",
            actor=actor,
            action_type=f"status_{status_key}",
            message=clean_text(message) or f"Status changed to {status_key}",
            metadata={"from_status": self.status, "to_status": status_key},
        )
        closed_at = utc_now_iso() if status_key in FINAL_STATUSES else None
        return RiskRegisterCase(
            case_id=self.case_id,
            subject_id=self.subject_id,
            summary=self.summary,
            owner=self.owner,
            unit=self.unit,
            status=status_key,
            priority=self.priority,
            value=self.value,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=closed_at,
            payload=self.payload,
            matched_rules=self.matched_rules,
            actions=self.actions + (action,),
            tags=self.tags,
        )

    def with_owner(self, owner: object, *, actor: object) -> "RiskRegisterCase":
        new_owner = clean_code(owner)
        action = RiskRegisterAction(
            action_id=f"{self.case_id}-{len(self.actions) + 1}-owner",
            actor=actor,
            action_type="owner_changed",
            message=f"Owner changed from {self.owner} to {new_owner}",
            metadata={"from_owner": self.owner, "to_owner": new_owner},
        )
        return RiskRegisterCase(
            case_id=self.case_id,
            subject_id=self.subject_id,
            summary=self.summary,
            owner=new_owner,
            unit=self.unit,
            status=self.status,
            priority=self.priority,
            value=self.value,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=self.closed_at,
            payload=self.payload,
            matched_rules=self.matched_rules,
            actions=self.actions + (action,),
            tags=self.tags,
        )

    def with_rule_matches(self, rules: Iterable[RiskRegisterRule]) -> "RiskRegisterCase":
        matched = tuple(sorted({rule.rule_id for rule in rules if rule.matches(self.payload)}))
        return RiskRegisterCase(
            case_id=self.case_id,
            subject_id=self.subject_id,
            summary=self.summary,
            owner=self.owner,
            unit=self.unit,
            status=self.status,
            priority=self.priority,
            value=self.value,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=self.closed_at,
            payload=self.payload,
            matched_rules=matched,
            actions=self.actions,
            tags=self.tags,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "subject_id": self.subject_id,
            "summary": self.summary,
            "owner": self.owner,
            "unit": self.unit,
            "status": self.status,
            "priority": self.priority,
            "value": str(self.value),
            "opened_at": self.opened_at,
            "due_at": self.due_at,
            "closed_at": self.closed_at,
            "payload": deepcopy(self.payload),
            "matched_rules": list(self.matched_rules),
            "actions": [action.to_dict() for action in self.actions],
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RiskRegisterCase":
        return cls(
            case_id=payload["case_id"],
            subject_id=payload["subject_id"],
            summary=payload["summary"],
            owner=payload["owner"],
            unit=payload["unit"],
            status=payload.get("status", NEW),
            priority=payload.get("priority", NORMAL),
            value=payload.get("value", "0.00"),
            opened_at=payload.get("opened_at", utc_now_iso()),
            due_at=payload.get("due_at"),
            closed_at=payload.get("closed_at"),
            payload=payload.get("payload") or {},
            matched_rules=tuple(payload.get("matched_rules") or ()),
            actions=tuple(RiskRegisterAction.from_dict(row) for row in payload.get("actions", ())),
            tags=tuple(payload.get("tags") or ()),
        )


class RiskRegisterEngine:
    def __init__(
        self,
        cases: Iterable[RiskRegisterCase] | None = None,
        rules: Iterable[RiskRegisterRule] | None = None,
    ) -> None:
        self._cases: dict[str, RiskRegisterCase] = {}
        self._rules: dict[str, RiskRegisterRule] = {}

        for rule in rules or ():
            self.add_rule(rule)
        for case in cases or ():
            self.add_case(case)

    def add_rule(self, rule: RiskRegisterRule) -> RiskRegisterRule:
        if rule.rule_id in self._rules:
            raise ValueError(f"rule already exists: {rule.rule_id}")
        self._rules[rule.rule_id] = rule
        return rule

    def add_case(self, case: RiskRegisterCase, *, evaluate: bool = True) -> RiskRegisterCase:
        if case.case_id in self._cases:
            raise ValueError(f"case already exists: {case.case_id}")
        stored = case.with_rule_matches(self._rules.values()) if evaluate else case
        self._cases[stored.case_id] = stored
        return stored

    def get_case(self, case_id: object) -> RiskRegisterCase:
        key = clean_code(case_id)
        try:
            return self._cases[key]
        except KeyError as exc:
            raise KeyError(f"unknown case: {key}") from exc

    def update_status(self, case_id: object, status: object, *, actor: object, message: object = "") -> RiskRegisterCase:
        case = self.get_case(case_id).with_status(status, actor=actor, message=message)
        self._cases[case.case_id] = case
        return case

    def assign_owner(self, case_id: object, owner: object, *, actor: object) -> RiskRegisterCase:
        case = self.get_case(case_id).with_owner(owner, actor=actor)
        self._cases[case.case_id] = case
        return case

    def reevaluate(self, case_id: object | None = None) -> list[RiskRegisterCase]:
        selected = [self.get_case(case_id)] if case_id is not None else list(self._cases.values())
        updated: list[RiskRegisterCase] = []
        for case in selected:
            refreshed = case.with_rule_matches(self._rules.values())
            self._cases[refreshed.case_id] = refreshed
            updated.append(refreshed)
        return sorted(updated, key=lambda item: item.case_id)

    def cases_by_status(self, status: object) -> list[RiskRegisterCase]:
        wanted = clean_status(status)
        return sorted([case for case in self._cases.values() if case.status == wanted], key=lambda item: item.case_id)

    def cases_by_owner(self, owner: object) -> list[RiskRegisterCase]:
        wanted = clean_code(owner)
        return sorted([case for case in self._cases.values() if case.owner == wanted], key=lambda item: item.case_id)

    def cases_by_unit(self, unit: object) -> list[RiskRegisterCase]:
        wanted = clean_text(unit)
        return sorted([case for case in self._cases.values() if case.unit == wanted], key=lambda item: item.case_id)

    def due_cases(self, at: object | None = None) -> list[RiskRegisterCase]:
        return sorted([case for case in self._cases.values() if case.is_due(at)], key=lambda item: (item.due_at or "", item.case_id))

    def high_risk_cases(self, minimum_score: int = 40) -> list[RiskRegisterCase]:
        return sorted([case for case in self._cases.values() if case.risk_score() >= minimum_score], key=lambda item: (-item.risk_score(), item.case_id))

    def open_cases(self) -> list[RiskRegisterCase]:
        return sorted([case for case in self._cases.values() if case.is_open()], key=lambda item: (item.priority, item.opened_at, item.case_id))

    def closed_cases(self) -> list[RiskRegisterCase]:
        return sorted([case for case in self._cases.values() if not case.is_open()], key=lambda item: (item.closed_at or "", item.case_id))

    def total_value(self, *, status: object | None = None) -> Decimal:
        selected = self._cases.values()
        if status is not None:
            wanted = clean_status(status)
            selected = [case for case in selected if case.status == wanted]
        return sum((case.value for case in selected), Decimal("0.00")).quantize(CENT)

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in sorted(ALL_STATUSES)}
        for case in self._cases.values():
            counts[case.status] += 1
        return counts

    def owner_load(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in self.open_cases():
            counts[case.owner] = counts.get(case.owner, 0) + 1
        return dict(sorted(counts.items()))

    def rule_hit_counts(self) -> dict[str, int]:
        counts = {rule_id: 0 for rule_id in sorted(self._rules)}
        for case in self._cases.values():
            for rule_id in case.matched_rules:
                counts[rule_id] = counts.get(rule_id, 0) + 1
        return dict(sorted(counts.items()))

    def unit_summary(self) -> dict[str, dict[str, Any]]:
        summary: dict[str, dict[str, Any]] = {}
        for case in self._cases.values():
            bucket = summary.setdefault(case.unit, {"case_count": 0, "open_count": 0, "value": Decimal("0.00")})
            bucket["case_count"] += 1
            if case.is_open():
                bucket["open_count"] += 1
            bucket["value"] += case.value
        return {
            unit: {
                "case_count": values["case_count"],
                "open_count": values["open_count"],
                "value": str(values["value"].quantize(CENT)),
            }
            for unit, values in sorted(summary.items())
        }

    def export_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for case in sorted(self._cases.values(), key=lambda item: item.case_id):
            rows.append(
                {
                    "case_id": case.case_id,
                    "subject_id": case.subject_id,
                    "summary": case.summary,
                    "owner": case.owner,
                    "unit": case.unit,
                    "status": case.status,
                    "priority": case.priority,
                    "value": str(case.value),
                    "risk_score": case.risk_score(),
                    "matched_rules": "|".join(case.matched_rules),
                    "opened_at": case.opened_at,
                    "due_at": case.due_at or "",
                    "closed_at": case.closed_at or "",
                }
            )
        return rows

    def write_csv(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        rows = self.export_rows()
        fieldnames = [
            "case_id",
            "subject_id",
            "summary",
            "owner",
            "unit",
            "status",
            "priority",
            "value",
            "risk_score",
            "matched_rules",
            "opened_at",
            "due_at",
            "closed_at",
        ]
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def snapshot(self) -> dict[str, Any]:
        return {
            "domain": "risk_register",
            "case_type": "risk_case",
            "case_count": len(self._cases),
            "rule_count": len(self._rules),
            "open_count": len(self.open_cases()),
            "closed_count": len(self.closed_cases()),
            "total_value": str(self.total_value()),
            "status_counts": self.status_counts(),
            "owner_load": self.owner_load(),
            "rule_hit_counts": self.rule_hit_counts(),
            "unit_summary": self.unit_summary(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": "risk_register",
            "case_type": "risk_case",
            "rules": [rule.to_dict() for rule in sorted(self._rules.values(), key=lambda item: item.rule_id)],
            "cases": [case.to_dict() for case in sorted(self._cases.values(), key=lambda item: item.case_id)],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> "RiskRegisterEngine":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        rules = [RiskRegisterRule.from_dict(row) for row in payload.get("rules", ())]
        cases = [RiskRegisterCase.from_dict(row) for row in payload.get("cases", ())]
        return cls(cases=cases, rules=rules)

    def __len__(self) -> int:
        return len(self._cases)
