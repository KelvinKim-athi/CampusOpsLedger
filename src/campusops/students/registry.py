from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from campusops.audit.ledger import AuditLedger
from campusops.students.models import ACTIVE, ARCHIVED, SUSPENDED, Student, clean_student_id


class StudentRegistry:
    def __init__(
        self,
        students: Iterable[Student] | None = None,
        *,
        audit: AuditLedger | None = None,
    ) -> None:
        self._students: dict[str, Student] = {}
        self.audit = audit or AuditLedger()

        for student in students or ():
            self._students[student.student_id] = student

    def add(self, student: Student, *, actor: str = "system") -> Student:
        if student.student_id in self._students:
            raise ValueError(f"student already exists: {student.student_id}")

        self._students[student.student_id] = student
        self.audit.record(
            event_type="student.created",
            actor=actor,
            entity_type="student",
            entity_id=student.student_id,
            message=f"Registered {student.full_name}",
            metadata={
                "cohort": student.cohort,
                "programme": student.programme,
                "year": student.year,
            },
        )
        return student

    def get(self, student_id: object) -> Student:
        key = clean_student_id(student_id)
        try:
            return self._students[key]
        except KeyError as exc:
            raise KeyError(f"unknown student: {key}") from exc

    def has(self, student_id: object) -> bool:
        return clean_student_id(student_id) in self._students

    def suspend(self, student_id: object, *, actor: str, reason: str) -> Student:
        student = self.get(student_id)
        updated = student.with_status(SUSPENDED)
        self._students[updated.student_id] = updated
        self.audit.record(
            event_type="student.suspended",
            actor=actor,
            entity_type="student",
            entity_id=updated.student_id,
            message=f"Suspended {updated.full_name}",
            metadata={"reason": reason},
        )
        return updated

    def activate(self, student_id: object, *, actor: str) -> Student:
        student = self.get(student_id)
        updated = student.with_status(ACTIVE)
        self._students[updated.student_id] = updated
        self.audit.record(
            event_type="student.activated",
            actor=actor,
            entity_type="student",
            entity_id=updated.student_id,
            message=f"Activated {updated.full_name}",
            metadata={},
        )
        return updated

    def archive(self, student_id: object, *, actor: str, reason: str) -> Student:
        student = self.get(student_id)
        updated = student.with_status(ARCHIVED)
        self._students[updated.student_id] = updated
        self.audit.record(
            event_type="student.archived",
            actor=actor,
            entity_type="student",
            entity_id=updated.student_id,
            message=f"Archived {updated.full_name}",
            metadata={"reason": reason},
        )
        return updated

    def transfer_cohort(self, student_id: object, cohort: str, *, actor: str) -> Student:
        student = self.get(student_id)
        old_cohort = student.cohort
        updated = student.with_cohort(cohort)
        self._students[updated.student_id] = updated
        self.audit.record(
            event_type="student.cohort_changed",
            actor=actor,
            entity_type="student",
            entity_id=updated.student_id,
            message=f"Moved {updated.full_name} from {old_cohort} to {updated.cohort}",
            metadata={"old_cohort": old_cohort, "new_cohort": updated.cohort},
        )
        return updated

    def by_cohort(self, cohort: str) -> list[Student]:
        wanted = cohort.strip()
        return sorted(
            [student for student in self._students.values() if student.cohort == wanted],
            key=lambda student: student.student_id,
        )

    def active_students(self) -> list[Student]:
        return sorted(
            [student for student in self._students.values() if student.status == ACTIVE],
            key=lambda student: student.student_id,
        )

    def to_records(self) -> list[dict[str, object]]:
        return [student.to_dict() for student in sorted(self._students.values(), key=lambda item: item.student_id)]

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_records(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def from_records(
        cls,
        records: Iterable[dict[str, object]],
        *,
        audit: AuditLedger | None = None,
    ) -> "StudentRegistry":
        return cls((Student.from_dict(record) for record in records), audit=audit)

    @classmethod
    def load_json(cls, path: str | Path, *, audit: AuditLedger | None = None) -> "StudentRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("student registry file must contain a list")
        return cls.from_records(payload, audit=audit)

    def __len__(self) -> int:
        return len(self._students)