from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


LECTURE = "lecture"
LAB = "lab"
HALL = "hall"
OFFICE = "office"

VALID_ROOM_KINDS = {LECTURE, LAB, HALL, OFFICE}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_code(value: object) -> str:
    text = clean_text(value).lower()
    for mark in (" ", "-", "."):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def parse_iso(value: object) -> datetime:
    text = clean_text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Room:
    room_code: str
    name: str
    capacity: int
    kind: str = LECTURE
    building: str = ""
    equipment: tuple[str, ...] = field(default_factory=tuple)
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        room_code = clean_code(self.room_code).upper()
        name = clean_text(self.name)
        kind = clean_code(self.kind)
        building = clean_text(self.building)
        capacity = int(self.capacity)

        if not room_code:
            raise ValueError("room code is required")
        if not name:
            raise ValueError("room name is required")
        if capacity <= 0:
            raise ValueError("room capacity must be positive")
        if kind not in VALID_ROOM_KINDS:
            raise ValueError(f"unsupported room kind: {self.kind}")

        equipment = tuple(sorted({clean_code(item) for item in self.equipment if clean_code(item)}))

        object.__setattr__(self, "room_code", room_code)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "capacity", capacity)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "building", building)
        object.__setattr__(self, "equipment", equipment)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def supports(self, *, size: int = 1, equipment: tuple[str, ...] = (), kind: str | None = None) -> bool:
        if not self.active:
            return False
        if self.capacity < int(size):
            return False
        if kind is not None and self.kind != clean_code(kind):
            return False

        required = {clean_code(item) for item in equipment if clean_code(item)}
        return required.issubset(set(self.equipment))

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_code": self.room_code,
            "name": self.name,
            "capacity": self.capacity,
            "kind": self.kind,
            "building": self.building,
            "equipment": list(self.equipment),
            "active": self.active,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Room":
        return cls(
            room_code=payload["room_code"],
            name=payload["name"],
            capacity=int(payload["capacity"]),
            kind=payload.get("kind", LECTURE),
            building=payload.get("building", ""),
            equipment=tuple(payload.get("equipment") or ()),
            active=bool(payload.get("active", True)),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class RoomBooking:
    booking_id: str
    room_code: str
    title: str
    starts_at: str
    ends_at: str
    expected_size: int
    owner: str
    course_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        booking_id = clean_code(self.booking_id)
        room_code = clean_code(self.room_code).upper()
        title = clean_text(self.title)
        owner = clean_text(self.owner)
        course_code = clean_code(self.course_code).upper() if self.course_code else ""
        expected_size = int(self.expected_size)

        if not booking_id:
            raise ValueError("booking id is required")
        if not room_code:
            raise ValueError("booking room code is required")
        if not title:
            raise ValueError("booking title is required")
        if not owner:
            raise ValueError("booking owner is required")
        if expected_size <= 0:
            raise ValueError("booking expected size must be positive")

        start = parse_iso(self.starts_at)
        end = parse_iso(self.ends_at)
        if end <= start:
            raise ValueError("booking end must be after start")

        object.__setattr__(self, "booking_id", booking_id)
        object.__setattr__(self, "room_code", room_code)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "course_code", course_code)
        object.__setattr__(self, "expected_size", expected_size)
        object.__setattr__(self, "starts_at", start.isoformat())
        object.__setattr__(self, "ends_at", end.isoformat())
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def overlaps(self, other: "RoomBooking") -> bool:
        if self.room_code != other.room_code:
            return False
        return parse_iso(self.starts_at) < parse_iso(other.ends_at) and parse_iso(other.starts_at) < parse_iso(self.ends_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "booking_id": self.booking_id,
            "room_code": self.room_code,
            "title": self.title,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "expected_size": self.expected_size,
            "owner": self.owner,
            "course_code": self.course_code,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RoomBooking":
        return cls(
            booking_id=payload["booking_id"],
            room_code=payload["room_code"],
            title=payload["title"],
            starts_at=payload["starts_at"],
            ends_at=payload["ends_at"],
            expected_size=int(payload["expected_size"]),
            owner=payload["owner"],
            course_code=payload.get("course_code", ""),
            metadata=payload.get("metadata") or {},
        )