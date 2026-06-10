from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from campusops.audit.ledger import AuditLedger
from campusops.rooms.models import Room, RoomBooking, clean_code, parse_iso


class RoomDirectory:
    def __init__(
        self,
        rooms: Iterable[Room] | None = None,
        bookings: Iterable[RoomBooking] | None = None,
        *,
        audit: AuditLedger | None = None,
    ) -> None:
        self._rooms: dict[str, Room] = {}
        self._bookings: dict[str, RoomBooking] = {}
        self.audit = audit or AuditLedger()

        for room in rooms or ():
            self._rooms[room.room_code] = room
        for booking in bookings or ():
            self._insert_existing_booking(booking)

    def add_room(self, room: Room, *, actor: str = "system") -> Room:
        if room.room_code in self._rooms:
            raise ValueError(f"room already exists: {room.room_code}")

        self._rooms[room.room_code] = room
        self.audit.record(
            event_type="room.created",
            actor=actor,
            entity_type="room",
            entity_id=room.room_code,
            message=f"Created room {room.name}",
            metadata={
                "capacity": room.capacity,
                "kind": room.kind,
                "building": room.building,
                "equipment": list(room.equipment),
            },
        )
        return room

    def get_room(self, room_code: object) -> Room:
        key = clean_code(room_code).upper()
        try:
            return self._rooms[key]
        except KeyError as exc:
            raise KeyError(f"unknown room: {key}") from exc

    def _insert_existing_booking(self, booking: RoomBooking) -> None:
        if booking.booking_id in self._bookings:
            raise ValueError(f"booking already exists: {booking.booking_id}")
        if booking.room_code not in self._rooms:
            raise KeyError(f"unknown room: {booking.room_code}")
        self._bookings[booking.booking_id] = booking

    def conflicts_for(self, booking: RoomBooking) -> list[RoomBooking]:
        return sorted(
            [
                existing
                for existing in self._bookings.values()
                if existing.booking_id != booking.booking_id and existing.overlaps(booking)
            ],
            key=lambda item: (item.starts_at, item.booking_id),
        )

    def book(self, booking: RoomBooking, *, actor: str = "system", allow_conflict: bool = False) -> RoomBooking:
        if booking.booking_id in self._bookings:
            raise ValueError(f"booking already exists: {booking.booking_id}")

        room = self.get_room(booking.room_code)
        if not room.active:
            raise ValueError(f"room is inactive: {room.room_code}")
        if booking.expected_size > room.capacity:
            raise ValueError(f"booking exceeds room capacity: {booking.expected_size} > {room.capacity}")

        conflicts = self.conflicts_for(booking)
        if conflicts and not allow_conflict:
            conflict_ids = ", ".join(row.booking_id for row in conflicts)
            raise ValueError(f"room booking conflict: {conflict_ids}")

        self._bookings[booking.booking_id] = booking
        self.audit.record(
            event_type="room.booked",
            actor=actor,
            entity_type="room_booking",
            entity_id=booking.booking_id,
            message=f"Booked {booking.room_code} for {booking.title}",
            metadata={
                "room_code": booking.room_code,
                "starts_at": booking.starts_at,
                "ends_at": booking.ends_at,
                "expected_size": booking.expected_size,
                "course_code": booking.course_code,
            },
        )
        return booking

    def cancel_booking(self, booking_id: object, *, actor: str = "system", reason: str = "") -> RoomBooking:
        key = clean_code(booking_id)
        try:
            booking = self._bookings.pop(key)
        except KeyError as exc:
            raise KeyError(f"unknown booking: {key}") from exc

        self.audit.record(
            event_type="room.booking_cancelled",
            actor=actor,
            entity_type="room_booking",
            entity_id=booking.booking_id,
            message=f"Cancelled booking {booking.booking_id}",
            metadata={"room_code": booking.room_code, "reason": reason},
        )
        return booking

    def bookings_for_room(self, room_code: object) -> list[RoomBooking]:
        room = self.get_room(room_code)
        return sorted(
            [booking for booking in self._bookings.values() if booking.room_code == room.room_code],
            key=lambda booking: (booking.starts_at, booking.booking_id),
        )

    def bookings_between(self, starts_at: object, ends_at: object) -> list[RoomBooking]:
        start = parse_iso(starts_at)
        end = parse_iso(ends_at)
        return sorted(
            [
                booking
                for booking in self._bookings.values()
                if parse_iso(booking.starts_at) < end and start < parse_iso(booking.ends_at)
            ],
            key=lambda booking: (booking.starts_at, booking.room_code, booking.booking_id),
        )

    def available_rooms(
        self,
        *,
        starts_at: object,
        ends_at: object,
        size: int = 1,
        equipment: tuple[str, ...] = (),
        kind: str | None = None,
    ) -> list[Room]:
        probe_start = parse_iso(starts_at)
        probe_end = parse_iso(ends_at)
        if probe_end <= probe_start:
            raise ValueError("availability end must be after start")

        busy_rooms = {
            booking.room_code
            for booking in self._bookings.values()
            if parse_iso(booking.starts_at) < probe_end and probe_start < parse_iso(booking.ends_at)
        }

        return sorted(
            [
                room
                for room in self._rooms.values()
                if room.room_code not in busy_rooms and room.supports(size=size, equipment=equipment, kind=kind)
            ],
            key=lambda room: (room.capacity, room.room_code),
        )

    def recommend_room(
        self,
        *,
        starts_at: object,
        ends_at: object,
        size: int,
        equipment: tuple[str, ...] = (),
        kind: str | None = None,
    ) -> Room:
        matches = self.available_rooms(
            starts_at=starts_at,
            ends_at=ends_at,
            size=size,
            equipment=equipment,
            kind=kind,
        )
        if not matches:
            raise LookupError("no available room matches the request")
        return matches[0]

    def utilization(self) -> dict[str, int]:
        counts = {room_code: 0 for room_code in self._rooms}
        for booking in self._bookings.values():
            counts[booking.room_code] += 1
        return dict(sorted(counts.items()))

    def to_dict(self) -> dict[str, object]:
        return {
            "rooms": [room.to_dict() for room in sorted(self._rooms.values(), key=lambda item: item.room_code)],
            "bookings": [
                booking.to_dict()
                for booking in sorted(self._bookings.values(), key=lambda item: item.booking_id)
            ],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path, *, audit: AuditLedger | None = None) -> "RoomDirectory":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        rooms = [Room.from_dict(row) for row in payload.get("rooms", ())]
        bookings = [RoomBooking.from_dict(row) for row in payload.get("bookings", ())]
        return cls(rooms=rooms, bookings=bookings, audit=audit)

    def __len__(self) -> int:
        return len(self._rooms)