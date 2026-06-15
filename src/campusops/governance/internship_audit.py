from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "internship_audit"
CASE_TYPE = "internship_case"


class InternshipAuditPolicy(GovernancePolicy):
    pass


class InternshipAuditMetric(GovernanceMetric):
    pass


class InternshipAuditCase(GovernanceCase):
    pass


class InternshipAuditRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = InternshipAuditPolicy
    case_class = InternshipAuditCase
    metric_class = InternshipAuditMetric


def build_default_policies() -> tuple[InternshipAuditPolicy, ...]:
    return (
        InternshipAuditPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        InternshipAuditPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> InternshipAuditCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return InternshipAuditCase(
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


def demo_register() -> InternshipAuditRegister:
    register = InternshipAuditRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
