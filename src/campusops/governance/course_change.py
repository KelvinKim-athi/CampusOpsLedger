from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "course_change"
CASE_TYPE = "change_case"


class CourseChangePolicy(GovernancePolicy):
    pass


class CourseChangeMetric(GovernanceMetric):
    pass


class CourseChangeCase(GovernanceCase):
    pass


class CourseChangeRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = CourseChangePolicy
    case_class = CourseChangeCase
    metric_class = CourseChangeMetric


def build_default_policies() -> tuple[CourseChangePolicy, ...]:
    return (
        CourseChangePolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        CourseChangePolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> CourseChangeCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return CourseChangeCase(
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


def demo_register() -> CourseChangeRegister:
    register = CourseChangeRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
