from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "visitor_audit"
CASE_TYPE = "visitor_case"


class VisitorAuditPolicy(GovernancePolicy):
    pass


class VisitorAuditMetric(GovernanceMetric):
    pass


class VisitorAuditCase(GovernanceCase):
    pass


class VisitorAuditRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = VisitorAuditPolicy
    case_class = VisitorAuditCase
    metric_class = VisitorAuditMetric


def build_default_policies() -> tuple[VisitorAuditPolicy, ...]:
    return (
        VisitorAuditPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        VisitorAuditPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> VisitorAuditCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return VisitorAuditCase(
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


def demo_register() -> VisitorAuditRegister:
    register = VisitorAuditRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
