from __future__ import annotations

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

OPEN = "open"
IN_REVIEW = "in_review"
WAITING = "waiting"
ESCALATED = "escalated"
RESOLVED = "resolved"
CLOSED = "closed"
VOID = "void"

OPEN_STATUSES = {OPEN, IN_REVIEW, WAITING, ESCALATED}
FINAL_STATUSES = {RESOLVED, CLOSED, VOID}
ALL_STATUSES = OPEN_STATUSES | FINAL_STATUSES
SEVERITY_WEIGHTS = {LOW: 1, NORMAL: 2, HIGH: 3, URGENT: 4}
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
        raise ValueError(f"unsupported governance status: {value}")
    return status


def clean_severity(value: object) -> str:
    severity = clean_code(value) or NORMAL
    if severity not in SEVERITY_WEIGHTS:
        raise ValueError(f"unsupported governance severity: {value}")
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


@dataclass(frozen=True)
class GovernancePolicy:
    policy_id: str
    title: str
    field: str
    operator: str
    expected: str
    impact: int = 0
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        policy_id = clean_code(self.policy_id)
        title = clean_text(self.title)
        field_name = clean_code(self.field)
        operator = clean_code(self.operator)
        expected = clean_text(self.expected)
        impact = int(self.impact)
        tags = tuple(sorted({clean_code(tag) for tag in self.tags if clean_code(tag)}))

        if not policy_id:
            raise ValueError("policy id is required")
        if not title:
            raise ValueError("policy title is required")
        if not field_name:
            raise ValueError("policy field is required")
        if operator not in {"equals", "not_equals", "contains", "gte", "gt", "lte", "lt", "exists", "missing"}:
            raise ValueError(f"unsupported policy operator: {self.operator}")

        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "field", field_name)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "expected", expected)
        object.__setattr__(self, "impact", impact)
        object.__setattr__(self, "tags", tags)

    def applies(self, data: dict[str, object]) -> bool:
        value = data.get(self.field)
        if self.operator == "exists":
            return self.field in data and value not in {None, ""}
        if self.operator == "missing":
            return self.field not in data or value in {None, ""}
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
            "policy_id": self.policy_id,
            "title": self.title,
            "field": self.field,
            "operator": self.operator,
            "expected": self.expected,
            "impact": self.impact,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GovernancePolicy":
        return cls(
            policy_id=payload["policy_id"],
            title=payload["title"],
            field=payload["field"],
            operator=payload["operator"],
            expected=payload.get("expected", ""),
            impact=int(payload.get("impact", 0)),
            tags=tuple(payload.get("tags") or ()),
        )


