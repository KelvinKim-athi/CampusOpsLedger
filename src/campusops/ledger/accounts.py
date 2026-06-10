from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


CENT = Decimal("0.01")
CHARGE = "charge"
PAYMENT = "payment"
WAIVER = "waiver"
REFUND = "refund"

VALID_LINE_KINDS = {CHARGE, PAYMENT, WAIVER, REFUND}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_code(value: object) -> str:
    text = clean_text(value).lower()
    for mark in (" ", "-", "."):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def clean_student_id(value: object) -> str:
    text = clean_text(value).upper().replace(" ", "")
    if not text:
        raise ValueError("student id is required")
    return text


def money(value: object) -> Decimal:
    amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    return amount


@dataclass(frozen=True)
class LedgerLine:
    line_id: str
    student_id: str
    account_code: str
    term: str
    amount: Decimal | str | int | float
    kind: str
    description: str
    posted_at: str = field(default_factory=utc_now_iso)
    reference: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        line_id = clean_code(self.line_id)
        student_id = clean_student_id(self.student_id)
        account_code = clean_code(self.account_code)
        term = clean_text(self.term).upper()
        kind = clean_code(self.kind)
        description = clean_text(self.description)
        reference = clean_text(self.reference)
        amount = money(self.amount)

        if not line_id:
            raise ValueError("ledger line id is required")
        if not account_code:
            raise ValueError("ledger account code is required")
        if not term:
            raise ValueError("ledger term is required")
        if kind not in VALID_LINE_KINDS:
            raise ValueError(f"unsupported ledger line kind: {self.kind}")
        if amount <= 0:
            raise ValueError("ledger amount must be positive")
        if not description:
            raise ValueError("ledger description is required")

        object.__setattr__(self, "line_id", line_id)
        object.__setattr__(self, "student_id", student_id)
        object.__setattr__(self, "account_code", account_code)
        object.__setattr__(self, "term", term)
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    @property
    def signed_amount(self) -> Decimal:
        if self.kind in {CHARGE, REFUND}:
            return self.amount
        return -self.amount

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_id": self.line_id,
            "student_id": self.student_id,
            "account_code": self.account_code,
            "term": self.term,
            "amount": str(self.amount),
            "kind": self.kind,
            "description": self.description,
            "posted_at": self.posted_at,
            "reference": self.reference,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LedgerLine":
        return cls(
            line_id=payload["line_id"],
            student_id=payload["student_id"],
            account_code=payload["account_code"],
            term=payload["term"],
            amount=payload["amount"],
            kind=payload["kind"],
            description=payload["description"],
            posted_at=payload.get("posted_at") or utc_now_iso(),
            reference=payload.get("reference", ""),
            metadata=payload.get("metadata") or {},
        )