from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "scholarship_review"
CASE_TYPE = "scholarship_case"


class ScholarshipReviewPolicy(GovernancePolicy):
    pass


class ScholarshipReviewMetric(GovernanceMetric):
    pass


class ScholarshipReviewCase(GovernanceCase):
    pass


class ScholarshipReviewRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = ScholarshipReviewPolicy
    case_class = ScholarshipReviewCase
    metric_class = ScholarshipReviewMetric


def build_default_policies() -> tuple[ScholarshipReviewPolicy, ...]:
    return (
        ScholarshipReviewPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        ScholarshipReviewPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> ScholarshipReviewCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return ScholarshipReviewCase(
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


def demo_register() -> ScholarshipReviewRegister:
    register = ScholarshipReviewRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