@dataclass(frozen=True)
class GovernanceAction:
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
    def from_dict(cls, payload: dict[str, Any]) -> "GovernanceAction":
        return cls(
            action_id=payload["action_id"],
            actor=payload["actor"],
            action_type=payload["action_type"],
            message=payload["message"],
            created_at=payload.get("created_at", utc_now_iso()),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class GovernanceMetric:
    metric_id: str
    name: str
    value: Decimal | str | int | float
    unit: str = "count"
    captured_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        metric_id = clean_code(self.metric_id)
        name = clean_code(self.name)
        value = money(self.value)
        unit = clean_code(self.unit) or "count"

        if not metric_id:
            raise ValueError("metric id is required")
        if not name:
            raise ValueError("metric name is required")

        object.__setattr__(self, "metric_id", metric_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "captured_at", parse_iso(self.captured_at).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "value": str(self.value),
            "unit": self.unit,
            "captured_at": self.captured_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GovernanceMetric":
        return cls(
            metric_id=payload["metric_id"],
            name=payload["name"],
            value=payload["value"],
            unit=payload.get("unit", "count"),
            captured_at=payload.get("captured_at", utc_now_iso()),
        )


@dataclass(frozen=True)
class GovernanceCase:
    case_id: str
    subject_id: str
    title: str
    owner: str
    unit: str
    severity: str = NORMAL
    status: str = OPEN
    amount: Decimal | str | int | float = Decimal("0.00")
    opened_at: str = field(default_factory=utc_now_iso)
    due_at: str | None = None
    closed_at: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    matched_policies: tuple[str, ...] = field(default_factory=tuple)
    actions: tuple[GovernanceAction, ...] = field(default_factory=tuple)
    metrics: tuple[GovernanceMetric, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        case_id = clean_code(self.case_id)
        subject_id = clean_code(self.subject_id).upper()
        title = clean_text(self.title)
        owner = clean_code(self.owner)
        unit = clean_text(self.unit)
        severity = clean_severity(self.severity)
        status = clean_status(self.status)
        amount = money(self.amount)
        matched_policies = tuple(sorted({clean_code(policy) for policy in self.matched_policies if clean_code(policy)}))
        tags = tuple(sorted({clean_code(tag) for tag in self.tags if clean_code(tag)}))

        if not case_id:
            raise ValueError("governance case id is required")
        if not subject_id:
            raise ValueError("governance subject id is required")
        if not title:
            raise ValueError("governance title is required")
        if not owner:
            raise ValueError("governance owner is required")
        if not unit:
            raise ValueError("governance unit is required")
        if amount < 0:
            raise ValueError("governance amount cannot be negative")

        opened_at = parse_iso(self.opened_at).isoformat()
        due_at = parse_iso(self.due_at).isoformat() if self.due_at else None
        closed_at = parse_iso(self.closed_at).isoformat() if self.closed_at else None

        if status in FINAL_STATUSES and closed_at is None:
            closed_at = utc_now_iso()

        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "opened_at", opened_at)
        object.__setattr__(self, "due_at", due_at)
        object.__setattr__(self, "closed_at", closed_at)
        object.__setattr__(self, "data", deepcopy(dict(self.data)))
        object.__setattr__(self, "matched_policies", matched_policies)
        object.__setattr__(self, "tags", tags)

    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def is_due(self, at: object | None = None) -> bool:
        if not self.due_at or not self.is_open():
            return False
        return parse_iso(self.due_at) <= parse_iso(at or utc_now_iso())

    def score(self, at: object | None = None) -> int:
        score = SEVERITY_WEIGHTS[self.severity] * 12
        score += len(self.matched_policies) * 10
        if self.status == ESCALATED:
            score += 20
        if self.is_due(at):
            score += 20
        score += min(len(self.metrics) * 3, 12)
        return score

    def apply_policies(self, policies: Iterable[GovernancePolicy]) -> "GovernanceCase":
        matched = tuple(sorted(policy.policy_id for policy in policies if policy.applies(self.data)))
        return type(self)(
            case_id=self.case_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            unit=self.unit,
            severity=self.severity,
            status=self.status,
            amount=self.amount,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=self.closed_at,
            data=self.data,
            matched_policies=matched,
            actions=self.actions,
            metrics=self.metrics,
            tags=self.tags,
        )

    def with_status(self, status: object, *, actor: object, message: object = "") -> "GovernanceCase":
        status_key = clean_status(status)
        action = GovernanceAction(
            action_id=f"{self.case_id}-{len(self.actions) + 1}-status",
            actor=actor,
            action_type=f"status_{status_key}",
            message=clean_text(message) or f"Status changed to {status_key}",
        )
        return type(self)(
            case_id=self.case_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            unit=self.unit,
            severity=self.severity,
            status=status_key,
            amount=self.amount,
            opened_at=self.opened_at,
            due_at=self.due_at,
            data=self.data,
            matched_policies=self.matched_policies,
            actions=self.actions + (action,),
            metrics=self.metrics,
            tags=self.tags,
        )

    def assign(self, owner: object, *, actor: object) -> "GovernanceCase":
        new_owner = clean_code(owner)
        action = GovernanceAction(
            action_id=f"{self.case_id}-{len(self.actions) + 1}-owner",
            actor=actor,
            action_type="owner_changed",
            message=f"Owner changed from {self.owner} to {new_owner}",
        )
        return type(self)(
            case_id=self.case_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=new_owner,
            unit=self.unit,
            severity=self.severity,
            status=self.status,
            amount=self.amount,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=self.closed_at,
            data=self.data,
            matched_policies=self.matched_policies,
            actions=self.actions + (action,),
            metrics=self.metrics,
            tags=self.tags,
        )

    def add_metric(self, metric: GovernanceMetric) -> "GovernanceCase":
        if any(existing.metric_id == metric.metric_id for existing in self.metrics):
            raise ValueError(f"metric already exists: {metric.metric_id}")
        return type(self)(
            case_id=self.case_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            unit=self.unit,
            severity=self.severity,
            status=self.status,
            amount=self.amount,
            opened_at=self.opened_at,
            due_at=self.due_at,
            closed_at=self.closed_at,
            data=self.data,
            matched_policies=self.matched_policies,
            actions=self.actions,
            metrics=self.metrics + (metric,),
            tags=self.tags,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "subject_id": self.subject_id,
            "title": self.title,
            "owner": self.owner,
            "unit": self.unit,
            "severity": self.severity,
            "status": self.status,
            "amount": str(self.amount),
            "opened_at": self.opened_at,
            "due_at": self.due_at,
            "closed_at": self.closed_at,
            "data": deepcopy(self.data),
            "matched_policies": list(self.matched_policies),
            "actions": [action.to_dict() for action in self.actions],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GovernanceCase":
        return cls(
            case_id=payload["case_id"],
            subject_id=payload["subject_id"],
            title=payload["title"],
            owner=payload["owner"],
            unit=payload["unit"],
            severity=payload.get("severity", NORMAL),
            status=payload.get("status", OPEN),
            amount=payload.get("amount", "0.00"),
            opened_at=payload.get("opened_at", utc_now_iso()),
            due_at=payload.get("due_at"),
            closed_at=payload.get("closed_at"),
            data=payload.get("data") or {},
            matched_policies=tuple(payload.get("matched_policies") or ()),
            actions=tuple(GovernanceAction.from_dict(row) for row in payload.get("actions", ())),
            metrics=tuple(GovernanceMetric.from_dict(row) for row in payload.get("metrics", ())),
            tags=tuple(payload.get("tags") or ()),
        )


class GovernanceRegister:
    domain = "governance"
    case_type = "case"
    policy_class = GovernancePolicy
    case_class = GovernanceCase
    metric_class = GovernanceMetric

    def __init__(
        self,
        cases: Iterable[GovernanceCase] | None = None,
        policies: Iterable[GovernancePolicy] | None = None,
    ) -> None:
        self._cases: dict[str, GovernanceCase] = {}
        self._policies: dict[str, GovernancePolicy] = {}

        for policy in policies or ():
            self.add_policy(policy)
        for case in cases or ():
            self.add_case(case)

    def add_policy(self, policy: GovernancePolicy) -> GovernancePolicy:
        if policy.policy_id in self._policies:
            raise ValueError(f"policy already exists: {policy.policy_id}")
        self._policies[policy.policy_id] = policy
        return policy

    def add_case(self, case: GovernanceCase, *, evaluate: bool = True) -> GovernanceCase:
        if case.case_id in self._cases:
            raise ValueError(f"case already exists: {case.case_id}")
        stored = case.apply_policies(self._policies.values()) if evaluate else case
        self._cases[stored.case_id] = stored
        return stored

    def get_case(self, case_id: object) -> GovernanceCase:
        key = clean_code(case_id)
        try:
            return self._cases[key]
        except KeyError as exc:
            raise KeyError(f"unknown governance case: {key}") from exc

    def update_status(self, case_id: object, status: object, *, actor: object, message: object = "") -> GovernanceCase:
        case = self.get_case(case_id).with_status(status, actor=actor, message=message)
        self._cases[case.case_id] = case
        return case

    def assign_owner(self, case_id: object, owner: object, *, actor: object) -> GovernanceCase:
        case = self.get_case(case_id).assign(owner, actor=actor)
        self._cases[case.case_id] = case
        return case

    def add_metric(self, case_id: object, metric: GovernanceMetric) -> GovernanceCase:
        case = self.get_case(case_id).add_metric(metric)
        self._cases[case.case_id] = case
        return case

    def reevaluate(self) -> list[GovernanceCase]:
        refreshed = []
        for case in list(self._cases.values()):
            updated = case.apply_policies(self._policies.values())
            self._cases[updated.case_id] = updated
            refreshed.append(updated)
        return sorted(refreshed, key=lambda item: item.case_id)

    def due_cases(self, at: object | None = None) -> list[GovernanceCase]:
        return sorted([case for case in self._cases.values() if case.is_due(at)], key=lambda item: item.case_id)

    def high_score_cases(self, minimum: int = 40, *, at: object | None = None) -> list[GovernanceCase]:
        return sorted(
            [case for case in self._cases.values() if case.score(at) >= minimum],
            key=lambda item: (-item.score(at), item.case_id),
        )

    def cases_by_owner(self, owner: object) -> list[GovernanceCase]:
        wanted = clean_code(owner)
        return sorted([case for case in self._cases.values() if case.owner == wanted], key=lambda item: item.case_id)

    def cases_by_unit(self, unit: object) -> list[GovernanceCase]:
        wanted = clean_text(unit)
        return sorted([case for case in self._cases.values() if case.unit == wanted], key=lambda item: item.case_id)

    def cases_by_policy(self, policy_id: object) -> list[GovernanceCase]:
        wanted = clean_code(policy_id)
        return sorted([case for case in self._cases.values() if wanted in case.matched_policies], key=lambda item: item.case_id)

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in sorted(ALL_STATUSES)}
        for case in self._cases.values():
            counts[case.status] += 1
        return counts

    def severity_counts(self) -> dict[str, int]:
        counts = {severity: 0 for severity in sorted(SEVERITY_WEIGHTS)}
        for case in self._cases.values():
            counts[case.severity] += 1
        return counts

    def owner_load(self) -> dict[str, int]:
        load: dict[str, int] = {}
        for case in self._cases.values():
            if case.is_open():
                load[case.owner] = load.get(case.owner, 0) + 1
        return dict(sorted(load.items()))

    def total_amount(self) -> Decimal:
        return sum((case.amount for case in self._cases.values()), Decimal("0.00")).quantize(CENT)

    def metric_summary(self) -> dict[str, dict[str, str | int]]:
        summary: dict[str, dict[str, Decimal | int]] = {}
        for case in self._cases.values():
            for metric in case.metrics:
                bucket = summary.setdefault(metric.name, {"count": 0, "total": Decimal("0.00")})
                bucket["count"] = int(bucket["count"]) + 1
                bucket["total"] = Decimal(bucket["total"]) + metric.value

        output: dict[str, dict[str, str | int]] = {}
        for name, values in sorted(summary.items()):
            count = int(values["count"])
            total = Decimal(values["total"]).quantize(CENT)
            average = (total / Decimal(count)).quantize(CENT) if count else Decimal("0.00")
            output[name] = {"count": count, "total": str(total), "average": str(average)}
        return output

    def export_rows(self) -> list[dict[str, Any]]:
        rows = []
        for case in sorted(self._cases.values(), key=lambda item: item.case_id):
            rows.append(
                {
                    "case_id": case.case_id,
                    "subject_id": case.subject_id,
                    "title": case.title,
                    "owner": case.owner,
                    "unit": case.unit,
                    "severity": case.severity,
                    "status": case.status,
                    "amount": str(case.amount),
                    "score": case.score(),
                    "matched_policies": "|".join(case.matched_policies),
                }
            )
        return rows

    def snapshot(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "case_type": self.case_type,
            "case_count": len(self._cases),
            "policy_count": len(self._policies),
            "amount_total": str(self.total_amount()),
            "status_counts": self.status_counts(),
            "severity_counts": self.severity_counts(),
            "owner_load": self.owner_load(),
            "metric_summary": self.metric_summary(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "case_type": self.case_type,
            "policies": [policy.to_dict() for policy in sorted(self._policies.values(), key=lambda item: item.policy_id)],
            "cases": [case.to_dict() for case in sorted(self._cases.values(), key=lambda item: item.case_id)],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> "GovernanceRegister":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        policies = [cls.policy_class.from_dict(row) for row in payload.get("policies", ())]
        cases = [cls.case_class.from_dict(row) for row in payload.get("cases", ())]
        return cls(cases=cases, policies=policies)

    def __len__(self) -> int:
        return len(self._cases)
