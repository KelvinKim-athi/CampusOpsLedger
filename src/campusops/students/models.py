from __future__ import annotations

from dataclasses import dataclass, field


ACTIVE = "active"
SUSPENDED = "suspended"
TRANSFERRED = "transferred"
ARCHIVED = "archived"

VALID_STATUSES = {ACTIVE, SUSPENDED, TRANSFERRED, ARCHIVED}


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_student_id(value: object) -> str:
    text = clean_text(value).upper().replace(" ", "")
    if not text:
        raise ValueError("student id is required")
    return text


def clean_status(value: object) -> str:
    text = clean_text(value).lower().replace("-", "_").replace(" ", "_")
    if text not in VALID_STATUSES:
        raise ValueError(f"unsupported student status: {value}")
    return text


@dataclass(frozen=True)
class Student:
    student_id: str
    full_name: str
    cohort: str
    programme: str
    year: int
    status: str = ACTIVE
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        student_id = clean_student_id(self.student_id)
        full_name = clean_text(self.full_name)
        cohort = clean_text(self.cohort)
        programme = clean_text(self.programme)
        status = clean_status(self.status)

        if not full_name:
            raise ValueError("student full name is required")
        if not cohort:
            raise ValueError("student cohort is required")
        if not programme:
            raise ValueError("student programme is required")

        year = int(self.year)
        if year < 1:
            raise ValueError("student year must be positive")

        clean_tags = tuple(sorted({clean_text(tag).lower() for tag in self.tags if clean_text(tag)}))

        object.__setattr__(self, "student_id", student_id)
        object.__setattr__(self, "full_name", full_name)
        object.__setattr__(self, "cohort", cohort)
        object.__setattr__(self, "programme", programme)
        object.__setattr__(self, "year", year)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "tags", clean_tags)

    def with_status(self, status: str) -> "Student":
        return Student(
            student_id=self.student_id,
            full_name=self.full_name,
            cohort=self.cohort,
            programme=self.programme,
            year=self.year,
            status=status,
            tags=self.tags,
        )

    def with_cohort(self, cohort: str) -> "Student":
        return Student(
            student_id=self.student_id,
            full_name=self.full_name,
            cohort=cohort,
            programme=self.programme,
            year=self.year,
            status=self.status,
            tags=self.tags,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "student_id": self.student_id,
            "full_name": self.full_name,
            "cohort": self.cohort,
            "programme": self.programme,
            "year": self.year,
            "status": self.status,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "Student":
        return cls(
            student_id=str(payload["student_id"]),
            full_name=str(payload["full_name"]),
            cohort=str(payload["cohort"]),
            programme=str(payload["programme"]),
            year=int(payload["year"]),
            status=str(payload.get("status", ACTIVE)),
            tags=tuple(payload.get("tags", ()) or ()),
        )
