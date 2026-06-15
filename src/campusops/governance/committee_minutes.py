from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "committee_minutes"
CASE_TYPE = "minute_case"


class CommitteeMinutesPolicy(GovernancePolicy):
    pass


class CommitteeMinutesMetric(GovernanceMetric):
    pass


class CommitteeMinutesCase(GovernanceCase):
    pass


class CommitteeMinutesRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = CommitteeMinutesPolicy
    case_class = CommitteeMinutesCase
    metric_class = CommitteeMinutesMetric


def build_default_policies() -> tuple[CommitteeMinutesPolicy, ...]:
    return (
        CommitteeMinutesPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        CommitteeMinutesPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> CommitteeMinutesCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return CommitteeMinutesCase(
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


def demo_register() -> CommitteeMinutesRegister:
    register = CommitteeMinutesRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
