from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "supplier_risk"
CASE_TYPE = "supplier_case"


class SupplierRiskPolicy(GovernancePolicy):
    pass


class SupplierRiskMetric(GovernanceMetric):
    pass


class SupplierRiskCase(GovernanceCase):
    pass


class SupplierRiskRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = SupplierRiskPolicy
    case_class = SupplierRiskCase
    metric_class = SupplierRiskMetric


def build_default_policies() -> tuple[SupplierRiskPolicy, ...]:
    return (
        SupplierRiskPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        SupplierRiskPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> SupplierRiskCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return SupplierRiskCase(
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


def demo_register() -> SupplierRiskRegister:
    register = SupplierRiskRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
