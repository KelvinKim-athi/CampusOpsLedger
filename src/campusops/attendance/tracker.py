from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from campusops.audit.ledger import AuditLedger
from campusops.attendance.policies import AttendancePolicy
from campusops.attendance.records import ABSENT, EXCUSED, AttendanceMark, ClassSession, clean_code, clean_student_id


class AttendanceTracker:
    def __init__(
        self,
        sessions: Iterable[ClassSession] | None = None,
        marks: Iterable[AttendanceMark] | None = None,
        *,
        audit: AuditLedger | None = None,
        policy: AttendancePolicy | None = None,
    ) -> None:
        self._sessions: dict[str, ClassSession] = {}
        self._marks: dict[str, AttendanceMark] = {}
        self.audit = audit or AuditLedger()
        self.policy = policy or AttendancePolicy()

        for session in sessions or ():
            self._sessions[session.session_id] = session
        for mark in marks or ():
            self._insert_existing_mark(mark)

    def _insert_existing_mark(self, mark: AttendanceMark) -> None:
        if mark.mark_id in self._marks:
            raise ValueError(f"attendance mark already exists: {mark.mark_id}")
        self._marks[mark.mark_id] = mark

    def add_session(self, session: ClassSession, *, actor: str = "system") -> ClassSession:
        if session.session_id in self._sessions:
            raise ValueError(f"session already exists: {session.session_id}")

        self._sessions[session.session_id] = session
        self.audit.record(
            event_type="attendance.session_created",
            actor=actor,
            entity_type="class_session",
            entity_id=session.session_id,
            message=f"Created session {session.course_code}",
            metadata={
                "course_code": session.course_code,
                "cohort": session.cohort,
                "room_code": session.room_code,
                "starts_at": session.starts_at,
                "ends_at": session.ends_at,
            },
        )
        return session

    def get_session(self, session_id: object) -> ClassSession:
        key = clean_code(session_id)
        try:
            return self._sessions[key]
        except KeyError as exc:
            raise KeyError(f"unknown session: {key}") from exc

    def mark(self, mark: AttendanceMark, *, actor: str = "system", replace: bool = False) -> AttendanceMark:
        session = self.get_session(mark.session_id)

        existing_for_student = [
            row for row in self._marks.values()
            if row.session_id == session.session_id and row.student_id == mark.student_id
        ]

        if existing_for_student and not replace:
            raise ValueError(f"student already marked for session: {mark.student_id}")

        for existing in existing_for_student:
            del self._marks[existing.mark_id]

        if mark.mark_id in self._marks:
            raise ValueError(f"attendance mark already exists: {mark.mark_id}")

        self._marks[mark.mark_id] = mark
        self.audit.record(
            event_type=f"attendance.{mark.status}",
            actor=actor,
            entity_type="attendance_mark",
            entity_id=mark.mark_id,
            message=f"Marked {mark.student_id} as {mark.status}",
            metadata={
                "session_id": mark.session_id,
                "student_id": mark.student_id,
                "course_code": session.course_code,
                "minutes_late": mark.minutes_late,
                "source": mark.source,
            },
        )
        return mark

    def mark_arrival(
        self,
        *,
        session_id: object,
        student_id: object,
        arrived_at: object,
        actor: str = "system",
        source: str = "scanner",
    ) -> AttendanceMark:
        session = self.get_session(session_id)
        status, minutes_late = self.policy.classify_arrival(session, arrived_at)
        mark = AttendanceMark(
            mark_id=f"{session.session_id}-{clean_student_id(student_id)}",
            session_id=session.session_id,
            student_id=student_id,
            status=status,
            marked_at=str(arrived_at),
            minutes_late=minutes_late,
            source=source,
        )
        return self.mark(mark, actor=actor)

    def excuse_absence(
        self,
        *,
        session_id: object,
        student_id: object,
        reason: object,
        actor: str = "system",
    ) -> AttendanceMark:
        session = self.get_session(session_id)
        mark = AttendanceMark(
            mark_id=f"{session.session_id}-{clean_student_id(student_id)}-excused",
            session_id=session.session_id,
            student_id=student_id,
            status=EXCUSED,
            reason=str(reason),
            source="office",
        )
        return self.mark(mark, actor=actor, replace=True)

    def session_marks(self, session_id: object) -> list[AttendanceMark]:
        session = self.get_session(session_id)
        return sorted(
            [mark for mark in self._marks.values() if mark.session_id == session.session_id],
            key=lambda mark: (mark.student_id, mark.mark_id),
        )

    def marks_for_student(self, student_id: object) -> list[AttendanceMark]:
        key = clean_student_id(student_id)
        return sorted(
            [mark for mark in self._marks.values() if mark.student_id == key],
            key=lambda mark: (mark.session_id, mark.marked_at, mark.mark_id),
        )

    def missing_students(self, session_id: object, enrolled_student_ids: Iterable[object]) -> list[str]:
        session = self.get_session(session_id)
        marked = {mark.student_id for mark in self._marks.values() if mark.session_id == session.session_id}
        enrolled = {clean_student_id(student_id) for student_id in enrolled_student_ids}
        return sorted(enrolled - marked)

    def fill_absences(
        self,
        *,
        session_id: object,
        enrolled_student_ids: Iterable[object],
        actor: str = "system",
    ) -> list[AttendanceMark]:
        session = self.get_session(session_id)
        created: list[AttendanceMark] = []

        for student_id in self.missing_students(session.session_id, enrolled_student_ids):
            created.append(
                self.mark(
                    AttendanceMark(
                        mark_id=f"{session.session_id}-{student_id}-absent",
                        session_id=session.session_id,
                        student_id=student_id,
                        status=ABSENT,
                        source="roll_call",
                    ),
                    actor=actor,
                )
            )

        return created

    def student_summary(self, student_id: object) -> dict[str, object]:
        key = clean_student_id(student_id)
        marks = self.marks_for_student(key)
        counts = {"present": 0, "late": 0, "absent": 0, "excused": 0}
        credit = 0.0

        for mark in marks:
            counts[mark.status] += 1
            credit += self.policy.attendance_credit(mark.status)

        total = len(marks)
        fraction = credit / total if total else 0.0

        return {
            "student_id": key,
            "total_sessions": total,
            "counts": counts,
            "attendance_credit": round(credit, 4),
            "attendance_fraction": round(fraction, 6),
            "meets_requirement": fraction >= self.policy.minimum_required_fraction if total else False,
        }

    def course_summary(self, course_code: object) -> dict[str, object]:
        wanted = clean_code(course_code).upper()
        session_ids = {
            session.session_id
            for session in self._sessions.values()
            if session.course_code == wanted
        }

        marks = [mark for mark in self._marks.values() if mark.session_id in session_ids]
        counts = {"present": 0, "late": 0, "absent": 0, "excused": 0}
        for mark in marks:
            counts[mark.status] += 1

        return {
            "course_code": wanted,
            "session_count": len(session_ids),
            "mark_count": len(marks),
            "counts": counts,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "sessions": [
                session.to_dict()
                for session in sorted(self._sessions.values(), key=lambda item: item.session_id)
            ],
            "marks": [
                mark.to_dict()
                for mark in sorted(self._marks.values(), key=lambda item: item.mark_id)
            ],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(
        cls,
        path: str | Path,
        *,
        audit: AuditLedger | None = None,
        policy: AttendancePolicy | None = None,
    ) -> "AttendanceTracker":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        sessions = [ClassSession.from_dict(row) for row in payload.get("sessions", ())]
        marks = [AttendanceMark.from_dict(row) for row in payload.get("marks", ())]
        return cls(sessions=sessions, marks=marks, audit=audit, policy=policy)

    def __len__(self) -> int:
        return len(self._sessions)