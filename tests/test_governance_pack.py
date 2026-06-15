
import importlib

import pytest


GOVERNANCE_DOMAINS = [('policy_exception', 'PolicyException', 'policy_exception'), ('accreditation_tracking', 'AccreditationTracking', 'accreditation_case'), ('syllabus_review', 'SyllabusReview', 'syllabus_case'), ('committee_minutes', 'CommitteeMinutes', 'minute_case'), ('research_ethics', 'ResearchEthics', 'ethics_case'), ('student_appeals', 'StudentAppeals', 'appeal_case'), ('access_review', 'AccessReview', 'access_case'), ('data_privacy', 'DataPrivacy', 'privacy_case'), ('asset_disposal', 'AssetDisposal', 'disposal_case'), ('procurement_audit', 'ProcurementAudit', 'audit_case'), ('bursary_review', 'BursaryReview', 'bursary_case'), ('hostel_safety', 'HostelSafety', 'safety_case'), ('lab_compliance', 'LabCompliance', 'lab_case'), ('vehicle_logbook', 'VehicleLogbook', 'logbook_case'), ('energy_monitoring', 'EnergyMonitoring', 'energy_case'), ('waste_management', 'WasteManagement', 'waste_case'), ('cafeteria_hygiene', 'CafeteriaHygiene', 'hygiene_case'), ('library_archives', 'LibraryArchives', 'archive_case'), ('exam_moderation', 'ExamModeration', 'moderation_case'), ('course_change', 'CourseChange', 'change_case'), ('timetable_conflict', 'TimetableConflict', 'conflict_case'), ('staff_onboarding', 'StaffOnboarding', 'onboarding_case'), ('contract_review', 'ContractReview', 'contract_case'), ('supplier_risk', 'SupplierRisk', 'supplier_case'), ('incident_escalation', 'IncidentEscalation', 'escalation_case'), ('continuity_planning', 'ContinuityPlanning', 'continuity_case'), ('insurance_claims', 'InsuranceClaims', 'claim_case'), ('health_safety', 'HealthSafety', 'safety_case'), ('records_audit', 'RecordsAudit', 'records_case'), ('external_reporting', 'ExternalReporting', 'reporting_case'), ('internship_audit', 'InternshipAudit', 'internship_case'), ('graduation_exception', 'GraduationException', 'graduation_case'), ('alumni_verification', 'AlumniVerification', 'verification_case'), ('scholarship_review', 'ScholarshipReview', 'scholarship_case'), ('fee_exception', 'FeeException', 'fee_case'), ('identity_verification', 'IdentityVerification', 'identity_case'), ('permit_review', 'PermitReview', 'permit_case'), ('visitor_audit', 'VisitorAudit', 'visitor_case'), ('service_sla', 'ServiceSla', 'sla_case'), ('quality_improvement', 'QualityImprovement', 'improvement_case')]


@pytest.mark.parametrize("slug,prefix,case_type", GOVERNANCE_DOMAINS)
def test_governance_case_normalization(slug, prefix, case_type):
    module = importlib.import_module(f"campusops.governance.{slug}")
    case_cls = getattr(module, f"{prefix}Case")

    case = case_cls(
        " Case-001 ",
        " s001 ",
        f"{case_type} sample",
        " Office.User ",
        " Governance ",
        severity=" High ",
        amount="1200.555",
        data={"amount": "1200.555", "source": "manual"},
        tags=("Risk", "risk", "student-facing"),
    )

    assert case.case_id == "case_001"
    assert case.subject_id == "S001"
    assert case.owner == "office_user"
    assert case.severity == "high"
    assert case.amount == module.Decimal("1200.56")
    assert case.tags == ("risk", "student_facing")


@pytest.mark.parametrize("slug,prefix,case_type", GOVERNANCE_DOMAINS)
def test_governance_policy_matching_and_register_snapshot(slug, prefix, case_type):
    module = importlib.import_module(f"campusops.governance.{slug}")
    policy_cls = getattr(module, f"{prefix}Policy")
    case_cls = getattr(module, f"{prefix}Case")
    register_cls = getattr(module, f"{prefix}Register")

    policy = policy_cls("amount-rule", "High amount", "amount", "gte", "1000", impact=25)
    register = register_cls(policies=[policy])
    stored = register.add_case(
        case_cls(
            "C1",
            "S001",
            "Review case",
            "owner.one",
            "Governance",
            severity="urgent",
            amount="1500",
            data={"amount": "1500"},
        )
    )

    assert stored.matched_policies == ("amount_rule",)
    assert register.cases_by_policy("amount rule")[0].case_id == "c1"
    assert register.snapshot()["domain"] == slug
    assert register.snapshot()["case_type"] == case_type


@pytest.mark.parametrize("slug,prefix,case_type", GOVERNANCE_DOMAINS)
def test_governance_status_owner_and_actions(slug, prefix, case_type):
    module = importlib.import_module(f"campusops.governance.{slug}")
    case_cls = getattr(module, f"{prefix}Case")
    register_cls = getattr(module, f"{prefix}Register")

    register = register_cls([case_cls("C1", "S001", "Review case", "owner.one", "Governance", amount="50")])
    register.assign_owner("C1", "manager.one", actor="owner.one")
    resolved = register.update_status("C1", "resolved", actor="manager.one", message="Done")

    assert resolved.owner == "manager_one"
    assert resolved.status == "resolved"
    assert resolved.actions[-1].action_type == "status_resolved"
    assert register.status_counts()["resolved"] == 1


@pytest.mark.parametrize("slug,prefix,case_type", GOVERNANCE_DOMAINS)
def test_governance_due_high_score_and_metric_summary(slug, prefix, case_type):
    module = importlib.import_module(f"campusops.governance.{slug}")
    case_cls = getattr(module, f"{prefix}Case")
    metric_cls = getattr(module, f"{prefix}Metric")
    register_cls = getattr(module, f"{prefix}Register")

    register = register_cls([
        case_cls(
            "C1",
            "S001",
            "Due case",
            "owner.one",
            "Governance",
            severity="urgent",
            amount="500",
            due_at="2026-02-01T00:00:00Z",
        )
    ])
    register.add_metric("C1", metric_cls("M1", "risk-score", "75"))

    assert register.due_cases("2026-02-02T00:00:00Z")[0].case_id == "c1"
    assert register.high_score_cases(minimum=40, at="2026-02-02T00:00:00Z")[0].case_id == "c1"
    assert register.metric_summary()["risk_score"]["average"] == "75.00"


@pytest.mark.parametrize("slug,prefix,case_type", GOVERNANCE_DOMAINS)
def test_governance_json_roundtrip_and_exports(slug, prefix, case_type, tmp_path):
    module = importlib.import_module(f"campusops.governance.{slug}")
    register_cls = getattr(module, f"{prefix}Register")

    register = module.demo_register()
    path = tmp_path / f"{slug}.json"
    register.save_json(path)

    loaded = register_cls.load_json(path)
    rows = loaded.export_rows()

    assert len(loaded) == 1
    assert loaded.snapshot()["policy_count"] == 2
    assert rows[0]["case_id"] == "demo_1"
    assert rows[0]["matched_policies"] == "amount_threshold|source_required"
