from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_code(value: object) -> str:
    text = clean_text(value).lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def course_code(value: object) -> str:
    text = clean_code(value).upper()
    if not text:
        raise ValueError("course code is required")
    return text


def programme_code(value: object) -> str:
    text = clean_code(value).upper()
    if not text:
        raise ValueError("programme code is required")
    return text


@dataclass(frozen=True)
class Course:
    code: str
    title: str
    credit_units: int
    department: str
    level: int
    prerequisites: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = course_code(self.code)
        title = clean_text(self.title)
        department = clean_text(self.department)
        level = int(self.level)
        credit_units = int(self.credit_units)

        if not title:
            raise ValueError("course title is required")
        if not department:
            raise ValueError("course department is required")
        if credit_units <= 0:
            raise ValueError("course credit units must be positive")
        if level < 1:
            raise ValueError("course level must be positive")

        prerequisites = tuple(sorted({course_code(item) for item in self.prerequisites}))
        tags = tuple(sorted({clean_code(item) for item in self.tags if clean_code(item)}))

        object.__setattr__(self, "code", code)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "credit_units", credit_units)
        object.__setattr__(self, "department", department)
        object.__setattr__(self, "level", level)
        object.__setattr__(self, "prerequisites", prerequisites)
        object.__setattr__(self, "tags", tags)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def requires(self, code: object) -> bool:
        return course_code(code) in self.prerequisites

    def has_tag(self, tag: object) -> bool:
        return clean_code(tag) in self.tags

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "credit_units": self.credit_units,
            "department": self.department,
            "level": self.level,
            "prerequisites": list(self.prerequisites),
            "tags": list(self.tags),
            "active": self.active,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Course":
        return cls(
            code=payload["code"],
            title=payload["title"],
            credit_units=int(payload["credit_units"]),
            department=payload["department"],
            level=int(payload["level"]),
            prerequisites=tuple(payload.get("prerequisites") or ()),
            tags=tuple(payload.get("tags") or ()),
            active=bool(payload.get("active", True)),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class CurriculumRule:
    rule_id: str
    description: str
    minimum_credit_units: int = 0
    required_courses: tuple[str, ...] = field(default_factory=tuple)
    required_tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        rule_id = clean_code(self.rule_id)
        description = clean_text(self.description)
        minimum_credit_units = int(self.minimum_credit_units)

        if not rule_id:
            raise ValueError("curriculum rule id is required")
        if not description:
            raise ValueError("curriculum rule description is required")
        if minimum_credit_units < 0:
            raise ValueError("minimum credit units cannot be negative")

        required_courses = tuple(sorted({course_code(item) for item in self.required_courses}))
        required_tags = tuple(sorted({clean_code(item) for item in self.required_tags if clean_code(item)}))

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "minimum_credit_units", minimum_credit_units)
        object.__setattr__(self, "required_courses", required_courses)
        object.__setattr__(self, "required_tags", required_tags)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "minimum_credit_units": self.minimum_credit_units,
            "required_courses": list(self.required_courses),
            "required_tags": list(self.required_tags),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CurriculumRule":
        return cls(
            rule_id=payload["rule_id"],
            description=payload["description"],
            minimum_credit_units=int(payload.get("minimum_credit_units", 0)),
            required_courses=tuple(payload.get("required_courses") or ()),
            required_tags=tuple(payload.get("required_tags") or ()),
        )


@dataclass(frozen=True)
class Programme:
    code: str
    name: str
    department: str
    duration_years: int
    required_credit_units: int
    rules: tuple[CurriculumRule, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = programme_code(self.code)
        name = clean_text(self.name)
        department = clean_text(self.department)
        duration_years = int(self.duration_years)
        required_credit_units = int(self.required_credit_units)

        if not name:
            raise ValueError("programme name is required")
        if not department:
            raise ValueError("programme department is required")
        if duration_years <= 0:
            raise ValueError("programme duration must be positive")
        if required_credit_units <= 0:
            raise ValueError("programme required credit units must be positive")

        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("programme has duplicate curriculum rules")

        object.__setattr__(self, "code", code)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "department", department)
        object.__setattr__(self, "duration_years", duration_years)
        object.__setattr__(self, "required_credit_units", required_credit_units)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "department": self.department,
            "duration_years": self.duration_years,
            "required_credit_units": self.required_credit_units,
            "rules": [rule.to_dict() for rule in self.rules],
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Programme":
        return cls(
            code=payload["code"],
            name=payload["name"],
            department=payload["department"],
            duration_years=int(payload["duration_years"]),
            required_credit_units=int(payload["required_credit_units"]),
            rules=tuple(CurriculumRule.from_dict(row) for row in payload.get("rules", ())),
            metadata=payload.get("metadata") or {},
        )


