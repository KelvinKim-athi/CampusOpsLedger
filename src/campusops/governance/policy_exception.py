from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "policy_exception"
CASE_TYPE = "policy_exception"


class PolicyExceptionPolicy(GovernancePolicy):
    pass


class PolicyExceptionMetric(GovernanceMetric):
    pass


class PolicyExceptionCase(GovernanceCase):
    pass


class PolicyExceptionRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = PolicyExceptionPolicy
    case_class = PolicyExceptionCase
    metric_class = PolicyExceptionMetric


def build_default_policies() -> tuple[PolicyExceptionPolicy, ...]:
    return (
        PolicyExceptionPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        PolicyExceptionPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> PolicyExceptionCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return PolicyExceptionCase(
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


def demo_register() -> PolicyExceptionRegister:
    register = PolicyExceptionRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
