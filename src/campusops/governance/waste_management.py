from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "waste_management"
CASE_TYPE = "waste_case"


class WasteManagementPolicy(GovernancePolicy):
    pass


class WasteManagementMetric(GovernanceMetric):
    pass


class WasteManagementCase(GovernanceCase):
    pass


class WasteManagementRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = WasteManagementPolicy
    case_class = WasteManagementCase
    metric_class = WasteManagementMetric


def build_default_policies() -> tuple[WasteManagementPolicy, ...]:
    return (
        WasteManagementPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        WasteManagementPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> WasteManagementCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return WasteManagementCase(
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


def demo_register() -> WasteManagementRegister:
    register = WasteManagementRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
