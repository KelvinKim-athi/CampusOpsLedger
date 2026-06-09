from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_word(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_event_type(value: object) -> str:
    text = clean_word(value).lower()
    for mark in ("-", ".", " "):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    actor: str
    entity_type: str
    entity_id: str
    message: str
    occurred_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        event_type = clean_event_type(self.event_type)
        actor = clean_word(self.actor)
        entity_type = clean_event_type(self.entity_type)
        entity_id = clean_word(self.entity_id)
        message = clean_word(self.message)

        if not event_type:
            raise ValueError("audit event type is required")
        if not actor:
            raise ValueError("audit actor is required")
        if not entity_type:
            raise ValueError("audit entity type is required")
        if not entity_id:
            raise ValueError("audit entity id is required")
        if not message:
            raise ValueError("audit message is required")

        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "entity_type", entity_type)
        object.__setattr__(self, "entity_id", entity_id)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "actor": self.actor,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "message": self.message,
            "occurred_at": self.occurred_at,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AuditEvent":
        return cls(
            event_type=payload["event_type"],
            actor=payload["actor"],
            entity_type=payload["entity_type"],
            entity_id=payload["entity_id"],
            message=payload["message"],
            occurred_at=payload.get("occurred_at") or utc_now_iso(),
            metadata=payload.get("metadata") or {},
        )