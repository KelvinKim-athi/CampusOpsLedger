from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


CENT = Decimal("0.01")


def money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def clean_key(value: object) -> str:
    text = str(value).strip().lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


@dataclass(frozen=True)
class ReconciliationLine:
    source: str
    reference: str
    amount: Decimal | str | int | float

    def __post_init__(self) -> None:
        source = clean_key(self.source)
        reference = clean_key(self.reference)
        if not source:
            raise ValueError("reconciliation source is required")
        if not reference:
            raise ValueError("reconciliation reference is required")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "reference", reference)
        object.__setattr__(self, "amount", money(self.amount))


class ReconciliationEngine:
    def compare(
        self,
        left: Iterable[ReconciliationLine],
        right: Iterable[ReconciliationLine],
        *,
        tolerance: Decimal | str | int | float = "0.00",
    ) -> dict[str, object]:
        tolerance_amount = money(tolerance)
        left_map = {line.reference: line for line in left}
        right_map = {line.reference: line for line in right}

        matched = []
        amount_mismatches = []
        missing_left = []
        missing_right = []

        for reference in sorted(set(left_map) | set(right_map)):
            left_line = left_map.get(reference)
            right_line = right_map.get(reference)

            if left_line and not right_line:
                missing_right.append(reference)
                continue
            if right_line and not left_line:
                missing_left.append(reference)
                continue

            assert left_line is not None and right_line is not None
            diff = abs(left_line.amount - right_line.amount)
            if diff <= tolerance_amount:
                matched.append(reference)
            else:
                amount_mismatches.append(
                    {
                        "reference": reference,
                        "left": str(left_line.amount),
                        "right": str(right_line.amount),
                        "difference": str(diff.quantize(CENT)),
                    }
                )

        return {
            "matched_count": len(matched),
            "mismatch_count": len(amount_mismatches),
            "missing_left_count": len(missing_left),
            "missing_right_count": len(missing_right),
            "matched": matched,
            "amount_mismatches": amount_mismatches,
            "missing_left": missing_left,
            "missing_right": missing_right,
        }
