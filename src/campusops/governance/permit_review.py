from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "permit_review"
CASE_TYPE = "permit_case"


class PermitReviewPolicy(GovernancePolicy):
    pass


class PermitReviewMetric(GovernanceMetric):
    pass


class PermitReviewCase(GovernanceCase):
    pass


class PermitReviewRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = PermitReviewPolicy
    case_class = PermitReviewCase
    metric_class = PermitReviewMetric


def build_default_policies() -> tuple[PermitReviewPolicy, ...]:
    return (
        PermitReviewPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        PermitReviewPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> PermitReviewCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return PermitReviewCase(
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


def demo_register() -> PermitReviewRegister:
    register = PermitReviewRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
