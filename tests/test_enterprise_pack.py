import csv
import importlib
from decimal import Decimal

DOMAINS = [
    ("admissions_review", "AdmissionsReview", "application"),
    ("finance_reconciliation", "FinanceReconciliation", "reconciliation"),
    ("attendance_intervention", "AttendanceIntervention", "intervention"),
    ("academic_probation", "AcademicProbation", "probation_case"),
    ("hostel_discipline", "HostelDiscipline", "discipline_case"),
    ("clinic_referral", "ClinicReferral", "referral"),
    ("library_fines", "LibraryFines", "fine_case"),
    ("exam_irregularity", "ExamIrregularity", "irregularity"),
    ("procurement_evaluation", "ProcurementEvaluation", "evaluation"),
    ("vendor_performance", "VendorPerformance", "performance_case"),
    ("fleet_safety", "FleetSafety", "safety_case"),
    ("facility_repair", "FacilityRepair", "repair_case"),
    ("document_retention", "DocumentRetention", "retention_case"),
    ("data_quality", "DataQuality", "quality_case"),
    ("security_exception", "SecurityException", "exception_case"),
    ("alumni_engagement", "AlumniEngagement", "engagement_case"),
    ("grant_compliance", "GrantCompliance", "compliance_case"),
    ("payroll_exception", "PayrollException", "payroll_case"),
    ("cafeteria_credit", "CafeteriaCredit", "credit_case"),
    ("internship_review", "InternshipReview", "placement_case"),
    ("graduation_audit", "GraduationAudit", "audit_case"),
    ("course_feedback", "CourseFeedback", "feedback_case"),
    ("parking_enforcement", "ParkingEnforcement", "permit_case"),
    ("visitor_screening", "VisitorScreening", "visit_case"),
    ("equipment_loss", "EquipmentLoss", "loss_case"),
    ("budget_variance", "BudgetVariance", "variance_case"),
    ("student_welfare_review", "StudentWelfareReview", "welfare_case"),
    ("appeals_board", "AppealsBoard", "appeal_case"),
    ("risk_register", "RiskRegister", "risk_case"),
    ("service_catalog", "ServiceCatalog", "service_case"),
]


def test_enterprise_modules_create_rules_cases_snapshots_and_roundtrip(tmp_path):
    for slug, prefix, case_type in DOMAINS:
        module = importlib.import_module(f"campusops.enterprise.{slug}")
        rule_cls = getattr(module, f"{prefix}Rule")
        case_cls = getattr(module, f"{prefix}Case")
        engine_cls = getattr(module, f"{prefix}Engine")

        rule = rule_cls(
            rule_id="high-value",
            title="High value case",
            field="amount",
            operator="gte",
            expected="1000",
            score=25,
            tags=("risk",),
        )
        case = case_cls(
            case_id="CASE-001",
            subject_id="S001",
            summary=f"{case_type} sample",
            owner="office.user",
            unit="Operations",
            priority="urgent",
            value="1250.50",
            due_at="2026-02-01T00:00:00Z",
            payload={"amount": "1250.50", "source": "test"},
            tags=("student",),
        )

        engine = engine_cls(rules=[rule])
        stored = engine.add_case(case)

        assert stored.matched_rules == ("high_value",)
        assert stored.risk_score() >= 65
        assert engine.snapshot()["case_type"] == case_type
        assert engine.total_value() == Decimal("1250.50")

        engine.assign_owner("case-001", "manager.user", actor="office.user")
        engine.update_status("case-001", "resolved", actor="manager.user", message="closed")

        assert engine.get_case("case 001").status == "resolved"
        assert engine.status_counts()["resolved"] == 1

        json_path = tmp_path / f"{slug}.json"
        csv_path = tmp_path / f"{slug}.csv"
        engine.save_json(json_path)
        engine.write_csv(csv_path)

        loaded = engine_cls.load_json(json_path)
        assert loaded.get_case("case-001").owner == "manager_user"

        with csv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["case_id"] == "case_001"
        assert rows[0]["matched_rules"] == "high_value"
