from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def clean_key(value: object) -> str:
    text = str(value).strip().lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


@dataclass(frozen=True)
class WorkItem:
    item_id: str
    owner: str
    effort_points: int = 1
    priority: str = "normal"

    def __post_init__(self) -> None:
        item_id = clean_key(self.item_id)
        owner = clean_key(self.owner)
        effort_points = int(self.effort_points)
        priority = clean_key(self.priority) or "normal"

        if not item_id:
            raise ValueError("work item id is required")
        if not owner:
            raise ValueError("work item owner is required")
        if effort_points <= 0:
            raise ValueError("effort points must be positive")

        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "effort_points", effort_points)
        object.__setattr__(self, "priority", priority)


class WorkloadBalancer:
    def workload(self, items: Iterable[WorkItem]) -> dict[str, int]:
        load: dict[str, int] = {}
        for item in items:
            load[item.owner] = load.get(item.owner, 0) + item.effort_points
        return dict(sorted(load.items()))

    def lightest_owner(self, owners: Iterable[object], items: Iterable[WorkItem]) -> str:
        owner_list = [clean_key(owner) for owner in owners if clean_key(owner)]
        if not owner_list:
            raise ValueError("at least one owner is required")

        load = {owner: 0 for owner in owner_list}
        for item in items:
            if item.owner in load:
                load[item.owner] += item.effort_points

        return sorted(load.items(), key=lambda pair: (pair[1], pair[0]))[0][0]

    def rebalance_plan(self, owners: Iterable[object], items: Iterable[WorkItem]) -> dict[str, object]:
        owner_list = [clean_key(owner) for owner in owners if clean_key(owner)]
        assignments: dict[str, list[str]] = {owner: [] for owner in owner_list}
        load: dict[str, int] = {owner: 0 for owner in owner_list}

        weight = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        sorted_items = sorted(items, key=lambda item: (weight.get(item.priority, 9), -item.effort_points, item.item_id))

        for item in sorted_items:
            owner = sorted(load.items(), key=lambda pair: (pair[1], pair[0]))[0][0]
            assignments[owner].append(item.item_id)
            load[owner] += item.effort_points

        return {"assignments": assignments, "load": load}
