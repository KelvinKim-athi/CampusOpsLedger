from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from campusops.audit.events import AuditEvent, clean_event_type


class AuditLedger:
    def __init__(self, events: Iterable[AuditEvent] | None = None) -> None:
        self._events: list[AuditEvent] = list(events or [])

    def append(self, event: AuditEvent) -> AuditEvent:
        if not isinstance(event, AuditEvent):
            raise TypeError("AuditLedger only accepts AuditEvent objects")
        self._events.append(event)
        return event

    def record(
        self,
        *,
        event_type: object,
        actor: object,
        entity_type: object,
        entity_id: object,
        message: object,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=str(event_type),
            actor=str(actor),
            entity_type=str(entity_type),
            entity_id=str(entity_id),
            message=str(message),
            metadata=metadata or {},
        )
        self.append(event)
        return event

    def all_events(self) -> list[AuditEvent]:
        return list(self._events)

    def find(
        self,
        *,
        entity_type: object | None = None,
        entity_id: object | None = None,
        event_type: object | None = None,
        actor: object | None = None,
    ) -> list[AuditEvent]:
        wanted_entity_type = clean_event_type(entity_type) if entity_type is not None else None
        wanted_event_type = clean_event_type(event_type) if event_type is not None else None
        wanted_entity_id = str(entity_id).strip() if entity_id is not None else None
        wanted_actor = str(actor).strip() if actor is not None else None

        matches: list[AuditEvent] = []
        for event in self._events:
            if wanted_entity_type is not None and event.entity_type != wanted_entity_type:
                continue
            if wanted_entity_id is not None and event.entity_id != wanted_entity_id:
                continue
            if wanted_event_type is not None and event.event_type != wanted_event_type:
                continue
            if wanted_actor is not None and event.actor != wanted_actor:
                continue
            matches.append(event)
        return matches

    def to_records(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._events]

    def to_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_records(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def from_records(cls, records: Iterable[dict[str, Any]]) -> "AuditLedger":
        return cls(AuditEvent.from_dict(deepcopy(record)) for record in records)

    @classmethod
    def from_json(cls, path: str | Path) -> "AuditLedger":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("audit ledger file must contain a list")
        return cls.from_records(payload)

    def digest(self) -> str:
        rows = []
        for event in self._events:
            rows.append(
                "|".join(
                    [
                        event.occurred_at,
                        event.event_type,
                        event.actor,
                        event.entity_type,
                        event.entity_id,
                        event.message,
                        json.dumps(event.metadata, sort_keys=True, separators=(",", ":")),
                    ]
                )
            )
        text = "\n".join(sorted(rows))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def __len__(self) -> int:
        return len(self._events)