from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "accreditation_tracking"
CASE_TYPE = "accreditation_case"


class AccreditationTrackingPolicy(GovernancePolicy):
    pass


class AccreditationTrackingMetric(GovernanceMetric):
    pass


class AccreditationTrackingCase(GovernanceCase):
    pass


class AccreditationTrackingRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = AccreditationTrackingPolicy
    case_class = AccreditationTrackingCase
    metric_class = AccreditationTrackingMetric


def build_default_policies() -> tuple[AccreditationTrackingPolicy, ...]:
    return (
        AccreditationTrackingPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        AccreditationTrackingPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> AccreditationTrackingCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return AccreditationTrackingCase(
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


def demo_register() -> AccreditationTrackingRegister:
    register = AccreditationTrackingRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
