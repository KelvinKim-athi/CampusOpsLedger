from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_key(value: object) -> str:
    text = clean_text(value).lower()
    for mark in (" ", "-", "."):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def clean_question_id(value: object) -> str:
    text = clean_key(value)
    if not text:
        raise ValueError("question id is required")
    return text


def clean_student_id(value: object) -> str:
    text = clean_text(value).upper().replace(" ", "")
    if not text:
        raise ValueError("student id is required")
    return text


def normalize_answer(value: object) -> str:
    text = clean_text(value).casefold()
    for mark in ("\t", "\n", "\r"):
        text = text.replace(mark, " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.strip()


@dataclass(frozen=True)
class Question:
    question_id: str
    prompt: str
    topic: str
    correct_answer: str
    points: float = 1.0
    choices: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        question_id = clean_question_id(self.question_id)
        prompt = clean_text(self.prompt)
        topic = clean_key(self.topic)
        correct_answer = normalize_answer(self.correct_answer)
        points = float(self.points)

        if not prompt:
            raise ValueError("question prompt is required")
        if not topic:
            raise ValueError("question topic is required")
        if not correct_answer:
            raise ValueError("question correct answer is required")
        if points <= 0:
            raise ValueError("question points must be positive")

        choices = tuple(clean_text(choice) for choice in self.choices if clean_text(choice))

        object.__setattr__(self, "question_id", question_id)
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "topic", topic)
        object.__setattr__(self, "correct_answer", correct_answer)
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "choices", choices)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def is_correct(self, answer: object) -> bool:
        return normalize_answer(answer) == self.correct_answer

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "prompt": self.prompt,
            "topic": self.topic,
            "correct_answer": self.correct_answer,
            "points": self.points,
            "choices": list(self.choices),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Question":
        return cls(
            question_id=payload["question_id"],
            prompt=payload["prompt"],
            topic=payload["topic"],
            correct_answer=payload["correct_answer"],
            points=payload.get("points", 1.0),
            choices=tuple(payload.get("choices") or ()),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class Assessment:
    assessment_id: str
    title: str
    programme: str
    questions: tuple[Question, ...]
    published: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        assessment_id = clean_key(self.assessment_id)
        title = clean_text(self.title)
        programme = clean_text(self.programme)

        if not assessment_id:
            raise ValueError("assessment id is required")
        if not title:
            raise ValueError("assessment title is required")
        if not programme:
            raise ValueError("assessment programme is required")
        if not self.questions:
            raise ValueError("assessment must have at least one question")

        question_ids = [question.question_id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("assessment has duplicate question ids")

        object.__setattr__(self, "assessment_id", assessment_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "programme", programme)
        object.__setattr__(self, "questions", tuple(self.questions))
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    @property
    def total_points(self) -> float:
        return sum(question.points for question in self.questions)

    def question_map(self) -> dict[str, Question]:
        return {question.question_id: question for question in self.questions}

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "title": self.title,
            "programme": self.programme,
            "published": self.published,
            "questions": [question.to_dict() for question in self.questions],
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Assessment":
        return cls(
            assessment_id=payload["assessment_id"],
            title=payload["title"],
            programme=payload["programme"],
            published=bool(payload.get("published", False)),
            questions=tuple(Question.from_dict(row) for row in payload.get("questions", ())),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class AssessmentAttempt:
    attempt_id: str
    student_id: str
    assessment_id: str
    responses: dict[str, Any]
    submitted_at: str = field(default_factory=utc_now_iso)
    late_minutes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        attempt_id = clean_key(self.attempt_id)
        student_id = clean_student_id(self.student_id)
        assessment_id = clean_key(self.assessment_id)

        if not attempt_id:
            raise ValueError("attempt id is required")
        if not assessment_id:
            raise ValueError("assessment id is required")

        late_minutes = int(self.late_minutes)
        if late_minutes < 0:
            raise ValueError("late minutes cannot be negative")

        cleaned_responses: dict[str, Any] = {}
        for key, value in self.responses.items():
            question_id = clean_question_id(key)
            cleaned_responses[question_id] = deepcopy(value)

        object.__setattr__(self, "attempt_id", attempt_id)
        object.__setattr__(self, "student_id", student_id)
        object.__setattr__(self, "assessment_id", assessment_id)
        object.__setattr__(self, "responses", cleaned_responses)
        object.__setattr__(self, "late_minutes", late_minutes)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "student_id": self.student_id,
            "assessment_id": self.assessment_id,
            "responses": deepcopy(self.responses),
            "submitted_at": self.submitted_at,
            "late_minutes": self.late_minutes,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AssessmentAttempt":
        return cls(
            attempt_id=payload["attempt_id"],
            student_id=payload["student_id"],
            assessment_id=payload["assessment_id"],
            responses=payload.get("responses") or {},
            submitted_at=payload.get("submitted_at") or utc_now_iso(),
            late_minutes=int(payload.get("late_minutes", 0)),
            metadata=payload.get("metadata") or {},
        )