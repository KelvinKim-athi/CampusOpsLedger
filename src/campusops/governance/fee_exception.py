from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "fee_exception"
CASE_TYPE = "fee_case"


class FeeExceptionPolicy(GovernancePolicy):
    pass


class FeeExceptionMetric(GovernanceMetric):
    pass


class FeeExceptionCase(GovernanceCase):
    pass


class FeeExceptionRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = FeeExceptionPolicy
    case_class = FeeExceptionCase
    metric_class = FeeExceptionMetric


def build_default_policies() -> tuple[FeeExceptionPolicy, ...]:
    return (
        FeeExceptionPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        FeeExceptionPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> FeeExceptionCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return FeeExceptionCase(
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


def demo_register() -> FeeExceptionRegister:
    register = FeeExceptionRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
