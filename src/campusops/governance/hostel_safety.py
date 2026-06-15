from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "hostel_safety"
CASE_TYPE = "safety_case"


class HostelSafetyPolicy(GovernancePolicy):
    pass


class HostelSafetyMetric(GovernanceMetric):
    pass


class HostelSafetyCase(GovernanceCase):
    pass


class HostelSafetyRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = HostelSafetyPolicy
    case_class = HostelSafetyCase
    metric_class = HostelSafetyMetric


def build_default_policies() -> tuple[HostelSafetyPolicy, ...]:
    return (
        HostelSafetyPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        HostelSafetyPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> HostelSafetyCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return HostelSafetyCase(
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


def demo_register() -> HostelSafetyRegister:
    register = HostelSafetyRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
