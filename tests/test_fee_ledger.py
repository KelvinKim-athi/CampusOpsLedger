from decimal import Decimal

import pytest

from campusops.ledger.accounts import LedgerLine, money
from campusops.ledger.fees import FeeItem, FeeSchedule
from campusops.ledger.transactions import StudentLedger
from campusops.students.models import Student


def make_student():
    return Student(
        student_id=" S001 ",
        full_name="Ann Wanjiku",
        cohort="BIT-2026",
        programme="Information Technology",
        year=2,
    )


def make_schedule():
    return FeeSchedule(
        schedule_id=" regular.2026 ",
        title="Regular 2026 Fees",
        items=(
            FeeItem(
                item_code=" tuition ",
                description="Tuition Fee",
                amount="12000",
                account_code="tuition",
                years=(1, 2, 3),
                programmes=("Information Technology",),
            ),
            FeeItem(
                item_code=" lab-fee ",
                description="Computer Lab Fee",
                amount="3500.125",
                account_code="Lab Fee",
                years=(2,),
                programmes=("Information Technology",),
            ),
            FeeItem(
                item_code="fieldwork",
                description="Fieldwork Fee",
                amount="9000",
                account_code="fieldwork",
                years=(3,),
                programmes=("Information Technology",),
            ),
        ),
    )


def test_money_rounds_to_cents_with_half_up_policy():
    assert money("10") == Decimal("10.00")
    assert money("10.125") == Decimal("10.13")
    assert money(10.124) == Decimal("10.12")


def test_ledger_line_normalizes_core_fields_and_signs_amounts():
    charge = LedgerLine(" Line.01 ", " s001 ", " Tuition Fee ", " 2026 t1 ", "1000", "charge", " Tuition ")
    payment = LedgerLine(" Line.02 ", " s001 ", " Cash ", " 2026 t1 ", "250", "payment", " Receipt ")

    assert charge.line_id == "line_01"
    assert charge.student_id == "S001"
    assert charge.account_code == "tuition_fee"
    assert charge.term == "2026 T1"
    assert charge.signed_amount == Decimal("1000.00")
    assert payment.signed_amount == Decimal("-250.00")


def test_student_ledger_posts_charges_payments_and_audit_events():
    ledger = StudentLedger()

    ledger.charge_fee(
        student_id="s001",
        account_code="tuition",
        term="2026-T1",
        amount="12000",
        description="Tuition",
        actor="accounts",
        reference="INV-001",
    )
    ledger.record_payment(
        student_id="S001",
        term="2026-T1",
        amount="5000",
        description="Mpesa payment",
        actor="cashier",
        reference="PAY-001",
    )

    assert ledger.balance_for_student(" s001 ") == Decimal("7000.00")
    assert [event.event_type for event in ledger.audit.all_events()] == [
        "ledger_charge",
        "ledger_payment",
    ]


def test_ledger_rejects_duplicate_line_ids_and_duplicate_student_references():
    ledger = StudentLedger()
    line = LedgerLine("L1", "S001", "tuition", "2026-T1", "100", "charge", "Tuition", reference="INV-001")

    ledger.post(line)

    with pytest.raises(ValueError, match="line already exists"):
        ledger.post(line)

    with pytest.raises(ValueError, match="reference already posted"):
        ledger.charge_fee(
            student_id="S001",
            account_code="tuition",
            term="2026-T1",
            amount="100",
            description="Tuition again",
            reference="INV-001",
        )


def test_balance_by_term_and_summary_include_waivers():
    ledger = StudentLedger()

    ledger.charge_fee(student_id="S001", account_code="tuition", term="2026-T1", amount="12000", description="Tuition")
    ledger.record_payment(student_id="S001", term="2026-T1", amount="5000", description="Receipt")
    ledger.apply_waiver(student_id="S001", term="2026-T1", amount="2000", description="Scholarship waiver")
    ledger.charge_fee(student_id="S001", account_code="tuition", term="2026-T2", amount="8000", description="Tuition")

    assert ledger.balance_for_student("S001", term="2026-T1") == Decimal("5000.00")
    assert ledger.balance_for_student("S001") == Decimal("13000.00")
    assert ledger.term_summary("2026-T1") == {
        "charges": Decimal("12000.00"),
        "payments": Decimal("5000.00"),
        "waivers": Decimal("2000.00"),
        "balance": Decimal("5000.00"),
    }


def test_statement_is_sorted_by_posted_time_then_line_id():
    ledger = StudentLedger()
    ledger.post(LedgerLine("B", "S001", "tuition", "2026-T1", "100", "charge", "B", posted_at="2026-01-02T10:00:00+00:00"))
    ledger.post(LedgerLine("A", "S001", "tuition", "2026-T1", "100", "charge", "A", posted_at="2026-01-01T10:00:00+00:00"))
    ledger.post(LedgerLine("C", "S001", "tuition", "2026-T1", "100", "charge", "C", posted_at="2026-01-02T10:00:00+00:00"))

    assert [line.line_id for line in ledger.statement("S001")] == ["a", "b", "c"]


def test_fee_schedule_filters_by_student_year_and_programme():
    schedule = make_schedule()
    student = make_student()

    items = schedule.expected_items(student)

    assert [item.item_code for item in items] == ["tuition", "lab_fee"]
    assert schedule.total_for(student) == Decimal("15500.13")


def test_fee_schedule_rejects_duplicate_items_after_normalization():
    with pytest.raises(ValueError, match="duplicate item codes"):
        FeeSchedule(
            schedule_id="regular",
            title="Regular Fees",
            items=(
                FeeItem("lab-fee", "Lab", "100", "lab"),
                FeeItem("lab.fee", "Lab Duplicate", "100", "lab"),
            ),
        )


def test_billing_student_from_schedule_posts_only_applicable_items():
    ledger = StudentLedger()
    student = make_student()
    schedule = make_schedule()

    posted = ledger.bill_student_from_schedule(student=student, schedule=schedule, term="2026-T1", actor="accounts")

    assert [line.account_code for line in posted] == ["tuition", "lab_fee"]
    assert ledger.balance_for_student("S001") == Decimal("15500.13")
    assert ledger.audit.all_events()[0].metadata["reference"] == "schedule:regular_2026:2026-T1:tuition"


def test_student_ledger_json_roundtrip(tmp_path):
    ledger = StudentLedger()
    ledger.charge_fee(student_id="S001", account_code="tuition", term="2026-T1", amount="12000", description="Tuition")
    ledger.record_payment(student_id="S001", term="2026-T1", amount="5000", description="Payment")

    path = tmp_path / "ledger.json"
    ledger.save_json(path)
    loaded = StudentLedger.load_json(path)

    assert len(loaded) == 2
    assert loaded.balance_for_student("S001") == Decimal("7000.00")
    amounts = sorted(record["amount"] for record in loaded.to_records())
    assert amounts == ["12000.00", "5000.00"]
