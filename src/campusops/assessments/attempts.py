from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from campusops.assessments.models import Assessment, AssessmentAttempt
from campusops.assessments.scoring import ScorePolicy, ScoreResult, score_attempt
from campusops.audit.ledger import AuditLedger


class AssessmentBook:
    def __init__(
        self,
        assessments: Iterable[Assessment] | None = None,
        attempts: Iterable[AssessmentAttempt] | None = None,
        *,
        audit: AuditLedger | None = None,
    ) -> None:
        self._assessments: dict[str, Assessment] = {}
        self._attempts: dict[str, AssessmentAttempt] = {}
        self.audit = audit or AuditLedger()

        for assessment in assessments or ():
            self._assessments[assessment.assessment_id] = assessment
        for attempt in attempts or ():
            self._attempts[attempt.attempt_id] = attempt

    def add_assessment(self, assessment: Assessment, *, actor: str = "system") -> Assessment:
        if assessment.assessment_id in self._assessments:
            raise ValueError(f"assessment already exists: {assessment.assessment_id}")

        self._assessments[assessment.assessment_id] = assessment
        self.audit.record(
            event_type="assessment.created",
            actor=actor,
            entity_type="assessment",
            entity_id=assessment.assessment_id,
            message=f"Created assessment {assessment.title}",
            metadata={
                "programme": assessment.programme,
                "question_count": len(assessment.questions),
                "published": assessment.published,
            },
        )
        return assessment

    def publish(self, assessment_id: object, *, actor: str = "system") -> Assessment:
        assessment = self.get_assessment(assessment_id)
        updated = Assessment(
            assessment_id=assessment.assessment_id,
            title=assessment.title,
            programme=assessment.programme,
            questions=assessment.questions,
            published=True,
            metadata=assessment.metadata,
        )
        self._assessments[updated.assessment_id] = updated
        self.audit.record(
            event_type="assessment.published",
            actor=actor,
            entity_type="assessment",
            entity_id=updated.assessment_id,
            message=f"Published assessment {updated.title}",
            metadata={"question_count": len(updated.questions)},
        )
        return updated

    def get_assessment(self, assessment_id: object) -> Assessment:
        key = str(assessment_id).strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        while "__" in key:
            key = key.replace("__", "_")
        key = key.strip("_")
        try:
            return self._assessments[key]
        except KeyError as exc:
            raise KeyError(f"unknown assessment: {key}") from exc

    def submit_attempt(
        self,
        attempt: AssessmentAttempt,
        *,
        actor: str = "system",
        allow_unpublished: bool = False,
    ) -> AssessmentAttempt:
        if attempt.attempt_id in self._attempts:
            raise ValueError(f"attempt already exists: {attempt.attempt_id}")

        assessment = self.get_assessment(attempt.assessment_id)
        if not assessment.published and not allow_unpublished:
            raise ValueError(f"assessment is not published: {assessment.assessment_id}")

        self._attempts[attempt.attempt_id] = attempt
        self.audit.record(
            event_type="assessment.attempt_submitted",
            actor=actor,
            entity_type="assessment_attempt",
            entity_id=attempt.attempt_id,
            message=f"Submitted attempt {attempt.attempt_id}",
            metadata={
                "student_id": attempt.student_id,
                "assessment_id": attempt.assessment_id,
                "response_count": len(attempt.responses),
                "late_minutes": attempt.late_minutes,
            },
        )
        return attempt

    def get_attempt(self, attempt_id: object) -> AssessmentAttempt:
        key = str(attempt_id).strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        while "__" in key:
            key = key.replace("__", "_")
        key = key.strip("_")
        try:
            return self._attempts[key]
        except KeyError as exc:
            raise KeyError(f"unknown attempt: {key}") from exc

    def attempts_for_student(self, student_id: object) -> list[AssessmentAttempt]:
        key = str(student_id).strip().upper().replace(" ", "")
        return sorted(
            [attempt for attempt in self._attempts.values() if attempt.student_id == key],
            key=lambda attempt: (attempt.assessment_id, attempt.submitted_at, attempt.attempt_id),
        )

    def score(self, attempt_id: object, *, policy: ScorePolicy | None = None) -> ScoreResult:
        attempt = self.get_attempt(attempt_id)
        assessment = self.get_assessment(attempt.assessment_id)
        return score_attempt(assessment, attempt, policy=policy)

    def leaderboard(self, assessment_id: object, *, policy: ScorePolicy | None = None) -> list[ScoreResult]:
        assessment = self.get_assessment(assessment_id)
        results: list[ScoreResult] = []

        for attempt in self._attempts.values():
            if attempt.assessment_id == assessment.assessment_id:
                results.append(score_attempt(assessment, attempt, policy=policy))

        return sorted(
            results,
            key=lambda result: (-result.adjusted_points, result.student_id, result.attempt_id),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "assessments": [
                assessment.to_dict()
                for assessment in sorted(self._assessments.values(), key=lambda item: item.assessment_id)
            ],
            "attempts": [
                attempt.to_dict()
                for attempt in sorted(self._attempts.values(), key=lambda item: item.attempt_id)
            ],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path, *, audit: AuditLedger | None = None) -> "AssessmentBook":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        assessments = [Assessment.from_dict(row) for row in payload.get("assessments", ())]
        attempts = [AssessmentAttempt.from_dict(row) for row in payload.get("attempts", ())]
        return cls(assessments=assessments, attempts=attempts, audit=audit)

    def __len__(self) -> int:
        return len(self._assessments)