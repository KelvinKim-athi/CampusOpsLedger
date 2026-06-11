from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


AVAILABLE = "available"
ASSIGNED = "assigned"
MAINTENANCE = "maintenance"
RETIRED = "retired"

OPEN = "open"
IN_PROGRESS = "in_progress"
RESOLVED = "resolved"
CLOSED = "closed"

CENT = Decimal("0.01")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_iso(value: object) -> datetime:
    text = clean_text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Asset:
    asset_id: str
    asset_tag: str
    name: str
    category: str
    purchase_cost: Decimal | str | int | float
    acquired_at: str
    location: str = ""
    assigned_to: str = ""
    status: str = AVAILABLE
    useful_life_months: int = 36
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        asset_id = clean_code(self.asset_id)
        asset_tag = clean_code(self.asset_tag).upper()
        name = clean_text(self.name)
        category = clean_code(self.category)
        location = clean_text(self.location)
        assigned_to = clean_text(self.assigned_to)
        status = clean_code(self.status)
        purchase_cost = money(self.purchase_cost)
        useful_life_months = int(self.useful_life_months)

        if not asset_id:
            raise ValueError("asset id is required")
        if not asset_tag:
            raise ValueError("asset tag is required")
        if not name:
            raise ValueError("asset name is required")
        if not category:
            raise ValueError("asset category is required")
        if purchase_cost < 0:
            raise ValueError("asset purchase cost cannot be negative")
        if useful_life_months <= 0:
            raise ValueError("useful life must be positive")
        if status not in {AVAILABLE, ASSIGNED, MAINTENANCE, RETIRED}:
            raise ValueError(f"unsupported asset status: {self.status}")

        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "asset_tag", asset_tag)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "purchase_cost", purchase_cost)
        object.__setattr__(self, "acquired_at", parse_iso(self.acquired_at).isoformat())
        object.__setattr__(self, "location", location)
        object.__setattr__(self, "assigned_to", assigned_to)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "useful_life_months", useful_life_months)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def assign(self, owner: object, location: object | None = None) -> "Asset":
        owner_text = clean_text(owner)
        if not owner_text:
            raise ValueError("asset assignment owner is required")
        return Asset(
            asset_id=self.asset_id,
            asset_tag=self.asset_tag,
            name=self.name,
            category=self.category,
            purchase_cost=self.purchase_cost,
            acquired_at=self.acquired_at,
            location=clean_text(location) if location is not None else self.location,
            assigned_to=owner_text,
            status=ASSIGNED,
            useful_life_months=self.useful_life_months,
            metadata=self.metadata,
        )

    def release(self, location: object | None = None) -> "Asset":
        return Asset(
            asset_id=self.asset_id,
            asset_tag=self.asset_tag,
            name=self.name,
            category=self.category,
            purchase_cost=self.purchase_cost,
            acquired_at=self.acquired_at,
            location=clean_text(location) if location is not None else self.location,
            assigned_to="",
            status=AVAILABLE,
            useful_life_months=self.useful_life_months,
            metadata=self.metadata,
        )

    def retire(self) -> "Asset":
        return Asset(
            asset_id=self.asset_id,
            asset_tag=self.asset_tag,
            name=self.name,
            category=self.category,
            purchase_cost=self.purchase_cost,
            acquired_at=self.acquired_at,
            location=self.location,
            assigned_to=self.assigned_to,
            status=RETIRED,
            useful_life_months=self.useful_life_months,
            metadata=self.metadata,
        )

    def mark_maintenance(self) -> "Asset":
        return Asset(
            asset_id=self.asset_id,
            asset_tag=self.asset_tag,
            name=self.name,
            category=self.category,
            purchase_cost=self.purchase_cost,
            acquired_at=self.acquired_at,
            location=self.location,
            assigned_to=self.assigned_to,
            status=MAINTENANCE,
            useful_life_months=self.useful_life_months,
            metadata=self.metadata,
        )

    def age_months(self, at: object | None = None) -> int:
        acquired = parse_iso(self.acquired_at)
        current = parse_iso(at or utc_now_iso())
        months = (current.year - acquired.year) * 12 + (current.month - acquired.month)
        if current.day < acquired.day:
            months -= 1
        return max(months, 0)

    def book_value(self, at: object | None = None) -> Decimal:
        age = self.age_months(at)
        depreciated = self.purchase_cost * Decimal(min(age, self.useful_life_months)) / Decimal(self.useful_life_months)
        return max(self.purchase_cost - depreciated, Decimal("0.00")).quantize(CENT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_tag": self.asset_tag,
            "name": self.name,
            "category": self.category,
            "purchase_cost": str(self.purchase_cost),
            "acquired_at": self.acquired_at,
            "location": self.location,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "useful_life_months": self.useful_life_months,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Asset":
        return cls(
            asset_id=payload["asset_id"],
            asset_tag=payload["asset_tag"],
            name=payload["name"],
            category=payload["category"],
            purchase_cost=payload["purchase_cost"],
            acquired_at=payload["acquired_at"],
            location=payload.get("location", ""),
            assigned_to=payload.get("assigned_to", ""),
            status=payload.get("status", AVAILABLE),
            useful_life_months=int(payload.get("useful_life_months", 36)),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class MaintenanceTicket:
    ticket_id: str
    asset_id: str
    issue: str
    priority: str = "normal"
    status: str = OPEN
    reported_by: str = "system"
    opened_at: str = field(default_factory=utc_now_iso)
    resolved_at: str | None = None
    cost: Decimal | str | int | float = Decimal("0.00")
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        ticket_id = clean_code(self.ticket_id)
        asset_id = clean_code(self.asset_id)
        issue = clean_text(self.issue)
        priority = clean_code(self.priority) or "normal"
        status = clean_code(self.status)
        reported_by = clean_text(self.reported_by)
        cost = money(self.cost)

        if not ticket_id:
            raise ValueError("maintenance ticket id is required")
        if not asset_id:
            raise ValueError("maintenance ticket asset id is required")
        if not issue:
            raise ValueError("maintenance issue is required")
        if status not in {OPEN, IN_PROGRESS, RESOLVED, CLOSED}:
            raise ValueError(f"unsupported maintenance status: {self.status}")
        if cost < 0:
            raise ValueError("maintenance cost cannot be negative")

        notes = tuple(clean_text(note) for note in self.notes if clean_text(note))

        object.__setattr__(self, "ticket_id", ticket_id)
        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "issue", issue)
        object.__setattr__(self, "priority", priority)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reported_by", reported_by)
        object.__setattr__(self, "opened_at", parse_iso(self.opened_at).isoformat())
        object.__setattr__(self, "resolved_at", parse_iso(self.resolved_at).isoformat() if self.resolved_at else None)
        object.__setattr__(self, "cost", cost)
        object.__setattr__(self, "notes", notes)

    def with_status(
        self,
        status: str,
        *,
        note: object = "",
        cost: object | None = None,
        resolved_at: object | None = None,
    ) -> "MaintenanceTicket":
        status_key = clean_code(status)
        notes = self.notes + ((clean_text(note),) if clean_text(note) else ())
        new_cost = self.cost if cost is None else money(cost)
        closed_time = self.resolved_at

        if status_key in {RESOLVED, CLOSED}:
            closed_time = parse_iso(resolved_at or utc_now_iso()).isoformat()

        return MaintenanceTicket(
            ticket_id=self.ticket_id,
            asset_id=self.asset_id,
            issue=self.issue,
            priority=self.priority,
            status=status_key,
            reported_by=self.reported_by,
            opened_at=self.opened_at,
            resolved_at=closed_time,
            cost=new_cost,
            notes=notes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "asset_id": self.asset_id,
            "issue": self.issue,
            "priority": self.priority,
            "status": self.status,
            "reported_by": self.reported_by,
            "opened_at": self.opened_at,
            "resolved_at": self.resolved_at,
            "cost": str(self.cost),
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MaintenanceTicket":
        return cls(
            ticket_id=payload["ticket_id"],
            asset_id=payload["asset_id"],
            issue=payload["issue"],
            priority=payload.get("priority", "normal"),
            status=payload.get("status", OPEN),
            reported_by=payload.get("reported_by", "system"),
            opened_at=payload.get("opened_at", utc_now_iso()),
            resolved_at=payload.get("resolved_at"),
            cost=payload.get("cost", "0.00"),
            notes=tuple(payload.get("notes") or ()),
        )


class AssetRegister:
    def __init__(
        self,
        assets: Iterable[Asset] | None = None,
        tickets: Iterable[MaintenanceTicket] | None = None,
    ) -> None:
        self._assets: dict[str, Asset] = {}
        self._tickets: dict[str, MaintenanceTicket] = {}

        for asset in assets or ():
            self.add_asset(asset)
        for ticket in tickets or ():
            self._insert_ticket(ticket)

    def add_asset(self, asset: Asset) -> Asset:
        if asset.asset_id in self._assets:
            raise ValueError(f"asset already exists: {asset.asset_id}")
        if any(existing.asset_tag == asset.asset_tag for existing in self._assets.values()):
            raise ValueError(f"asset tag already exists: {asset.asset_tag}")
        self._assets[asset.asset_id] = asset
        return asset

    def get_asset(self, asset_id: object) -> Asset:
        key = clean_code(asset_id)
        try:
            return self._assets[key]
        except KeyError as exc:
            raise KeyError(f"unknown asset: {key}") from exc

    def assign_asset(self, asset_id: object, owner: object, *, location: object | None = None) -> Asset:
        asset = self.get_asset(asset_id)
        if asset.status == RETIRED:
            raise ValueError(f"cannot assign retired asset: {asset.asset_id}")
        updated = asset.assign(owner, location)
        self._assets[updated.asset_id] = updated
        return updated

    def release_asset(self, asset_id: object, *, location: object | None = None) -> Asset:
        asset = self.get_asset(asset_id)
        updated = asset.release(location)
        self._assets[updated.asset_id] = updated
        return updated

    def retire_asset(self, asset_id: object) -> Asset:
        asset = self.get_asset(asset_id)
        updated = asset.retire()
        self._assets[updated.asset_id] = updated
        return updated

    def _insert_ticket(self, ticket: MaintenanceTicket) -> None:
        if ticket.ticket_id in self._tickets:
            raise ValueError(f"maintenance ticket already exists: {ticket.ticket_id}")
        if ticket.asset_id not in self._assets:
            raise KeyError(f"unknown asset for maintenance ticket: {ticket.asset_id}")
        self._tickets[ticket.ticket_id] = ticket

    def open_ticket(self, ticket: MaintenanceTicket) -> MaintenanceTicket:
        self._insert_ticket(ticket)
        asset = self.get_asset(ticket.asset_id).mark_maintenance()
        self._assets[asset.asset_id] = asset
        return ticket

    def update_ticket(
        self,
        ticket_id: object,
        status: str,
        *,
        note: object = "",
        cost: object | None = None,
        resolved_at: object | None = None,
    ) -> MaintenanceTicket:
        key = clean_code(ticket_id)
        try:
            ticket = self._tickets[key]
        except KeyError as exc:
            raise KeyError(f"unknown maintenance ticket: {key}") from exc

        updated = ticket.with_status(status, note=note, cost=cost, resolved_at=resolved_at)
        self._tickets[updated.ticket_id] = updated

        if updated.status in {RESOLVED, CLOSED}:
            asset = self.get_asset(updated.asset_id).release()
            self._assets[asset.asset_id] = asset
        elif updated.status == IN_PROGRESS:
            asset = self.get_asset(updated.asset_id).mark_maintenance()
            self._assets[asset.asset_id] = asset

        return updated

    def assets_by_status(self, status: object) -> list[Asset]:
        wanted = clean_code(status)
        return sorted(
            [asset for asset in self._assets.values() if asset.status == wanted],
            key=lambda item: item.asset_id,
        )

    def assets_by_category(self, category: object) -> list[Asset]:
        wanted = clean_code(category)
        return sorted(
            [asset for asset in self._assets.values() if asset.category == wanted],
            key=lambda item: item.asset_id,
        )

    def assigned_to(self, owner: object) -> list[Asset]:
        wanted = clean_text(owner)
        return sorted(
            [asset for asset in self._assets.values() if asset.assigned_to == wanted],
            key=lambda item: item.asset_id,
        )

    def open_tickets(self, *, priority: object | None = None) -> list[MaintenanceTicket]:
        wanted_priority = clean_code(priority) if priority is not None else None
        return sorted(
            [
                ticket
                for ticket in self._tickets.values()
                if ticket.status in {OPEN, IN_PROGRESS}
                and (wanted_priority is None or ticket.priority == wanted_priority)
            ],
            key=lambda item: (item.priority, item.opened_at, item.ticket_id),
        )

    def replacement_candidates(self, at: object | None = None, *, threshold_value: object = "0.00") -> list[Asset]:
        threshold = money(threshold_value)
        return sorted(
            [
                asset
                for asset in self._assets.values()
                if asset.status != RETIRED and asset.book_value(at) <= threshold
            ],
            key=lambda item: (item.category, item.asset_id),
        )

    def valuation_report(self, at: object | None = None) -> dict[str, Any]:
        by_category: dict[str, Decimal] = {}
        total_cost = Decimal("0.00")
        total_book_value = Decimal("0.00")

        for asset in self._assets.values():
            if asset.status == RETIRED:
                continue
            total_cost += asset.purchase_cost
            value = asset.book_value(at)
            total_book_value += value
            by_category[asset.category] = by_category.get(asset.category, Decimal("0.00")) + value

        return {
            "asset_count": sum(1 for asset in self._assets.values() if asset.status != RETIRED),
            "purchase_cost": str(total_cost.quantize(CENT)),
            "book_value": str(total_book_value.quantize(CENT)),
            "by_category": {key: str(value.quantize(CENT)) for key, value in sorted(by_category.items())},
        }

    def maintenance_cost_report(self) -> dict[str, Any]:
        by_asset: dict[str, Decimal] = {}
        by_category: dict[str, Decimal] = {}
        total = Decimal("0.00")

        for ticket in self._tickets.values():
            total += ticket.cost
            by_asset[ticket.asset_id] = by_asset.get(ticket.asset_id, Decimal("0.00")) + ticket.cost
            category = self.get_asset(ticket.asset_id).category
            by_category[category] = by_category.get(category, Decimal("0.00")) + ticket.cost

        return {
            "ticket_count": len(self._tickets),
            "total_cost": str(total.quantize(CENT)),
            "by_asset": {key: str(value.quantize(CENT)) for key, value in sorted(by_asset.items())},
            "by_category": {key: str(value.quantize(CENT)) for key, value in sorted(by_category.items())},
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "assets": [asset.to_dict() for asset in sorted(self._assets.values(), key=lambda item: item.asset_id)],
            "tickets": [
                ticket.to_dict()
                for ticket in sorted(self._tickets.values(), key=lambda item: item.ticket_id)
            ],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path) -> "AssetRegister":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        assets = [Asset.from_dict(row) for row in payload.get("assets", ())]
        tickets = [MaintenanceTicket.from_dict(row) for row in payload.get("tickets", ())]
        return cls(assets=assets, tickets=tickets)

    def __len__(self) -> int:
        return len(self._assets)
