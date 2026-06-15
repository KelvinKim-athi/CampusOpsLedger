from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "alumni_verification"
CASE_TYPE = "verification_case"


class AlumniVerificationPolicy(GovernancePolicy):
    pass


class AlumniVerificationMetric(GovernanceMetric):
    pass


class AlumniVerificationCase(GovernanceCase):
    pass


class AlumniVerificationRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = AlumniVerificationPolicy
    case_class = AlumniVerificationCase
    metric_class = AlumniVerificationMetric


def build_default_policies() -> tuple[AlumniVerificationPolicy, ...]:
    return (
        AlumniVerificationPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        AlumniVerificationPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> AlumniVerificationCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return AlumniVerificationCase(
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


def demo_register() -> AlumniVerificationRegister:
    register = AlumniVerificationRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
