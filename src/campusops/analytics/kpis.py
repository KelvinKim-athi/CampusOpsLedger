from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable


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
class KpiPoint:
    metric: str
    value: Decimal | str | int | float
    unit: str = "count"
    group: str = "overall"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        metric = clean_key(self.metric)
        group = clean_key(self.group) or "overall"
        unit = clean_key(self.unit) or "count"
        if not metric:
            raise ValueError("metric is required")
        object.__setattr__(self, "metric", metric)
        object.__setattr__(self, "group", group)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "value", money(self.value))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "value": str(self.value),
            "unit": self.unit,
            "group": self.group,
            "metadata": dict(self.metadata),
        }


class KpiDashboard:
    def __init__(self, points: Iterable[KpiPoint] | None = None) -> None:
        self._points: list[KpiPoint] = list(points or ())

    def add(self, point: KpiPoint) -> KpiPoint:
        self._points.append(point)
        return point

    def points(self) -> list[KpiPoint]:
        return list(self._points)

    def by_metric(self, metric: object) -> list[KpiPoint]:
        wanted = clean_key(metric)
        return [point for point in self._points if point.metric == wanted]

    def by_group(self, group: object) -> list[KpiPoint]:
        wanted = clean_key(group) or "overall"
        return [point for point in self._points if point.group == wanted]

    def total(self, metric: object, *, group: object | None = None) -> Decimal:
        points = self.by_metric(metric)
        if group is not None:
            wanted = clean_key(group) or "overall"
            points = [point for point in points if point.group == wanted]
        return sum((point.value for point in points), Decimal("0.00")).quantize(CENT)

    def average(self, metric: object, *, group: object | None = None) -> Decimal:
        points = self.by_metric(metric)
        if group is not None:
            wanted = clean_key(group) or "overall"
            points = [point for point in points if point.group == wanted]
        if not points:
            return Decimal("0.00")
        return (sum((point.value for point in points), Decimal("0.00")) / Decimal(len(points))).quantize(CENT)

    def metric_summary(self) -> dict[str, dict[str, str | int]]:
        summary: dict[str, dict[str, Decimal | int]] = {}
        for point in self._points:
            bucket = summary.setdefault(point.metric, {"count": 0, "total": Decimal("0.00")})
            bucket["count"] = int(bucket["count"]) + 1
            bucket["total"] = Decimal(bucket["total"]) + point.value

        output: dict[str, dict[str, str | int]] = {}
        for metric, values in sorted(summary.items()):
            count = int(values["count"])
            total = Decimal(values["total"]).quantize(CENT)
            average = (total / Decimal(count)).quantize(CENT) if count else Decimal("0.00")
            output[metric] = {"count": count, "total": str(total), "average": str(average)}
        return output

    def group_summary(self) -> dict[str, dict[str, str | int]]:
        summary: dict[str, dict[str, Decimal | int]] = {}
        for point in self._points:
            bucket = summary.setdefault(point.group, {"count": 0, "total": Decimal("0.00")})
            bucket["count"] = int(bucket["count"]) + 1
            bucket["total"] = Decimal(bucket["total"]) + point.value

        return {
            group: {"count": int(values["count"]), "total": str(Decimal(values["total"]).quantize(CENT))}
            for group, values in sorted(summary.items())
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_count": len(self._points),
            "metrics": self.metric_summary(),
            "groups": self.group_summary(),
            "points": [point.to_dict() for point in self._points],
        }
