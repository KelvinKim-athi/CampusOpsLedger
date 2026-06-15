
import importlib

import pytest


OPERATIONS = [('admissions', 'Admissions', 'application'), ('scholarships', 'Scholarship', 'award'), ('library_circulation', 'LibraryCirculation', 'loan'), ('procurement', 'Procurement', 'purchase_order'), ('hostel_allocation', 'HostelAllocation', 'bed_assignment'), ('clinic_visits', 'ClinicVisit', 'case'), ('transport_fleet', 'TransportFleet', 'trip'), ('exam_scheduling', 'ExamScheduling', 'exam_slot'), ('graduation_clearance', 'GraduationClearance', 'clearance'), ('alumni_relations', 'AlumniRelations', 'alumni_case'), ('staff_payroll', 'StaffPayroll', 'pay_run'), ('cafeteria_accounts', 'CafeteriaAccount', 'meal_account'), ('research_grants', 'ResearchGrant', 'grant'), ('compliance_reviews', 'ComplianceReview', 'review'), ('incident_response', 'IncidentResponse', 'incident'), ('visitor_management', 'VisitorManagement', 'visit'), ('parking_permits', 'ParkingPermit', 'permit'), ('internship_tracking', 'InternshipTracking', 'placement'), ('disciplinary_cases', 'DisciplinaryCase', 'case'), ('equipment_checkout', 'EquipmentCheckout', 'checkout'), ('vendor_contracts', 'VendorContract', 'contract'), ('budget_planning', 'BudgetPlanning', 'budget_line'), ('facility_inspections', 'FacilityInspection', 'inspection'), ('service_desk', 'ServiceDesk', 'ticket'), ('event_planning', 'EventPlanning', 'event'), ('document_registry', 'DocumentRegistry', 'document'), ('course_evaluation', 'CourseEvaluation', 'evaluation'), ('quality_assurance', 'QualityAssurance', 'audit'), ('student_welfare', 'StudentWelfare', 'case'), ('field_attachment', 'FieldAttachment', 'attachment')]

ENTERPRISE = [('admissions_review', 'AdmissionsReview', 'application'), ('finance_reconciliation', 'FinanceReconciliation', 'reconciliation'), ('attendance_intervention', 'AttendanceIntervention', 'intervention'), ('academic_probation', 'AcademicProbation', 'probation_case'), ('hostel_discipline', 'HostelDiscipline', 'discipline_case'), ('clinic_referral', 'ClinicReferral', 'referral'), ('library_fines', 'LibraryFines', 'fine_case'), ('exam_irregularity', 'ExamIrregularity', 'irregularity'), ('procurement_evaluation', 'ProcurementEvaluation', 'evaluation'), ('vendor_performance', 'VendorPerformance', 'performance_case'), ('fleet_safety', 'FleetSafety', 'safety_case'), ('facility_repair', 'FacilityRepair', 'repair_case'), ('document_retention', 'DocumentRetention', 'retention_case'), ('data_quality', 'DataQuality', 'quality_case'), ('security_exception', 'SecurityException', 'exception_case'), ('alumni_engagement', 'AlumniEngagement', 'engagement_case'), ('grant_compliance', 'GrantCompliance', 'compliance_case'), ('payroll_exception', 'PayrollException', 'payroll_case'), ('cafeteria_credit', 'CafeteriaCredit', 'credit_case'), ('internship_review', 'InternshipReview', 'placement_case'), ('graduation_audit', 'GraduationAudit', 'audit_case'), ('course_feedback', 'CourseFeedback', 'feedback_case'), ('parking_enforcement', 'ParkingEnforcement', 'permit_case'), ('visitor_screening', 'VisitorScreening', 'visit_case'), ('equipment_loss', 'EquipmentLoss', 'loss_case'), ('budget_variance', 'BudgetVariance', 'variance_case'), ('student_welfare_review', 'StudentWelfareReview', 'welfare_case'), ('appeals_board', 'AppealsBoard', 'appeal_case'), ('risk_register', 'RiskRegister', 'risk_case'), ('service_catalog', 'ServiceCatalog', 'service_case')]


