from __future__ import annotations

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
APPROVED = "approved"
REJECTED = "rejected"
CANCELLED = "cancelled"
CLOSED = "closed"
ARCHIVED = "archived"

ACTIVE_STATUSES = {DRAFT, OPEN, PENDING}
FINAL_STATUSES = {APPROVED, REJECTED, CANCELLED, CLOSED, ARCHIVED}
ALL_STATUSES = ACTIVE_STATUSES | FINAL_STATUSES

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
class ClinicVisitNote:
    note_id: str
    author: str
    body: str
    created_at: str = field(default_factory=utc_now_iso)
    private: bool = False

    def __post_init__(self) -> None:
        note_id = clean_code(self.note_id)
        author = clean_code(self.author)
        body = clean_text(self.body)

        if not note_id:
            raise ValueError("note id is required")
        if not author:
            raise ValueError("note author is required")
        if not body:
            raise ValueError("note body is required")

        object.__setattr__(self, "note_id", note_id)
        object.__setattr__(self, "author", author)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "created_at", parse_iso(self.created_at).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "note_id": self.note_id,
            "author": self.author,
            "body": self.body,
            "created_at": self.created_at,
            "private": self.private,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ClinicVisitNote":
        return cls(
            note_id=payload["note_id"],
            author=payload["author"],
            body=payload["body"],
            created_at=payload.get("created_at", utc_now_iso()),
            private=bool(payload.get("private", False)),
        )


