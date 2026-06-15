from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "health_safety"
CASE_TYPE = "safety_case"


class HealthSafetyPolicy(GovernancePolicy):
    pass


class HealthSafetyMetric(GovernanceMetric):
    pass


class HealthSafetyCase(GovernanceCase):
    pass


class HealthSafetyRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = HealthSafetyPolicy
    case_class = HealthSafetyCase
    metric_class = HealthSafetyMetric


def build_default_policies() -> tuple[HealthSafetyPolicy, ...]:
    return (
        HealthSafetyPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        HealthSafetyPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> HealthSafetyCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return HealthSafetyCase(
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


def demo_register() -> HealthSafetyRegister:
    register = HealthSafetyRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
