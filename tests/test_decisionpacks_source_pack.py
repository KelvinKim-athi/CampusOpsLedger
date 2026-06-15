import csv
import importlib

import pytest


DOMAINS = [('student_eligibility_review', 'StudentEligibilityReview'), ('student_exception_review', 'StudentExceptionReview'), ('student_case_triage', 'StudentCaseTriage'), ('student_approval_routing', 'StudentApprovalRouting'), ('student_deadline_monitoring', 'StudentDeadlineMonitoring'), ('student_evidence_audit', 'StudentEvidenceAudit'), ('student_compliance_scoring', 'StudentComplianceScoring'), ('student_sla_watch', 'StudentSlaWatch'), ('student_clearance_control', 'StudentClearanceControl'), ('student_document_hold', 'StudentDocumentHold'), ('finance_eligibility_review', 'FinanceEligibilityReview'), ('finance_exception_review', 'FinanceExceptionReview'), ('finance_case_triage', 'FinanceCaseTriage'), ('finance_approval_routing', 'FinanceApprovalRouting'), ('finance_deadline_monitoring', 'FinanceDeadlineMonitoring'), ('finance_evidence_audit', 'FinanceEvidenceAudit'), ('finance_compliance_scoring', 'FinanceComplianceScoring'), ('finance_sla_watch', 'FinanceSlaWatch'), ('finance_clearance_control', 'FinanceClearanceControl'), ('finance_document_hold', 'FinanceDocumentHold')]


@pytest.mark.parametrize("slug,prefix", DOMAINS)
def test_decisionpack_demo_register_snapshot_and_roundtrip(slug, prefix, tmp_path):
    module = importlib.import_module(f"campusops.decisionpacks.{slug}")
    register_cls = getattr(module, f"{prefix}Register")
    evidence_cls = getattr(module, f"{prefix}Evidence")

    register = module.demo_register()
    register.add_evidence("DEMO-1", evidence_cls("EV-1", "operator.one", "Uploaded review evidence"))
    register.assign_owner("DEMO-1", "manager.one", actor="operator.one")
    register.update_status("DEMO-1", "approved", actor="manager.one", message="Approved")

    snapshot = register.snapshot()
    assert snapshot["domain"] == slug
    assert snapshot["record_count"] == 1
    assert snapshot["status_counts"]["approved"] == 1

    json_path = tmp_path / f"{slug}.json"
    csv_path = tmp_path / f"{slug}.csv"

    register.save_json(json_path)
    register.write_csv(csv_path)

    loaded = register_cls.load_json(json_path)
    assert loaded.get("demo-1").owner == "manager_one"
    assert loaded.get("demo-1").evidence[0].description == "Uploaded review evidence"

    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["record_id"] == "demo_1"
    assert rows[0]["matched_rules"] == "amount_threshold|priority_marker|source_required"

