from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "access_review"
CASE_TYPE = "access_case"


class AccessReviewPolicy(GovernancePolicy):
    pass


class AccessReviewMetric(GovernanceMetric):
    pass


class AccessReviewCase(GovernanceCase):
    pass


class AccessReviewRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = AccessReviewPolicy
    case_class = AccessReviewCase
    metric_class = AccessReviewMetric


def build_default_policies() -> tuple[AccessReviewPolicy, ...]:
    return (
        AccessReviewPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        AccessReviewPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> AccessReviewCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return AccessReviewCase(
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


def demo_register() -> AccessReviewRegister:
    register = AccessReviewRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