class CourseCatalog:
    def __init__(
        self,
        courses: Iterable[Course] | None = None,
        programmes: Iterable[Programme] | None = None,
    ) -> None:
        self._courses: dict[str, Course] = {}
        self._programmes: dict[str, Programme] = {}

        for course in courses or ():
            self.add_course(course)
        for programme in programmes or ():
            self.add_programme(programme)

    def add_course(self, course: Course) -> Course:
        if course.code in self._courses:
            raise ValueError(f"course already exists: {course.code}")

        missing = [code for code in course.prerequisites if code not in self._courses]
        if missing:
            raise KeyError(f"unknown prerequisite course(s): {', '.join(missing)}")

        self._courses[course.code] = course
        return course

    def add_programme(self, programme: Programme) -> Programme:
        if programme.code in self._programmes:
            raise ValueError(f"programme already exists: {programme.code}")
        self._programmes[programme.code] = programme
        return programme

    def get_course(self, code: object) -> Course:
        key = course_code(code)
        try:
            return self._courses[key]
        except KeyError as exc:
            raise KeyError(f"unknown course: {key}") from exc

    def get_programme(self, code: object) -> Programme:
        key = programme_code(code)
        try:
            return self._programmes[key]
        except KeyError as exc:
            raise KeyError(f"unknown programme: {key}") from exc

    def courses_by_department(self, department: object) -> list[Course]:
        wanted = clean_text(department)
        return sorted(
            [course for course in self._courses.values() if course.department == wanted],
            key=lambda item: (item.level, item.code),
        )

    def courses_by_tag(self, tag: object) -> list[Course]:
        wanted = clean_code(tag)
        return sorted(
            [course for course in self._courses.values() if wanted in course.tags],
            key=lambda item: (item.level, item.code),
        )

    def inactive_courses(self) -> list[Course]:
        return sorted(
            [course for course in self._courses.values() if not course.active],
            key=lambda item: item.code,
        )

    def prerequisite_chain(self, code: object) -> list[str]:
        target = self.get_course(code)
        visited: set[str] = set()
        chain: list[str] = []

        def walk(course: Course) -> None:
            for prerequisite in course.prerequisites:
                if prerequisite in visited:
                    continue
                visited.add(prerequisite)
                walk(self.get_course(prerequisite))
                chain.append(prerequisite)

        walk(target)
        return chain

    def validate_prerequisite_graph(self) -> dict[str, Any]:
        visiting: set[str] = set()
        visited: set[str] = set()
        cycles: list[list[str]] = []

        def walk(code: str, path: list[str]) -> None:
            if code in visiting:
                start = path.index(code) if code in path else 0
                cycles.append(path[start:] + [code])
                return
            if code in visited:
                return

            visiting.add(code)
            path.append(code)
            course = self._courses[code]
            for prerequisite in course.prerequisites:
                if prerequisite in self._courses:
                    walk(prerequisite, path)
            path.pop()
            visiting.remove(code)
            visited.add(code)

        for code in sorted(self._courses):
            walk(code, [])

        return {
            "course_count": len(self._courses),
            "valid": not cycles,
            "cycles": cycles,
        }

    def graduation_audit(self, programme_code_value: object, completed_courses: Iterable[object]) -> dict[str, Any]:
        programme = self.get_programme(programme_code_value)
        completed = {course_code(item) for item in completed_courses}
        known_completed = [self._courses[code] for code in completed if code in self._courses]
        completed_credit_units = sum(course.credit_units for course in known_completed)

        missing_required: list[str] = []
        tag_credit_units: dict[str, int] = {}

        for rule in programme.rules:
            for required in rule.required_courses:
                if required not in completed:
                    missing_required.append(required)

            if rule.required_tags:
                credit_units = sum(
                    course.credit_units
                    for course in known_completed
                    if set(rule.required_tags).intersection(set(course.tags))
                )
                tag_credit_units[rule.rule_id] = credit_units
                if credit_units < rule.minimum_credit_units:
                    missing_required.append(rule.rule_id)

        missing_credit_units = max(programme.required_credit_units - completed_credit_units, 0)

        return {
            "programme_code": programme.code,
            "completed_course_count": len(known_completed),
            "completed_credit_units": completed_credit_units,
            "required_credit_units": programme.required_credit_units,
            "missing_credit_units": missing_credit_units,
            "missing_requirements": sorted(set(missing_required)),
            "eligible": missing_credit_units == 0 and not missing_required,
            "tag_credit_units": dict(sorted(tag_credit_units.items())),
        }

    def recommend_next_courses(
        self,
        completed_courses: Iterable[object],
        *,
        max_level: int | None = None,
        tags: Iterable[object] | None = None,
    ) -> list[Course]:
        completed = {course_code(item) for item in completed_courses}
        wanted_tags = {clean_code(item) for item in tags or () if clean_code(item)}

        candidates: list[Course] = []
        for course in self._courses.values():
            if not course.active or course.code in completed:
                continue
            if max_level is not None and course.level > int(max_level):
                continue
            if wanted_tags and not wanted_tags.intersection(set(course.tags)):
                continue
            if set(course.prerequisites).issubset(completed):
                candidates.append(course)

        return sorted(candidates, key=lambda item: (item.level, item.code))

    def to_dict(self) -> dict[str, Any]:
        return {
            "courses": [course.to_dict() for course in sorted(self._courses.values(), key=lambda item: item.code)],
            "programmes": [
                programme.to_dict()
                for programme in sorted(self._programmes.values(), key=lambda item: item.code)
            ],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> "CourseCatalog":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        courses = [Course.from_dict(row) for row in payload.get("courses", ())]
        programmes = [Programme.from_dict(row) for row in payload.get("programmes", ())]
        return cls(courses=courses, programmes=programmes)

    def __len__(self) -> int:
        return len(self._courses)
