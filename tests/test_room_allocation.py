import pytest

from campusops.rooms.allocation import RoomDirectory
from campusops.rooms.models import LAB, LECTURE, Room, RoomBooking


def make_directory():
    return RoomDirectory(
        rooms=[
            Room(" LAB-2 ", "Computer Lab Two", 40, kind=LAB, building="Science Block", equipment=("Projector", "Computers")),
            Room("LH.1", "Lecture Hall One", 120, kind=LECTURE, building="Main Block", equipment=("Projector", "PA System")),
            Room("SR-1", "Seminar Room", 25, kind=LECTURE, building="Library", equipment=("Whiteboard",)),
        ]
    )


def test_room_normalizes_code_kind_equipment_and_support_checks():
    room = Room(
        room_code=" lab-2 ",
        name=" Computer   Lab Two ",
        capacity="40",
        kind=" Lab ",
        building=" Science Block ",
        equipment=(" Projector ", "projector", "PA System"),
    )

    assert room.room_code == "LAB_2"
    assert room.name == "Computer Lab Two"
    assert room.kind == LAB
    assert room.equipment == ("pa_system", "projector")
    assert room.supports(size=35, equipment=("projector",), kind="lab") is True
    assert room.supports(size=41, equipment=("projector",), kind="lab") is False


def test_booking_normalizes_dates_and_rejects_bad_time_range():
    booking = RoomBooking(
        booking_id=" ICT-101.Week-1 ",
        room_code=" lab-2 ",
        title=" ICT 101 Practical ",
        starts_at="2026-02-01T08:00:00+03:00",
        ends_at="2026-02-01T10:00:00+03:00",
        expected_size="35",
        owner="Dr Maina",
        course_code=" ict 101 ",
    )

    assert booking.booking_id == "ict_101_week_1"
    assert booking.room_code == "LAB_2"
    assert booking.course_code == "ICT_101"
    assert booking.starts_at == "2026-02-01T05:00:00+00:00"
    assert booking.ends_at == "2026-02-01T07:00:00+00:00"

    with pytest.raises(ValueError, match="end must be after start"):
        RoomBooking("bad", "LAB-2", "Bad", "2026-02-01T10:00:00+00:00", "2026-02-01T09:00:00+00:00", 10, "Office")


def test_directory_adds_room_and_audits_creation():
    directory = RoomDirectory()
    directory.add_room(Room("LAB-2", "Computer Lab Two", 40, kind=LAB), actor="estate")

    assert len(directory) == 1
    assert directory.get_room("lab 2").name == "Computer Lab Two"
    assert directory.audit.all_events()[0].event_type == "room_created"


def test_booking_rejects_unknown_room_and_capacity_overflow():
    directory = make_directory()

    with pytest.raises(KeyError, match="unknown room"):
        directory.book(RoomBooking("B1", "MISSING", "Ghost", "2026-02-01T08:00:00Z", "2026-02-01T09:00:00Z", 5, "Office"))

    with pytest.raises(ValueError, match="exceeds room capacity"):
        directory.book(RoomBooking("B2", "SR-1", "Large Class", "2026-02-01T08:00:00Z", "2026-02-01T09:00:00Z", 50, "Office"))


def test_booking_rejects_overlapping_same_room_but_allows_back_to_back():
    directory = make_directory()
    directory.book(RoomBooking("B1", "LAB-2", "Morning Lab", "2026-02-01T08:00:00Z", "2026-02-01T10:00:00Z", 30, "Dr Maina"))

    with pytest.raises(ValueError, match="room booking conflict"):
        directory.book(RoomBooking("B2", "LAB-2", "Overlap", "2026-02-01T09:30:00Z", "2026-02-01T11:00:00Z", 30, "Dr Maina"))

    directory.book(RoomBooking("B3", "LAB-2", "Back To Back", "2026-02-01T10:00:00Z", "2026-02-01T11:00:00Z", 30, "Dr Maina"))

    assert [booking.booking_id for booking in directory.bookings_for_room("lab-2")] == ["b1", "b3"]


def test_available_rooms_filters_busy_capacity_kind_and_equipment():
    directory = make_directory()
    directory.book(RoomBooking("B1", "LAB-2", "Morning Lab", "2026-02-01T08:00:00Z", "2026-02-01T10:00:00Z", 30, "Dr Maina"))

    available = directory.available_rooms(
        starts_at="2026-02-01T08:30:00Z",
        ends_at="2026-02-01T09:00:00Z",
        size=20,
        equipment=("projector",),
    )

    assert [room.room_code for room in available] == ["LH_1"]


def test_recommend_room_chooses_smallest_available_fit():
    directory = make_directory()

    room = directory.recommend_room(
        starts_at="2026-02-01T08:30:00Z",
        ends_at="2026-02-01T09:00:00Z",
        size=20,
        equipment=("whiteboard",),
    )

    assert room.room_code == "SR_1"

    with pytest.raises(LookupError, match="no available room"):
        directory.recommend_room(
            starts_at="2026-02-01T08:30:00Z",
            ends_at="2026-02-01T09:00:00Z",
            size=200,
        )


def test_bookings_between_and_cancel_booking_update_calendar():
    directory = make_directory()
    directory.book(RoomBooking("B1", "LAB-2", "Morning Lab", "2026-02-01T08:00:00Z", "2026-02-01T10:00:00Z", 30, "Dr Maina"))
    directory.book(RoomBooking("B2", "LH-1", "Lecture", "2026-02-01T09:00:00Z", "2026-02-01T11:00:00Z", 90, "Dr Achieng"))

    assert [booking.booking_id for booking in directory.bookings_between("2026-02-01T08:30:00Z", "2026-02-01T09:30:00Z")] == ["b1", "b2"]

    cancelled = directory.cancel_booking("B1", actor="timetable", reason="class moved")

    assert cancelled.booking_id == "b1"
    assert [booking.booking_id for booking in directory.bookings_between("2026-02-01T08:30:00Z", "2026-02-01T09:30:00Z")] == ["b2"]
    assert directory.audit.all_events()[-1].event_type == "room_booking_cancelled"


def test_utilization_counts_rooms_with_zero_bookings():
    directory = make_directory()
    directory.book(RoomBooking("B1", "LAB-2", "Morning Lab", "2026-02-01T08:00:00Z", "2026-02-01T10:00:00Z", 30, "Dr Maina"))

    assert directory.utilization() == {"LAB_2": 1, "LH_1": 0, "SR_1": 0}


def test_room_directory_json_roundtrip(tmp_path):
    directory = make_directory()
    directory.book(RoomBooking("B1", "LAB-2", "Morning Lab", "2026-02-01T08:00:00Z", "2026-02-01T10:00:00Z", 30, "Dr Maina"))

    path = tmp_path / "rooms.json"
    directory.save_json(path)
    loaded = RoomDirectory.load_json(path)

    assert len(loaded) == 3
    assert loaded.bookings_for_room("lab-2")[0].booking_id == "b1"
    assert loaded.recommend_room(
        starts_at="2026-02-01T08:30:00Z",
        ends_at="2026-02-01T09:00:00Z",
        size=20,
        equipment=("projector",),
    ).room_code == "LH_1"