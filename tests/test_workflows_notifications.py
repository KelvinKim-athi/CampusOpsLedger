import pytest

from campusops.notifications.outbox import (
    FAILED,
    QUEUED,
    SENT,
    NotificationMessage,
    NotificationOutbox,
    NotificationTemplate,
)
from campusops.workflows.approvals import (
    APPROVED,
    CANCELLED,
    PENDING,
    REJECTED,
    ApprovalBoard,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStep,
)


def make_request():
    return ApprovalRequest(
        request_id=" Fee-Waiver-001 ",
        workflow_name=" Fee Waiver ",
        entity_type=" Ledger Waiver ",
        entity_id="S001-2026-T1",
        submitted_by=" finance.office ",
        steps=(
            ApprovalStep("finance-review", "Finance Review", "finance officer"),
            ApprovalStep("dean-review", "Dean Review", "dean"),
        ),
        payload={"student_id": "S001", "amount": "2000"},
    )


def test_approval_request_normalizes_and_tracks_next_step():
    request = make_request()

    assert request.request_id == "fee_waiver_001"
    assert request.workflow_name == "fee_waiver"
    assert request.entity_type == "ledger_waiver"
    assert request.status == PENDING
    assert request.next_pending_step().step_id == "finance_review"


def test_approval_request_rejects_duplicate_steps():
    with pytest.raises(ValueError, match="duplicate steps"):
        ApprovalRequest(
            request_id="R1",
            workflow_name="Test",
            entity_type="student",
            entity_id="S001",
            submitted_by="office",
            steps=(
                ApprovalStep("same", "One", "registrar"),
                ApprovalStep("same", "Two", "dean"),
            ),
        )


def test_approval_board_moves_request_to_approved_after_required_steps():
    board = ApprovalBoard()
    board.submit(make_request(), actor="finance")

    first = board.decide(
        "fee waiver 001",
        ApprovalDecision("finance-review", "bob.finance", APPROVED, "Looks valid"),
        actor="bob.finance",
    )
    assert first.status == PENDING
    assert first.next_pending_step().step_id == "dean_review"

    final = board.decide(
        "fee waiver 001",
        ApprovalDecision("dean-review", "dean.office", APPROVED, "Approved"),
        actor="dean.office",
    )

    assert final.status == APPROVED
    assert board.status_counts() == {"pending": 0, "approved": 1, "rejected": 0, "cancelled": 0}
    assert board.audit.all_events()[-1].event_type == "workflow_approved"


def test_approval_board_rejects_and_blocks_later_decisions():
    board = ApprovalBoard([make_request()])

    rejected = board.decide(
        "fee-waiver-001",
        ApprovalDecision("finance-review", "bob.finance", REJECTED, "Missing documents"),
    )

    assert rejected.status == REJECTED
    with pytest.raises(ValueError, match="already final"):
        board.decide(
            "fee-waiver-001",
            ApprovalDecision("dean-review", "dean.office", APPROVED),
        )


def test_approval_board_pending_for_role_and_entity_lookup():
    board = ApprovalBoard()
    request = board.submit(make_request())
    board.submit(
        ApprovalRequest(
            request_id="room-change-001",
            workflow_name="Room Change",
            entity_type="room booking",
            entity_id="B1",
            submitted_by="timetable",
            steps=(ApprovalStep("estate-review", "Estate Review", "estate"),),
        )
    )

    assert [row.request_id for row in board.pending_for_role("finance officer")] == [request.request_id]
    assert [row.request_id for row in board.requests_for_entity("ledger waiver", "S001-2026-T1")] == [request.request_id]


def test_approval_board_cancel_and_json_roundtrip(tmp_path):
    board = ApprovalBoard()
    board.submit(make_request())
    board.cancel("fee-waiver-001", actor="finance")

    path = tmp_path / "approvals.json"
    board.save_json(path)
    loaded = ApprovalBoard.load_json(path)

    assert loaded.get("fee waiver 001").status == CANCELLED
    assert loaded.status_counts()["cancelled"] == 1


def test_notification_template_renders_with_safe_missing_values():
    template = NotificationTemplate(
        "Fee Reminder",
        "Balance for $student_id",
        "Hello $name, your balance is $balance. Ref: $missing",
    )

    subject, body = template.render({"student_id": "S001", "name": "Ann", "balance": "750.00"})

    assert template.template_id == "fee_reminder"
    assert subject == "Balance for S001"
    assert body == "Hello Ann, your balance is 750.00. Ref: $missing"


def test_notification_outbox_queues_from_template_and_audits():
    outbox = NotificationOutbox()
    outbox.add_template(NotificationTemplate("Fee Reminder", "Balance $student_id", "Pay $balance"), actor="admin")

    message = outbox.queue_from_template(
        message_id="MSG-1",
        template_id="fee reminder",
        recipient="ann@example.test",
        context={"student_id": "S001", "balance": "750.00"},
        actor="finance",
    )

    assert message.message_id == "msg_1"
    assert message.subject == "Balance S001"
    assert message.body == "Pay 750.00"
    assert outbox.status_counts() == {QUEUED: 1, SENT: 0, FAILED: 0}
    assert [event.event_type for event in outbox.audit.all_events()] == [
        "notification_template_created",
        "notification_queued",
    ]


def test_notification_outbox_due_messages_respect_send_after_and_status():
    outbox = NotificationOutbox()
    outbox.queue(
        NotificationMessage(
            "now",
            "a@example.test",
            "Now",
            "Body",
            send_after="2026-02-01T08:00:00Z",
        )
    )
    outbox.queue(
        NotificationMessage(
            "later",
            "b@example.test",
            "Later",
            "Body",
            send_after="2026-02-01T10:00:00Z",
        )
    )
    outbox.mark_sent("now")

    assert outbox.due_messages("2026-02-01T09:00:00Z") == []
    assert [message.message_id for message in outbox.due_messages("2026-02-01T11:00:00Z")] == ["later"]


def test_notification_outbox_failure_and_recipient_lookup():
    outbox = NotificationOutbox()
    outbox.queue(NotificationMessage("M1", "ann@example.test", "One", "Body"))
    outbox.queue(NotificationMessage("M2", "ann@example.test", "Two", "Body"))
    failed = outbox.mark_failed("M1", reason="SMTP rejected", actor="worker")

    assert failed.status == FAILED
    assert failed.metadata["failure_reason"] == "SMTP rejected"
    assert [message.message_id for message in outbox.messages_for_recipient("ann@example.test")] == ["m1", "m2"]


def test_notification_outbox_json_roundtrip(tmp_path):
    outbox = NotificationOutbox()
    outbox.add_template(NotificationTemplate("Fee Reminder", "Balance $student_id", "Pay $balance"))
    outbox.queue_from_template(
        message_id="MSG-1",
        template_id="fee reminder",
        recipient="ann@example.test",
        context={"student_id": "S001", "balance": "750.00"},
    )
    outbox.mark_sent("msg-1")

    path = tmp_path / "outbox.json"
    outbox.save_json(path)
    loaded = NotificationOutbox.load_json(path)

    assert len(loaded) == 1
    assert loaded.get_message("msg 1").status == SENT
    assert loaded.get_template("fee reminder").channel == "email"
