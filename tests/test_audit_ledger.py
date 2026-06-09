from campusops.audit.events import AuditEvent, clean_event_type
from campusops.audit.ledger import AuditLedger


def test_event_type_cleaning_collapses_old_separators():
    assert clean_event_type(" Student.Created ") == "student_created"
    assert clean_event_type("student-created") == "student_created"
    assert clean_event_type("student.created") == "student_created"
    assert clean_event_type("student   created") == "student_created"


def test_audit_event_copies_nested_metadata():
    metadata = {"changes": {"cohort": "BIT-2026"}}
    event = AuditEvent(
        event_type="student.created",
        actor=" registrar ",
        entity_type=" student ",
        entity_id=" S001 ",
        message=" Registered student ",
        metadata=metadata,
    )

    metadata["changes"]["cohort"] = "MUTATED"

    assert event.actor == "registrar"
    assert event.entity_type == "student"
    assert event.entity_id == "S001"
    assert event.metadata["changes"]["cohort"] == "BIT-2026"


def test_ledger_records_and_filters_events():
    ledger = AuditLedger()
    ledger.record(
        event_type="student.created",
        actor="registrar",
        entity_type="student",
        entity_id="S001",
        message="Registered student",
        metadata={"cohort": "BIT"},
    )
    ledger.record(
        event_type="student.suspended",
        actor="dean",
        entity_type="student",
        entity_id="S001",
        message="Suspended student",
        metadata={"reason": "fees"},
    )

    matches = ledger.find(entity_type="student", entity_id="S001", event_type="student-suspended")

    assert len(matches) == 1
    assert matches[0].actor == "dean"
    assert matches[0].metadata == {"reason": "fees"}


def test_ledger_json_roundtrip_keeps_digest(tmp_path):
    ledger = AuditLedger()
    ledger.record(
        event_type="student.created",
        actor="registrar",
        entity_type="student",
        entity_id="S001",
        message="Registered student",
        metadata={"cohort": "BIT"},
    )

    path = tmp_path / "audit.json"
    ledger.to_json(path)
    loaded = AuditLedger.from_json(path)

    assert len(loaded) == 1
    assert loaded.digest() == ledger.digest()
    assert loaded.all_events()[0].to_dict() == ledger.all_events()[0].to_dict()