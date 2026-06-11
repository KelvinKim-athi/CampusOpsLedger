from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from campusops.audit.ledger import AuditLedger


PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
CANCELLED = "cancelled"

FINAL_STATUSES = {APPROVED, REJECTED, CANCELLED}


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


@dataclass(frozen=True)
class ApprovalStep:
    step_id: str
    title: str
    role_id: str
    required: bool = True

    def __post_init__(self) -> None:
        step_id = clean_code(self.step_id)
        title = clean_text(self.title)
        role_id = clean_code(self.role_id)

        if not step_id:
            raise ValueError("approval step id is required")
        if not title:
            raise ValueError("approval step title is required")
        if not role_id:
            raise ValueError("approval step role is required")

        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "role_id", role_id)

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "role_id": self.role_id,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ApprovalStep":
        return cls(
            step_id=payload["step_id"],
            title=payload["title"],
            role_id=payload["role_id"],
            required=bool(payload.get("required", True)),
        )


@dataclass(frozen=True)
class ApprovalDecision:
    step_id: str
    decided_by: str
    decision: str
    note: str = ""
    decided_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        step_id = clean_code(self.step_id)
        decided_by = clean_code(self.decided_by)
        decision = clean_code(self.decision)
        note = clean_text(self.note)

        if decision not in {APPROVED, REJECTED}:
            raise ValueError("approval decision must be approved or rejected")
        if not step_id:
            raise ValueError("approval decision step is required")
        if not decided_by:
            raise ValueError("approval decision actor is required")

        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "decided_by", decided_by)
        object.__setattr__(self, "decision", decision)
        object.__setattr__(self, "note", note)

    def to_dict(self) -> dict[str, object]:
        return {
            "step_id": self.step_id,
            "decided_by": self.decided_by,
            "decision": self.decision,
            "note": self.note,
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ApprovalDecision":
        return cls(
            step_id=payload["step_id"],
            decided_by=payload["decided_by"],
            decision=payload["decision"],
            note=payload.get("note", ""),
            decided_at=payload.get("decided_at", utc_now_iso()),
        )


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    workflow_name: str
    entity_type: str
    entity_id: str
    submitted_by: str
    steps: tuple[ApprovalStep, ...]
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = PENDING
    decisions: tuple[ApprovalDecision, ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        request_id = clean_code(self.request_id)
        workflow_name = clean_code(self.workflow_name)
        entity_type = clean_code(self.entity_type)
        entity_id = clean_text(self.entity_id)
        submitted_by = clean_code(self.submitted_by)
        status = clean_code(self.status)

        if not request_id:
            raise ValueError("approval request id is required")
        if not workflow_name:
            raise ValueError("workflow name is required")
        if not entity_type:
            raise ValueError("approval entity type is required")
        if not entity_id:
            raise ValueError("approval entity id is required")
        if not submitted_by:
            raise ValueError("approval submitter is required")
        if status not in {PENDING, APPROVED, REJECTED, CANCELLED}:
            raise ValueError(f"unsupported approval status: {self.status}")
        if not self.steps:
            raise ValueError("approval request must have at least one step")

        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("approval request has duplicate steps")

        object.__setattr__(self, "request_id", request_id)
        object.__setattr__(self, "workflow_name", workflow_name)
        object.__setattr__(self, "entity_type", entity_type)
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "submitted_by", submitted_by)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "payload", deepcopy(dict(self.payload)))

    def decided_steps(self) -> set[str]:
        return {decision.step_id for decision in self.decisions}

    def next_pending_step(self) -> ApprovalStep | None:
        if self.status != PENDING:
            return None
        decided = self.decided_steps()
        for step in self.steps:
            if step.required and step.step_id not in decided:
                return step
        return None

    def with_decision(self, decision: ApprovalDecision) -> "ApprovalRequest":
        if self.status in FINAL_STATUSES:
            raise ValueError(f"approval request is already final: {self.status}")
        if decision.step_id not in {step.step_id for step in self.steps}:
            raise KeyError(f"unknown approval step: {decision.step_id}")
        if decision.step_id in self.decided_steps():
            raise ValueError(f"approval step already decided: {decision.step_id}")

        decisions = self.decisions + (decision,)
        status = REJECTED if decision.decision == REJECTED else PENDING

        if status == PENDING:
            required_steps = {step.step_id for step in self.steps if step.required}
            decided_steps = {row.step_id for row in decisions}
            if required_steps.issubset(decided_steps):
                status = APPROVED

        return ApprovalRequest(
            request_id=self.request_id,
            workflow_name=self.workflow_name,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            submitted_by=self.submitted_by,
            steps=self.steps,
            payload=self.payload,
            status=status,
            decisions=decisions,
            created_at=self.created_at,
        )

    def cancel(self) -> "ApprovalRequest":
        if self.status in FINAL_STATUSES:
            raise ValueError(f"approval request is already final: {self.status}")
        return ApprovalRequest(
            request_id=self.request_id,
            workflow_name=self.workflow_name,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            submitted_by=self.submitted_by,
            steps=self.steps,
            payload=self.payload,
            status=CANCELLED,
            decisions=self.decisions,
            created_at=self.created_at,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "workflow_name": self.workflow_name,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "submitted_by": self.submitted_by,
            "steps": [step.to_dict() for step in self.steps],
            "payload": deepcopy(self.payload),
            "status": self.status,
            "decisions": [decision.to_dict() for decision in self.decisions],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ApprovalRequest":
        return cls(
            request_id=payload["request_id"],
            workflow_name=payload["workflow_name"],
            entity_type=payload["entity_type"],
            entity_id=payload["entity_id"],
            submitted_by=payload["submitted_by"],
            steps=tuple(ApprovalStep.from_dict(row) for row in payload.get("steps", ())),
            payload=payload.get("payload") or {},
            status=payload.get("status", PENDING),
            decisions=tuple(ApprovalDecision.from_dict(row) for row in payload.get("decisions", ())),
            created_at=payload.get("created_at", utc_now_iso()),
        )


class ApprovalBoard:
    def __init__(self, requests: Iterable[ApprovalRequest] | None = None, *, audit: AuditLedger | None = None) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self.audit = audit or AuditLedger()

        for request in requests or ():
            if request.request_id in self._requests:
                raise ValueError(f"approval request already exists: {request.request_id}")
            self._requests[request.request_id] = request

    def submit(self, request: ApprovalRequest, *, actor: str = "system") -> ApprovalRequest:
        if request.request_id in self._requests:
            raise ValueError(f"approval request already exists: {request.request_id}")
        self._requests[request.request_id] = request
        self.audit.record(
            event_type="workflow.request_created",
            actor=actor,
            entity_type="approval_request",
            entity_id=request.request_id,
            message=f"Submitted approval request {request.request_id}",
            metadata={"workflow_name": request.workflow_name, "status": request.status},
        )
        return request

    def get(self, request_id: object) -> ApprovalRequest:
        key = clean_code(request_id)
        try:
            return self._requests[key]
        except KeyError as exc:
            raise KeyError(f"unknown approval request: {key}") from exc

    def decide(self, request_id: object, decision: ApprovalDecision, *, actor: str = "system") -> ApprovalRequest:
        request = self.get(request_id)
        updated = request.with_decision(decision)
        self._requests[updated.request_id] = updated
        self.audit.record(
            event_type=f"workflow.{decision.decision}",
            actor=actor,
            entity_type="approval_request",
            entity_id=updated.request_id,
            message=f"Recorded {decision.decision} decision for {updated.request_id}",
            metadata={"step_id": decision.step_id, "status": updated.status, "decided_by": decision.decided_by},
        )
        return updated

    def cancel(self, request_id: object, *, actor: str = "system") -> ApprovalRequest:
        request = self.get(request_id).cancel()
        self._requests[request.request_id] = request
        self.audit.record(
            event_type="workflow.cancelled",
            actor=actor,
            entity_type="approval_request",
            entity_id=request.request_id,
            message=f"Cancelled approval request {request.request_id}",
            metadata={"status": request.status},
        )
        return request

    def pending_for_role(self, role_id: object) -> list[ApprovalRequest]:
        role = clean_code(role_id)
        return sorted(
            [
                request
                for request in self._requests.values()
                if request.next_pending_step() is not None and request.next_pending_step().role_id == role
            ],
            key=lambda item: (item.created_at, item.request_id),
        )

    def requests_for_entity(self, entity_type: object, entity_id: object) -> list[ApprovalRequest]:
        wanted_type = clean_code(entity_type)
        wanted_id = clean_text(entity_id)
        return sorted(
            [
                request
                for request in self._requests.values()
                if request.entity_type == wanted_type and request.entity_id == wanted_id
            ],
            key=lambda item: (item.created_at, item.request_id),
        )

    def status_counts(self) -> dict[str, int]:
        counts = {PENDING: 0, APPROVED: 0, REJECTED: 0, CANCELLED: 0}
        for request in self._requests.values():
            counts[request.status] += 1
        return counts

    def to_dict(self) -> dict[str, object]:
        return {
            "requests": [
                request.to_dict()
                for request in sorted(self._requests.values(), key=lambda item: item.request_id)
            ]
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path, *, audit: AuditLedger | None = None) -> "ApprovalBoard":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        requests = [ApprovalRequest.from_dict(row) for row in payload.get("requests", ())]
        return cls(requests=requests, audit=audit)

    def __len__(self) -> int:
        return len(self._requests)
