from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "asset_disposal"
CASE_TYPE = "disposal_case"


class AssetDisposalPolicy(GovernancePolicy):
    pass


class AssetDisposalMetric(GovernanceMetric):
    pass


class AssetDisposalCase(GovernanceCase):
    pass


class AssetDisposalRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = AssetDisposalPolicy
    case_class = AssetDisposalCase
    metric_class = AssetDisposalMetric


def build_default_policies() -> tuple[AssetDisposalPolicy, ...]:
    return (
        AssetDisposalPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        AssetDisposalPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> AssetDisposalCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return AssetDisposalCase(
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


def demo_register() -> AssetDisposalRegister:
    register = AssetDisposalRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
