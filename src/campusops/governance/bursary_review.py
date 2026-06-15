from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "bursary_review"
CASE_TYPE = "bursary_case"


class BursaryReviewPolicy(GovernancePolicy):
    pass


class BursaryReviewMetric(GovernanceMetric):
    pass


class BursaryReviewCase(GovernanceCase):
    pass


class BursaryReviewRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = BursaryReviewPolicy
    case_class = BursaryReviewCase
    metric_class = BursaryReviewMetric


def build_default_policies() -> tuple[BursaryReviewPolicy, ...]:
    return (
        BursaryReviewPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        BursaryReviewPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> BursaryReviewCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return BursaryReviewCase(
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


def demo_register() -> BursaryReviewRegister:
    register = BursaryReviewRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
