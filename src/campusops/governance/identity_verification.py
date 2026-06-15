from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "identity_verification"
CASE_TYPE = "identity_case"


class IdentityVerificationPolicy(GovernancePolicy):
    pass


class IdentityVerificationMetric(GovernanceMetric):
    pass


class IdentityVerificationCase(GovernanceCase):
    pass


class IdentityVerificationRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = IdentityVerificationPolicy
    case_class = IdentityVerificationCase
    metric_class = IdentityVerificationMetric


def build_default_policies() -> tuple[IdentityVerificationPolicy, ...]:
    return (
        IdentityVerificationPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        IdentityVerificationPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> IdentityVerificationCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return IdentityVerificationCase(
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


def demo_register() -> IdentityVerificationRegister:
    register = IdentityVerificationRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
