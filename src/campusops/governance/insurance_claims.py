from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "insurance_claims"
CASE_TYPE = "claim_case"


class InsuranceClaimsPolicy(GovernancePolicy):
    pass


class InsuranceClaimsMetric(GovernanceMetric):
    pass


class InsuranceClaimsCase(GovernanceCase):
    pass


class InsuranceClaimsRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = InsuranceClaimsPolicy
    case_class = InsuranceClaimsCase
    metric_class = InsuranceClaimsMetric


def build_default_policies() -> tuple[InsuranceClaimsPolicy, ...]:
    return (
        InsuranceClaimsPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        InsuranceClaimsPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> InsuranceClaimsCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return InsuranceClaimsCase(
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


def demo_register() -> InsuranceClaimsRegister:
    register = InsuranceClaimsRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
