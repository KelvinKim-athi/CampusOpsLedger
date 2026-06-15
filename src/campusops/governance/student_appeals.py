from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "student_appeals"
CASE_TYPE = "appeal_case"


class StudentAppealsPolicy(GovernancePolicy):
    pass


class StudentAppealsMetric(GovernanceMetric):
    pass


class StudentAppealsCase(GovernanceCase):
    pass


class StudentAppealsRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = StudentAppealsPolicy
    case_class = StudentAppealsCase
    metric_class = StudentAppealsMetric


def build_default_policies() -> tuple[StudentAppealsPolicy, ...]:
    return (
        StudentAppealsPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        StudentAppealsPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> StudentAppealsCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return StudentAppealsCase(
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


def demo_register() -> StudentAppealsRegister:
    register = StudentAppealsRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
