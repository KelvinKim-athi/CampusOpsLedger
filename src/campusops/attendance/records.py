from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


PRESENT = "present"
LATE = "late"
ABSENT = "absent"
EXCUSED = "excused"

VALID_ATTENDANCE_STATUSES = {PRESENT, LATE, ABSENT, EXCUSED}


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


def clean_student_id(value: object) -> str:
    text = clean_text(value).upper().replace(" ", "")
    if not text:
        raise ValueError("student id is required")
    return text


def clean_status(value: object) -> str:
    status = clean_code(value)
    if status not in VALID_ATTENDANCE_STATUSES:
        raise ValueError(f"unsupported attendance status: {value}")
    return status


def parse_iso(value: object) -> datetime:
    text = clean_text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ClassSession:
    session_id: str
    course_code: str
    cohort: str
    room_code: str
    starts_at: str
    ends_at: str
    lecturer: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        session_id = clean_code(self.session_id)
        course_code = clean_code(self.course_code).upper()
        cohort = clean_text(self.cohort)
        room_code = clean_code(self.room_code).upper()
        lecturer = clean_text(self.lecturer)

        if not session_id:
            raise ValueError("session id is required")
        if not course_code:
            raise ValueError("course code is required")
        if not cohort:
            raise ValueError("session cohort is required")
        if not room_code:
            raise ValueError("room code is required")
        if not lecturer:
            raise ValueError("session lecturer is required")

        starts_at = parse_iso(self.starts_at).isoformat()
        ends_at_dt = parse_iso(self.ends_at)
        starts_at_dt = parse_iso(starts_at)

        if ends_at_dt <= starts_at_dt:
            raise ValueError("session end must be after start")

        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "course_code", course_code)
        object.__setattr__(self, "cohort", cohort)
        object.__setattr__(self, "room_code", room_code)
        object.__setattr__(self, "starts_at", starts_at_dt.isoformat())
        object.__setattr__(self, "ends_at", ends_at_dt.isoformat())
        object.__setattr__(self, "lecturer", lecturer)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "course_code": self.course_code,
            "cohort": self.cohort,
            "room_code": self.room_code,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "lecturer": self.lecturer,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ClassSession":
        return cls(
            session_id=payload["session_id"],
            course_code=payload["course_code"],
            cohort=payload["cohort"],
            room_code=payload["room_code"],
            starts_at=payload["starts_at"],
            ends_at=payload["ends_at"],
            lecturer=payload["lecturer"],
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class AttendanceMark:
    mark_id: str
    session_id: str
    student_id: str
    status: str
    marked_at: str = field(default_factory=utc_now_iso)
    minutes_late: int = 0
    source: str = "manual"
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        mark_id = clean_code(self.mark_id)
        session_id = clean_code(self.session_id)
        student_id = clean_student_id(self.student_id)
        status = clean_status(self.status)
        source = clean_code(self.source) or "manual"
        reason = clean_text(self.reason)
        minutes_late = int(self.minutes_late)

        if not mark_id:
            raise ValueError("attendance mark id is required")
        if not session_id:
            raise ValueError("attendance session id is required")
        if minutes_late < 0:
            raise ValueError("minutes late cannot be negative")
        if status != LATE and minutes_late:
            raise ValueError("only late marks can carry minutes late")

        object.__setattr__(self, "mark_id", mark_id)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "student_id", student_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "marked_at", parse_iso(self.marked_at).isoformat())
        object.__setattr__(self, "minutes_late", minutes_late)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "mark_id": self.mark_id,
            "session_id": self.session_id,
            "student_id": self.student_id,
            "status": self.status,
            "marked_at": self.marked_at,
            "minutes_late": self.minutes_late,
            "source": self.source,
            "reason": self.reason,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AttendanceMark":
        return cls(
            mark_id=payload["mark_id"],
            session_id=payload["session_id"],
            student_id=payload["student_id"],
            status=payload["status"],
            marked_at=payload.get("marked_at") or utc_now_iso(),
            minutes_late=int(payload.get("minutes_late", 0)),
            source=payload.get("source", "manual"),
            reason=payload.get("reason", ""),
            metadata=payload.get("metadata") or {},
        )