@pytest.mark.parametrize("slug,prefix,record_type", OPERATIONS)
def test_operations_record_creation_and_normalization(slug, prefix, record_type):
    module = importlib.import_module(f"campusops.operations.{slug}")
    record_cls = getattr(module, f"{prefix}Record")

    record = record_cls(
        record_id=" Case-001 ",
        subject_id=" s001 ",
        title=f"{record_type} sample",
        owner=" Office.User ",
        department=" Student Services ",
        amount="1200.555",
        priority=" High ",
        tags=(" urgent ", "student-facing", "urgent"),
        due_at="2026-02-01T00:00:00Z",
    )

    assert record.record_id == "case_001"
    assert record.subject_id == "S001"
    assert record.owner == "office_user"
    assert record.amount == module.Decimal("1200.56")
    assert record.priority == "high"
    assert record.tags == ("student_facing", "urgent")


@pytest.mark.parametrize("slug,prefix,record_type", OPERATIONS)
def test_operations_register_status_owner_and_history(slug, prefix, record_type):
    module = importlib.import_module(f"campusops.operations.{slug}")
    record_cls = getattr(module, f"{prefix}Record")
    register_cls = getattr(module, f"{prefix}Register")

    register = register_cls()
    register.add(record_cls("R1", "S001", "Sample", "owner.one", "Operations", amount="100"))
    register.assign_owner("R1", "owner.two", actor="manager")
    updated = register.update_status("R1", "approved", actor="owner.two", message="Approved")

    assert updated.owner == "owner_two"
    assert updated.status == "approved"
    assert updated.history[-1].action == "status_approved"
    assert register.status_counts()["approved"] == 1


@pytest.mark.parametrize("slug,prefix,record_type", OPERATIONS)
def test_operations_register_filtering_and_priority_queue(slug, prefix, record_type):
    module = importlib.import_module(f"campusops.operations.{slug}")
    record_cls = getattr(module, f"{prefix}Record")
    register_cls = getattr(module, f"{prefix}Register")

    register = register_cls([
        record_cls("R1", "S001", "Urgent", "owner.one", "Ops", amount="100", priority="urgent", tags=("risk",)),
        record_cls("R2", "S002", "Low", "owner.two", "Ops", amount="50", priority="low", tags=("normal",)),
    ])

    assert [row.record_id for row in register.by_tag("risk")] == ["r1"]
    assert [row.record_id for row in register.by_owner("owner one")] == ["r1"]
    assert register.priority_queue()[0].record_id == "r1"
    assert register.amount_total() == module.Decimal("150.00")


@pytest.mark.parametrize("slug,prefix,record_type", OPERATIONS)
def test_operations_notes_metadata_and_integrity(slug, prefix, record_type):
    module = importlib.import_module(f"campusops.operations.{slug}")
    note_cls = getattr(module, f"{prefix}Note")
    record_cls = getattr(module, f"{prefix}Record")
    register_cls = getattr(module, f"{prefix}Register")

    register = register_cls([record_cls("R1", "S001", "Sample", "owner.one", "Ops")])
    register.add_note("R1", note_cls("N1", "owner.one", "First note"))
    register.update_metadata("R1", {"source": "front-desk", "stage": "review"})

    record = register.get("R1")
    assert record.notes[0].body == "First note"
    assert record.metadata["source"] == "front-desk"
    assert register.validate_integrity()["valid"] is True


@pytest.mark.parametrize("slug,prefix,record_type", OPERATIONS)
def test_operations_json_roundtrip_and_snapshot(slug, prefix, record_type, tmp_path):
    module = importlib.import_module(f"campusops.operations.{slug}")
    record_cls = getattr(module, f"{prefix}Record")
    register_cls = getattr(module, f"{prefix}Register")

    register = register_cls([record_cls("R1", "S001", "Sample", "owner.one", "Ops", amount="100")])
    path = tmp_path / f"{slug}.json"
    register.save_json(path)
    loaded = register_cls.load_json(path)

    assert loaded.get("R1").subject_id == "S001"
    assert loaded.snapshot()["domain"] == slug
    assert loaded.snapshot()["record_type"] == record_type


