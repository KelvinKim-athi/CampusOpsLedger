from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from campusops.assessments.models import Assessment, AssessmentAttempt, normalize_answer


@dataclass(frozen=True)
class ScorePolicy:
    passing_fraction: float = 0.5
    late_penalty_per_minute: float = 0.0
    max_late_penalty: float = 0.0
    topic_weights: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        passing_fraction = float(self.passing_fraction)
        late_penalty_per_minute = float(self.late_penalty_per_minute)
        max_late_penalty = float(self.max_late_penalty)

        if not 0 <= passing_fraction <= 1:
            raise ValueError("passing fraction must be between 0 and 1")
        if late_penalty_per_minute < 0:
            raise ValueError("late penalty per minute cannot be negative")
        if max_late_penalty < 0:
            raise ValueError("max late penalty cannot be negative")

        weights = {str(key).strip().lower(): float(value) for key, value in self.topic_weights.items()}
        for topic, weight in weights.items():
            if not topic:
                raise ValueError("topic weight cannot have a blank topic")
            if weight <= 0:
                raise ValueError("topic weight must be positive")

        object.__setattr__(self, "passing_fraction", passing_fraction)
        object.__setattr__(self, "late_penalty_per_minute", late_penalty_per_minute)
        object.__setattr__(self, "max_late_penalty", max_late_penalty)
        object.__setattr__(self, "topic_weights", weights)


@dataclass(frozen=True)
class ScoreResult:
    attempt_id: str
    student_id: str
    assessment_id: str
    raw_points: float
    adjusted_points: float
    total_points: float
    fraction: float
    passed: bool
    topic_breakdown: dict[str, dict[str, float]]
    missing_questions: tuple[str, ...]
    extra_responses: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "student_id": self.student_id,
            "assessment_id": self.assessment_id,
            "raw_points": self.raw_points,
            "adjusted_points": self.adjusted_points,
            "total_points": self.total_points,
            "fraction": self.fraction,
            "passed": self.passed,
            "topic_breakdown": deepcopy(self.topic_breakdown),
            "missing_questions": list(self.missing_questions),
            "extra_responses": list(self.extra_responses),
        }


def score_attempt(
    assessment: Assessment,
    attempt: AssessmentAttempt,
    *,
    policy: ScorePolicy | None = None,
) -> ScoreResult:
    if assessment.assessment_id != attempt.assessment_id:
        raise ValueError("attempt belongs to a different assessment")

    active_policy = policy or ScorePolicy()
    questions = assessment.question_map()

    raw_points = 0.0
    total_points = 0.0
    topic_breakdown: dict[str, dict[str, float]] = {}

    for question in assessment.questions:
        topic_weight = active_policy.topic_weights.get(question.topic, 1.0)
        weighted_points = question.points * topic_weight
        total_points += weighted_points

        row = topic_breakdown.setdefault(question.topic, {"earned": 0.0, "possible": 0.0, "correct": 0.0, "count": 0.0})
        row["possible"] += weighted_points
        row["count"] += 1.0

        answer = attempt.responses.get(question.question_id)
        if answer is not None and normalize_answer(answer) == question.correct_answer:
            raw_points += weighted_points
            row["earned"] += weighted_points
            row["correct"] += 1.0

    missing_questions = tuple(
        question_id for question_id in questions if question_id not in attempt.responses
    )
    extra_responses = tuple(
        question_id for question_id in sorted(attempt.responses) if question_id not in questions
    )

    penalty = attempt.late_minutes * active_policy.late_penalty_per_minute
    penalty = min(penalty, active_policy.max_late_penalty)
    adjusted_points = max(0.0, raw_points - penalty)

    fraction = adjusted_points / total_points if total_points else 0.0

    return ScoreResult(
        attempt_id=attempt.attempt_id,
        student_id=attempt.student_id,
        assessment_id=attempt.assessment_id,
        raw_points=round(raw_points, 4),
        adjusted_points=round(adjusted_points, 4),
        total_points=round(total_points, 4),
        fraction=round(fraction, 6),
        passed=fraction >= active_policy.passing_fraction,
        topic_breakdown={topic: {key: round(value, 4) for key, value in row.items()} for topic, row in topic_breakdown.items()},
        missing_questions=missing_questions,
        extra_responses=extra_responses,
    )