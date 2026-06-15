from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


def parse_iso(value: object) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def clean_key(value: object) -> str:
    text = str(value).strip().lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


@dataclass(frozen=True)
class RetentionRule:
    rule_id: str
    category: str
    keep_days: int
    legal_hold: bool = False

    def __post_init__(self) -> None:
        rule_id = clean_key(self.rule_id)
        category = clean_key(self.category)
        keep_days = int(self.keep_days)

        if not rule_id:
            raise ValueError("retention rule id is required")
        if not category:
            raise ValueError("retention category is required")
        if keep_days < 0:
            raise ValueError("retention days cannot be negative")

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "keep_days", keep_days)


@dataclass(frozen=True)
class RetainedRecord:
    record_id: str
    category: str
    created_at: str
    legal_hold: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        record_id = clean_key(self.record_id)
        category = clean_key(self.category)
        if not record_id:
            raise ValueError("retained record id is required")
        if not category:
            raise ValueError("retained record category is required")
        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "created_at", parse_iso(self.created_at).isoformat())
        object.__setattr__(self, "metadata", dict(self.metadata))


class RetentionPlanner:
    def __init__(self, rules: Iterable[RetentionRule] | None = None) -> None:
        self._rules: dict[str, RetentionRule] = {}
        for rule in rules or ():
            self.add_rule(rule)

    def add_rule(self, rule: RetentionRule) -> RetentionRule:
        self._rules[rule.category] = rule
        return rule

    def rule_for(self, record: RetainedRecord) -> RetentionRule:
        if record.category not in self._rules:
            raise KeyError(f"no retention rule for category: {record.category}")
        return self._rules[record.category]

    def should_dispose(self, record: RetainedRecord, at: object) -> bool:
        if record.legal_hold:
            return False

        rule = self.rule_for(record)
        if rule.legal_hold:
            return False

        age_days = (parse_iso(at) - parse_iso(record.created_at)).days
        return age_days >= rule.keep_days

    def disposal_plan(self, records: Iterable[RetainedRecord], at: object) -> dict[str, Any]:
        dispose = []
        keep = []

        for record in records:
            if self.should_dispose(record, at):
                dispose.append(record.record_id)
            else:
                keep.append(record.record_id)

        return {
            "dispose_count": len(dispose),
            "keep_count": len(keep),
            "dispose": sorted(dispose),
            "keep": sorted(keep),
        }