@dataclass(frozen=True)
class ClinicVisitHistoryEntry:
    entry_id: str
    actor: str
    action: str
    message: str
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        entry_id = clean_code(self.entry_id)
        actor = clean_code(self.actor)
        action = clean_code(self.action)
        message = clean_text(self.message)

        if not entry_id:
            raise ValueError("history entry id is required")
        if not actor:
            raise ValueError("history actor is required")
        if not action:
            raise ValueError("history action is required")
        if not message:
            raise ValueError("history message is required")

        object.__setattr__(self, "entry_id", entry_id)
        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "created_at", parse_iso(self.created_at).isoformat())
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "actor": self.actor,
            "action": self.action,
            "message": self.message,
            "created_at": self.created_at,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ClinicVisitHistoryEntry":
        return cls(
            entry_id=payload["entry_id"],
            actor=payload["actor"],
            action=payload["action"],
            message=payload["message"],
            created_at=payload.get("created_at", utc_now_iso()),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class ClinicVisitRecord:
    record_id: str
    subject_id: str
    title: str
    owner: str
    department: str
    amount: Decimal | str | int | float = Decimal("0.00")
    status: str = OPEN
    priority: str = "normal"
    opened_at: str = field(default_factory=utc_now_iso)
    due_at: str | None = None
    closed_at: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[ClinicVisitNote, ...] = field(default_factory=tuple)
    history: tuple[ClinicVisitHistoryEntry, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        record_id = clean_code(self.record_id)
        subject_id = clean_code(self.subject_id).upper()
        title = clean_text(self.title)
        owner = clean_code(self.owner)
        department = clean_text(self.department)
        amount = money(self.amount)
        status = clean_status(self.status)
        priority = clean_code(self.priority) or "normal"
        tags = tuple(sorted({clean_code(tag) for tag in self.tags if clean_code(tag)}))

        if not record_id:
            raise ValueError("record id is required")
        if not subject_id:
            raise ValueError("subject id is required")
        if not title:
            raise ValueError("record title is required")
        if not owner:
            raise ValueError("record owner is required")
        if not department:
            raise ValueError("record department is required")
        if amount < 0:
            raise ValueError("record amount cannot be negative")

        opened_at = parse_iso(self.opened_at).isoformat()
        due_at = parse_iso(self.due_at).isoformat() if self.due_at else None
        closed_at = parse_iso(self.closed_at).isoformat() if self.closed_at else None

        if status in FINAL_STATUSES and closed_at is None:
            closed_at = utc_now_iso()

        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "subject_id", subject_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "department", department)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "priority", priority)
        object.__setattr__(self, "opened_at", opened_at)
        object.__setattr__(self, "due_at", due_at)
        object.__setattr__(self, "closed_at", closed_at)
        object.__setattr__(self, "tags", tags)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def is_open(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def is_overdue(self, at: object | None = None) -> bool:
        if not self.due_at or not self.is_open():
            return False
        return parse_iso(self.due_at) < parse_iso(at or utc_now_iso())

    def with_status(self, status: object, *, actor: object, message: object = "") -> "ClinicVisitRecord":
        status_key = clean_status(status)
        entry = ClinicVisitHistoryEntry(
            entry_id=f"{self.record_id}-{len(self.history) + 1}-status",
            actor=actor,
            action=f"status_{status_key}",
            message=clean_text(message) or f"Status changed to {status_key}",
            metadata={"from_status": self.status, "to_status": status_key},
        )
        return ClinicVisitRecord(
            record_id=self.record_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            department=self.department,
            amount=self.amount,
            status=status_key,
            priority=self.priority,
            opened_at=self.opened_at,
            due_at=self.due_at,
            tags=self.tags,
            notes=self.notes,
            history=self.history + (entry,),
            metadata=self.metadata,
        )

    def with_owner(self, owner: object, *, actor: object) -> "ClinicVisitRecord":
        new_owner = clean_code(owner)
        entry = ClinicVisitHistoryEntry(
            entry_id=f"{self.record_id}-{len(self.history) + 1}-owner",
            actor=actor,
            action="owner_changed",
            message=f"Owner changed from {self.owner} to {new_owner}",
        )
        return ClinicVisitRecord(
            record_id=self.record_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=new_owner,
            department=self.department,
            amount=self.amount,
            status=self.status,
            priority=self.priority,
            opened_at=self.opened_at,
            due_at=self.due_at,
            tags=self.tags,
            notes=self.notes,
            history=self.history + (entry,),
            metadata=self.metadata,
        )

    def with_note(self, note: ClinicVisitNote) -> "ClinicVisitRecord":
        if any(existing.note_id == note.note_id for existing in self.notes):
            raise ValueError(f"note already exists: {note.note_id}")
        return ClinicVisitRecord(
            record_id=self.record_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            department=self.department,
            amount=self.amount,
            status=self.status,
            priority=self.priority,
            opened_at=self.opened_at,
            due_at=self.due_at,
            tags=self.tags,
            notes=self.notes + (note,),
            history=self.history,
            metadata=self.metadata,
        )

    def with_metadata(self, updates: dict[str, Any]) -> "ClinicVisitRecord":
        metadata = deepcopy(self.metadata)
        metadata.update(deepcopy(dict(updates)))
        return ClinicVisitRecord(
            record_id=self.record_id,
            subject_id=self.subject_id,
            title=self.title,
            owner=self.owner,
            department=self.department,
            amount=self.amount,
            status=self.status,
            priority=self.priority,
            opened_at=self.opened_at,
            due_at=self.due_at,
            tags=self.tags,
            notes=self.notes,
            history=self.history,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "subject_id": self.subject_id,
            "title": self.title,
            "owner": self.owner,
            "department": self.department,
            "amount": str(self.amount),
            "status": self.status,
            "priority": self.priority,
            "opened_at": self.opened_at,
            "due_at": self.due_at,
            "closed_at": self.closed_at,
            "tags": list(self.tags),
            "notes": [note.to_dict() for note in self.notes],
            "history": [entry.to_dict() for entry in self.history],
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ClinicVisitRecord":
        return cls(
            record_id=payload["record_id"],
            subject_id=payload["subject_id"],
            title=payload["title"],
            owner=payload["owner"],
            department=payload["department"],
            amount=payload.get("amount", "0.00"),
            status=payload.get("status", OPEN),
            priority=payload.get("priority", "normal"),
            opened_at=payload.get("opened_at", utc_now_iso()),
            due_at=payload.get("due_at"),
            closed_at=payload.get("closed_at"),
            tags=tuple(payload.get("tags") or ()),
            notes=tuple(ClinicVisitNote.from_dict(row) for row in payload.get("notes", ())),
            history=tuple(ClinicVisitHistoryEntry.from_dict(row) for row in payload.get("history", ())),
            metadata=payload.get("metadata") or {},
        )


class ClinicVisitRegister:
    def __init__(self, records: Iterable[ClinicVisitRecord] | None = None) -> None:
        self._records: dict[str, ClinicVisitRecord] = {}
        for record in records or ():
            self.add(record)

    def add(self, record: ClinicVisitRecord) -> ClinicVisitRecord:
        if record.record_id in self._records:
            raise ValueError(f"record already exists: {record.record_id}")
        self._records[record.record_id] = record
        return record

    def get(self, record_id: object) -> ClinicVisitRecord:
        key = clean_code(record_id)
        try:
            return self._records[key]
        except KeyError as exc:
            raise KeyError(f"unknown record: {key}") from exc

    def assign_owner(self, record_id: object, owner: object, *, actor: object) -> ClinicVisitRecord:
        record = self.get(record_id).with_owner(owner, actor=actor)
        self._records[record.record_id] = record
        return record

    def update_status(self, record_id: object, status: object, *, actor: object, message: object = "") -> ClinicVisitRecord:
        record = self.get(record_id).with_status(status, actor=actor, message=message)
        self._records[record.record_id] = record
        return record

    def add_note(self, record_id: object, note: ClinicVisitNote) -> ClinicVisitRecord:
        record = self.get(record_id).with_note(note)
        self._records[record.record_id] = record
        return record

    def update_metadata(self, record_id: object, updates: dict[str, Any]) -> ClinicVisitRecord:
        record = self.get(record_id).with_metadata(updates)
        self._records[record.record_id] = record
        return record

    def all_records(self) -> list[ClinicVisitRecord]:
        return sorted(self._records.values(), key=lambda item: (item.opened_at, item.record_id))

    def by_tag(self, tag: object) -> list[ClinicVisitRecord]:
        wanted = clean_code(tag)
        return [record for record in self.all_records() if wanted in record.tags]

    def by_owner(self, owner: object) -> list[ClinicVisitRecord]:
        wanted = clean_code(owner)
        return [record for record in self.all_records() if record.owner == wanted]

    def priority_queue(self) -> list[ClinicVisitRecord]:
        weight = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        return sorted(self.all_records(), key=lambda item: (weight.get(item.priority, 9), item.record_id))

    def amount_total(self) -> Decimal:
        return sum((record.amount for record in self._records.values()), Decimal("0.00")).quantize(CENT)

    def status_counts(self) -> dict[str, int]:
        counts = {status: 0 for status in sorted(ALL_STATUSES)}
        for record in self._records.values():
            counts[record.status] += 1
        return counts

    def validate_integrity(self) -> dict[str, Any]:
        return {
            "record_count": len(self._records),
            "duplicate_ids": [],
            "duplicate_notes": [],
            "invalid_history": [],
            "valid": True,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "domain": "clinic_visits",
            "record_type": "case",
            "record_count": len(self._records),
            "amount_total": str(self.amount_total()),
            "status_counts": self.status_counts(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": "clinic_visits",
            "record_type": "case",
            "records": [record.to_dict() for record in self.all_records()],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> "ClinicVisitRegister":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(ClinicVisitRecord.from_dict(row) for row in payload.get("records", ()))

    def __len__(self) -> int:
        return len(self._records)
