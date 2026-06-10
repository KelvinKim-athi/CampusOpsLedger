from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Iterable

from campusops.ledger.accounts import clean_code, clean_text, money


@dataclass(frozen=True)
class FeeItem:
    item_code: str
    description: str
    amount: Decimal | str | int | float
    account_code: str
    years: tuple[int, ...] = field(default_factory=tuple)
    programmes: tuple[str, ...] = field(default_factory=tuple)
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        item_code = clean_code(self.item_code)
        description = clean_text(self.description)
        account_code = clean_code(self.account_code)
        amount = money(self.amount)

        if not item_code:
            raise ValueError("fee item code is required")
        if not description:
            raise ValueError("fee item description is required")
        if not account_code:
            raise ValueError("fee account code is required")
        if amount <= 0:
            raise ValueError("fee amount must be positive")

        years = tuple(sorted({int(year) for year in self.years}))
        if any(year < 1 for year in years):
            raise ValueError("fee years must be positive")

        programmes = tuple(sorted({clean_text(programme) for programme in self.programmes if clean_text(programme)}))

        object.__setattr__(self, "item_code", item_code)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "account_code", account_code)
        object.__setattr__(self, "years", years)
        object.__setattr__(self, "programmes", programmes)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def applies_to(self, student: object) -> bool:
        student_year = int(getattr(student, "year"))
        student_programme = clean_text(getattr(student, "programme"))

        if self.years and student_year not in self.years:
            return False
        if self.programmes and student_programme not in self.programmes:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_code": self.item_code,
            "description": self.description,
            "amount": str(self.amount),
            "account_code": self.account_code,
            "years": list(self.years),
            "programmes": list(self.programmes),
            "required": self.required,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FeeItem":
        return cls(
            item_code=payload["item_code"],
            description=payload["description"],
            amount=payload["amount"],
            account_code=payload["account_code"],
            years=tuple(payload.get("years") or ()),
            programmes=tuple(payload.get("programmes") or ()),
            required=bool(payload.get("required", True)),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class FeeSchedule:
    schedule_id: str
    title: str
    items: tuple[FeeItem, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        schedule_id = clean_code(self.schedule_id)
        title = clean_text(self.title)

        if not schedule_id:
            raise ValueError("fee schedule id is required")
        if not title:
            raise ValueError("fee schedule title is required")
        if not self.items:
            raise ValueError("fee schedule must have at least one item")

        item_codes = [item.item_code for item in self.items]
        if len(item_codes) != len(set(item_codes)):
            raise ValueError("fee schedule has duplicate item codes")

        object.__setattr__(self, "schedule_id", schedule_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def expected_items(self, student: object) -> list[FeeItem]:
        return [item for item in self.items if item.applies_to(student)]

    def total_for(self, student: object) -> Decimal:
        return sum((item.amount for item in self.expected_items(student)), Decimal("0.00"))

    def to_records(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.items]

    @classmethod
    def from_records(
        cls,
        *,
        schedule_id: str,
        title: str,
        records: Iterable[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> "FeeSchedule":
        return cls(
            schedule_id=schedule_id,
            title=title,
            items=tuple(FeeItem.from_dict(record) for record in records),
            metadata=metadata or {},
        )