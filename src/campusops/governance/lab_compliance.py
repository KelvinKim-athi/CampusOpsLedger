from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "lab_compliance"
CASE_TYPE = "lab_case"


class LabCompliancePolicy(GovernancePolicy):
    pass


class LabComplianceMetric(GovernanceMetric):
    pass


class LabComplianceCase(GovernanceCase):
    pass


class LabComplianceRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = LabCompliancePolicy
    case_class = LabComplianceCase
    metric_class = LabComplianceMetric


def build_default_policies() -> tuple[LabCompliancePolicy, ...]:
    return (
        LabCompliancePolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        LabCompliancePolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> LabComplianceCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return LabComplianceCase(
        case_id=case_id,
        subject_id=subject_id,
        title=title,
        owner=owner,
        unit="Governance",
        severity="normal",
        amount=amount,
        data=payload,
        tags=(DOMAIN,),
    )


def demo_register() -> LabComplianceRegister:
    register = LabComplianceRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
