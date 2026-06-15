from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "syllabus_review"
CASE_TYPE = "syllabus_case"


class SyllabusReviewPolicy(GovernancePolicy):
    pass


class SyllabusReviewMetric(GovernanceMetric):
    pass


class SyllabusReviewCase(GovernanceCase):
    pass


class SyllabusReviewRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = SyllabusReviewPolicy
    case_class = SyllabusReviewCase
    metric_class = SyllabusReviewMetric


def build_default_policies() -> tuple[SyllabusReviewPolicy, ...]:
    return (
        SyllabusReviewPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        SyllabusReviewPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> SyllabusReviewCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return SyllabusReviewCase(
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


def demo_register() -> SyllabusReviewRegister:
    register = SyllabusReviewRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
