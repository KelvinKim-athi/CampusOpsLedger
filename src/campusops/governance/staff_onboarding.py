from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "staff_onboarding"
CASE_TYPE = "onboarding_case"


class StaffOnboardingPolicy(GovernancePolicy):
    pass


class StaffOnboardingMetric(GovernanceMetric):
    pass


class StaffOnboardingCase(GovernanceCase):
    pass


class StaffOnboardingRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = StaffOnboardingPolicy
    case_class = StaffOnboardingCase
    metric_class = StaffOnboardingMetric


def build_default_policies() -> tuple[StaffOnboardingPolicy, ...]:
    return (
        StaffOnboardingPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        StaffOnboardingPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> StaffOnboardingCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return StaffOnboardingCase(
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


def demo_register() -> StaffOnboardingRegister:
    register = StaffOnboardingRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
