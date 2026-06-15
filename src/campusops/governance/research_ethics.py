from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "research_ethics"
CASE_TYPE = "ethics_case"


class ResearchEthicsPolicy(GovernancePolicy):
    pass


class ResearchEthicsMetric(GovernanceMetric):
    pass


class ResearchEthicsCase(GovernanceCase):
    pass


class ResearchEthicsRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = ResearchEthicsPolicy
    case_class = ResearchEthicsCase
    metric_class = ResearchEthicsMetric


def build_default_policies() -> tuple[ResearchEthicsPolicy, ...]:
    return (
        ResearchEthicsPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        ResearchEthicsPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> ResearchEthicsCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return ResearchEthicsCase(
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


def demo_register() -> ResearchEthicsRegister:
    register = ResearchEthicsRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
