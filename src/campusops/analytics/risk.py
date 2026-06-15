from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable


def clean_key(value: object) -> str:
    text = str(value).strip().lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


@dataclass(frozen=True)
class RiskFactor:
    factor_id: str
    field: str
    operator: str
    expected: str
    weight: int
    label: str = ""

    def __post_init__(self) -> None:
        factor_id = clean_key(self.factor_id)
        field_name = clean_key(self.field)
        operator = clean_key(self.operator)
        if not factor_id:
            raise ValueError("risk factor id is required")
        if not field_name:
            raise ValueError("risk field is required")
        if operator not in {"equals", "not_equals", "contains", "gte", "gt", "lte", "lt", "exists", "missing"}:
            raise ValueError(f"unsupported risk operator: {self.operator}")

        object.__setattr__(self, "factor_id", factor_id)
        object.__setattr__(self, "field", field_name)
        object.__setattr__(self, "operator", operator)
        object.__setattr__(self, "label", self.label or factor_id)

    def matches(self, payload: dict[str, object]) -> bool:
        value = payload.get(self.field)

        if self.operator == "exists":
            return self.field in payload and value not in {None, ""}
        if self.operator == "missing":
            return self.field not in payload or value in {None, ""}
        if value is None:
            return False

        actual = str(value).strip()
        expected = str(self.expected).strip()

        if self.operator == "equals":
            return actual == expected
        if self.operator == "not_equals":
            return actual != expected
        if self.operator == "contains":
            return expected.lower() in actual.lower()

        actual_num = Decimal(actual)
        expected_num = Decimal(expected)

        if self.operator == "gte":
            return actual_num >= expected_num
        if self.operator == "gt":
            return actual_num > expected_num
        if self.operator == "lte":
            return actual_num <= expected_num
        if self.operator == "lt":
            return actual_num < expected_num
        return False


@dataclass(frozen=True)
class RiskProfile:
    subject_id: str
    payload: dict[str, Any]
    base_score: int = 0
    matched_factors: tuple[str, ...] = field(default_factory=tuple)
    score: int = 0

    def band(self) -> str:
        if self.score >= 80:
            return "critical"
        if self.score >= 60:
            return "high"
        if self.score >= 35:
            return "medium"
        return "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "score": self.score,
            "band": self.band(),
            "matched_factors": list(self.matched_factors),
            "payload": dict(self.payload),
        }


class RiskScorer:
    def __init__(self, factors: Iterable[RiskFactor] | None = None) -> None:
        self._factors: list[RiskFactor] = list(factors or ())

    def add_factor(self, factor: RiskFactor) -> RiskFactor:
        if any(existing.factor_id == factor.factor_id for existing in self._factors):
            raise ValueError(f"risk factor already exists: {factor.factor_id}")
        self._factors.append(factor)
        return factor

    def score(self, subject_id: object, payload: dict[str, object], *, base_score: int = 0) -> RiskProfile:
        matched: list[str] = []
        score = int(base_score)

        normalized = {clean_key(key): value for key, value in payload.items()}

        for factor in self._factors:
            if factor.matches(normalized):
                matched.append(factor.factor_id)
                score += factor.weight

        return RiskProfile(
            subject_id=str(subject_id).strip(),
            payload=normalized,
            base_score=int(base_score),
            matched_factors=tuple(sorted(matched)),
            score=max(score, 0),
        )

    def rank(self, rows: Iterable[tuple[object, dict[str, object]]], *, base_score: int = 0) -> list[RiskProfile]:
        profiles = [self.score(subject_id, payload, base_score=base_score) for subject_id, payload in rows]
        return sorted(profiles, key=lambda item: (-item.score, item.subject_id))
