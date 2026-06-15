from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "continuity_planning"
CASE_TYPE = "continuity_case"


class ContinuityPlanningPolicy(GovernancePolicy):
    pass


class ContinuityPlanningMetric(GovernanceMetric):
    pass


class ContinuityPlanningCase(GovernanceCase):
    pass


class ContinuityPlanningRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = ContinuityPlanningPolicy
    case_class = ContinuityPlanningCase
    metric_class = ContinuityPlanningMetric


def build_default_policies() -> tuple[ContinuityPlanningPolicy, ...]:
    return (
        ContinuityPlanningPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        ContinuityPlanningPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> ContinuityPlanningCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return ContinuityPlanningCase(
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


def demo_register() -> ContinuityPlanningRegister:
    register = ContinuityPlanningRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
