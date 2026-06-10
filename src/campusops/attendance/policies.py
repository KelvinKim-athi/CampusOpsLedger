from __future__ import annotations

from dataclasses import dataclass

from campusops.attendance.records import ABSENT, EXCUSED, LATE, PRESENT, ClassSession, parse_iso


@dataclass(frozen=True)
class AttendancePolicy:
    grace_minutes: int = 10
    absent_after_minutes: int = 45
    minimum_required_fraction: float = 0.75
    count_excused_as_present: bool = True

    def __post_init__(self) -> None:
        grace_minutes = int(self.grace_minutes)
        absent_after_minutes = int(self.absent_after_minutes)
        minimum_required_fraction = float(self.minimum_required_fraction)

        if grace_minutes < 0:
            raise ValueError("grace minutes cannot be negative")
        if absent_after_minutes <= grace_minutes:
            raise ValueError("absent cutoff must be greater than grace minutes")
        if not 0 <= minimum_required_fraction <= 1:
            raise ValueError("minimum required fraction must be between 0 and 1")

        object.__setattr__(self, "grace_minutes", grace_minutes)
        object.__setattr__(self, "absent_after_minutes", absent_after_minutes)
        object.__setattr__(self, "minimum_required_fraction", minimum_required_fraction)

    def classify_arrival(self, session: ClassSession, arrived_at: object) -> tuple[str, int]:
        start = parse_iso(session.starts_at)
        arrival = parse_iso(arrived_at)
        minutes_late = int((arrival - start).total_seconds() // 60)

        if minutes_late <= self.grace_minutes:
            return PRESENT, 0
        if minutes_late >= self.absent_after_minutes:
            return ABSENT, 0
        return LATE, minutes_late

    def attendance_credit(self, status: str) -> float:
        if status == PRESENT:
            return 1.0
        if status == LATE:
            return 0.5
        if status == EXCUSED:
            return 1.0 if self.count_excused_as_present else 0.0
        if status == ABSENT:
            return 0.0
        raise ValueError(f"unsupported attendance status: {status}")