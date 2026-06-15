from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "cafeteria_hygiene"
CASE_TYPE = "hygiene_case"


class CafeteriaHygienePolicy(GovernancePolicy):
    pass


class CafeteriaHygieneMetric(GovernanceMetric):
    pass


class CafeteriaHygieneCase(GovernanceCase):
    pass


class CafeteriaHygieneRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = CafeteriaHygienePolicy
    case_class = CafeteriaHygieneCase
    metric_class = CafeteriaHygieneMetric


def build_default_policies() -> tuple[CafeteriaHygienePolicy, ...]:
    return (
        CafeteriaHygienePolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        CafeteriaHygienePolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> CafeteriaHygieneCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return CafeteriaHygieneCase(
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


def demo_register() -> CafeteriaHygieneRegister:
    register = CafeteriaHygieneRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
