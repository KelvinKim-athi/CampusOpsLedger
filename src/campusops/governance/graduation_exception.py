from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "graduation_exception"
CASE_TYPE = "graduation_case"


class GraduationExceptionPolicy(GovernancePolicy):
    pass


class GraduationExceptionMetric(GovernanceMetric):
    pass


class GraduationExceptionCase(GovernanceCase):
    pass


class GraduationExceptionRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = GraduationExceptionPolicy
    case_class = GraduationExceptionCase
    metric_class = GraduationExceptionMetric


def build_default_policies() -> tuple[GraduationExceptionPolicy, ...]:
    return (
        GraduationExceptionPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        GraduationExceptionPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> GraduationExceptionCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return GraduationExceptionCase(
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


def demo_register() -> GraduationExceptionRegister:
    register = GraduationExceptionRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
