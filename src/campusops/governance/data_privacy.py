from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "data_privacy"
CASE_TYPE = "privacy_case"


class DataPrivacyPolicy(GovernancePolicy):
    pass


class DataPrivacyMetric(GovernanceMetric):
    pass


class DataPrivacyCase(GovernanceCase):
    pass


class DataPrivacyRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = DataPrivacyPolicy
    case_class = DataPrivacyCase
    metric_class = DataPrivacyMetric


def build_default_policies() -> tuple[DataPrivacyPolicy, ...]:
    return (
        DataPrivacyPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        DataPrivacyPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> DataPrivacyCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return DataPrivacyCase(
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


def demo_register() -> DataPrivacyRegister:
    register = DataPrivacyRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