@pytest.mark.parametrize("slug,prefix,record_type", ENTERPRISE)
def test_enterprise_rule_matching_and_case_creation(slug, prefix, record_type):
    module = importlib.import_module(f"campusops.enterprise.{slug}")
    rule_cls = getattr(module, f"{prefix}Rule")
    case_cls = getattr(module, f"{prefix}Case")
    engine_cls = getattr(module, f"{prefix}Engine")

    rule = rule_cls("amount-rule", "High amount", "amount", "gte", "1000", score=20)
    case = case_cls(
        "C1",
        "S001",
        "Review case",
        "owner.one",
        "Operations",
        priority="urgent",
        value="1500",
        payload={"amount": "1500"},
    )
    engine = engine_cls(rules=[rule])
    stored = engine.add_case(case)

    assert stored.case_id == "c1"
    assert stored.matched_rules == ("amount_rule",)
    assert stored.risk_score() >= 45


@pytest.mark.parametrize("slug,prefix,record_type", ENTERPRISE)
def test_enterprise_status_owner_and_action_history(slug, prefix, record_type):
    module = importlib.import_module(f"campusops.enterprise.{slug}")
    case_cls = getattr(module, f"{prefix}Case")
    engine_cls = getattr(module, f"{prefix}Engine")

    engine = engine_cls()
    engine.add_case(case_cls("C1", "S001", "Review case", "owner.one", "Operations", value="50"))
    engine.assign_owner("C1", "manager.one", actor="owner.one")
    resolved = engine.update_status("C1", "resolved", actor="manager.one", message="Done")

    assert resolved.owner == "manager_one"
    assert resolved.status == "resolved"
    assert resolved.actions[-1].action_type == "status_resolved"
    assert engine.status_counts()["resolved"] == 1


@pytest.mark.parametrize("slug,prefix,record_type", ENTERPRISE)
def test_enterprise_filters_totals_and_unit_summary(slug, prefix, record_type):
    module = importlib.import_module(f"campusops.enterprise.{slug}")
    case_cls = getattr(module, f"{prefix}Case")
    engine_cls = getattr(module, f"{prefix}Engine")

    engine = engine_cls([
        case_cls("C1", "S001", "Case one", "owner.one", "Operations", value="100", priority="high"),
        case_cls("C2", "S002", "Case two", "owner.two", "Finance", value="200", priority="low"),
    ])

    assert [case.case_id for case in engine.cases_by_owner("owner.one")] == ["c1"]
    assert [case.case_id for case in engine.cases_by_unit("Finance")] == ["c2"]
    assert engine.total_value() == module.Decimal("300.00")
    assert engine.unit_summary()["Operations"]["value"] == "100.00"


@pytest.mark.parametrize("slug,prefix,record_type", ENTERPRISE)
def test_enterprise_due_and_high_risk_queues(slug, prefix, record_type):
    module = importlib.import_module(f"campusops.enterprise.{slug}")
    case_cls = getattr(module, f"{prefix}Case")
    engine_cls = getattr(module, f"{prefix}Engine")

    engine = engine_cls([
        case_cls(
            "C1",
            "S001",
            "Due case",
            "owner.one",
            "Operations",
            priority="urgent",
            due_at="2026-02-01T00:00:00Z",
            payload={"amount": "5000"},
        ),
        case_cls("C2", "S002", "Normal case", "owner.two", "Operations", priority="low"),
    ])

    assert [case.case_id for case in engine.due_cases("2026-02-02T00:00:00Z")] == ["c1"]
    assert engine.high_risk_cases(minimum_score=40)[0].case_id == "c1"


@pytest.mark.parametrize("slug,prefix,record_type", ENTERPRISE)
def test_enterprise_json_and_csv_exports(slug, prefix, record_type, tmp_path):
    import csv

    module = importlib.import_module(f"campusops.enterprise.{slug}")
    case_cls = getattr(module, f"{prefix}Case")
    engine_cls = getattr(module, f"{prefix}Engine")

    engine = engine_cls([case_cls("C1", "S001", "Export case", "owner.one", "Operations", value="75")])
    json_path = tmp_path / f"{slug}.json"
    csv_path = tmp_path / f"{slug}.csv"

    engine.save_json(json_path)
    engine.write_csv(csv_path)
    loaded = engine_cls.load_json(json_path)

    assert loaded.get_case("C1").summary == "Export case"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["case_id"] == "c1"
    assert rows[0]["value"] == "75.00"

