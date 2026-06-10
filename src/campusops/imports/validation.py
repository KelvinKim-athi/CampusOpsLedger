from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_key(value: object) -> str:
    text = clean_text(value).lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


@dataclass(frozen=True)
class ImportIssue:
    row_number: int
    code: str
    message: str
    row: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        row_number = int(self.row_number)
        code = clean_key(self.code)
        message = clean_text(self.message)

        if row_number < 1:
            raise ValueError("import issue row number must be positive")
        if not code:
            raise ValueError("import issue code is required")
        if not message:
            raise ValueError("import issue message is required")

        object.__setattr__(self, "row_number", row_number)
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "row", deepcopy(dict(self.row)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_number": self.row_number,
            "code": self.code,
            "message": self.message,
            "row": deepcopy(self.row),
        }


@dataclass
class ImportResult:
    job_name: str
    accepted: int = 0
    rejected: int = 0
    issues: list[ImportIssue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_accept(self, count: int = 1) -> None:
        self.accepted += int(count)

    def add_issue(self, issue: ImportIssue) -> None:
        self.issues.append(issue)
        self.rejected += 1

    @property
    def total_rows(self) -> int:
        return self.accepted + self.rejected

    @property
    def ok(self) -> bool:
        return self.rejected == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_name": clean_key(self.job_name),
            "accepted": self.accepted,
            "rejected": self.rejected,
            "total_rows": self.total_rows,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
            "metadata": deepcopy(dict(self.metadata)),
        }