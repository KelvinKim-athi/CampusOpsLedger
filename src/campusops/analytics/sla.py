from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


def clean_key(value: object) -> str:
    text = str(value).strip().lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def parse_iso(value: object) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class SlaTarget:
    target_id: str
    service: str
    response_hours: int
    resolution_hours: int
    priority: str = "normal"

    def __post_init__(self) -> None:
        target_id = clean_key(self.target_id)
        service = clean_key(self.service)
        priority = clean_key(self.priority) or "normal"
        response_hours = int(self.response_hours)
        resolution_hours = int(self.resolution_hours)

        if not target_id:
            raise ValueError("SLA target id is required")
        if not service:
            raise ValueError("SLA service is required")
        if response_hours < 0:
            raise ValueError("response hours cannot be negative")
        if resolution_hours < response_hours:
            raise ValueError("resolution hours cannot be less than response hours")

        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "service", service)
        object.__setattr__(self, "priority", priority)
        object.__setattr__(self, "response_hours", response_hours)
        object.__setattr__(self, "resolution_hours", resolution_hours)


@dataclass(frozen=True)
class SlaCase:
    case_id: str
    service: str
    priority: str
    opened_at: str
    first_response_at: str | None = None
    resolved_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        case_id = clean_key(self.case_id)
        service = clean_key(self.service)
        priority = clean_key(self.priority) or "normal"
        if not case_id:
            raise ValueError("SLA case id is required")
        if not service:
            raise ValueError("SLA case service is required")

        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "service", service)
        object.__setattr__(self, "priority", priority)
        object.__setattr__(self, "opened_at", parse_iso(self.opened_at).isoformat())
        object.__setattr__(self, "first_response_at", parse_iso(self.first_response_at).isoformat() if self.first_response_at else None)
        object.__setattr__(self, "resolved_at", parse_iso(self.resolved_at).isoformat() if self.resolved_at else None)
        object.__setattr__(self, "metadata", dict(self.metadata))

    def response_hours(self, at: object | None = None) -> float:
        start = parse_iso(self.opened_at)
        end = parse_iso(self.first_response_at or at or datetime.now(timezone.utc).isoformat())
        return max((end - start).total_seconds() / 3600, 0)

    def resolution_hours(self, at: object | None = None) -> float:
        start = parse_iso(self.opened_at)
        end = parse_iso(self.resolved_at or at or datetime.now(timezone.utc).isoformat())
        return max((end - start).total_seconds() / 3600, 0)


class SlaMonitor:
    def __init__(self, targets: Iterable[SlaTarget] | None = None) -> None:
        self._targets: dict[tuple[str, str], SlaTarget] = {}
        for target in targets or ():
            self.add_target(target)

    def add_target(self, target: SlaTarget) -> SlaTarget:
        self._targets[(target.service, target.priority)] = target
        return target

    def target_for(self, case: SlaCase) -> SlaTarget:
        key = (case.service, case.priority)
        fallback = (case.service, "normal")
        if key in self._targets:
            return self._targets[key]
        if fallback in self._targets:
            return self._targets[fallback]
        raise KeyError(f"no SLA target for {case.service}/{case.priority}")

    def evaluate(self, case: SlaCase, *, at: object | None = None) -> dict[str, Any]:
        target = self.target_for(case)
        response_hours = case.response_hours(at)
        resolution_hours = case.resolution_hours(at)

        return {
            "case_id": case.case_id,
            "service": case.service,
            "priority": case.priority,
            "response_hours": round(response_hours, 2),
            "resolution_hours": round(resolution_hours, 2),
            "response_breached": response_hours > target.response_hours,
            "resolution_breached": resolution_hours > target.resolution_hours,
            "target_response_hours": target.response_hours,
            "target_resolution_hours": target.resolution_hours,
        }

    def summary(self, cases: Iterable[SlaCase], *, at: object | None = None) -> dict[str, Any]:
        rows = [self.evaluate(case, at=at) for case in cases]
        response_breaches = sum(1 for row in rows if row["response_breached"])
        resolution_breaches = sum(1 for row in rows if row["resolution_breached"])
        return {
            "case_count": len(rows),
            "response_breaches": response_breaches,
            "resolution_breaches": resolution_breaches,
            "breach_count": response_breaches + resolution_breaches,
            "rows": rows,
        }
