from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "service_sla"
CASE_TYPE = "sla_case"


class ServiceSlaPolicy(GovernancePolicy):
    pass


class ServiceSlaMetric(GovernanceMetric):
    pass


class ServiceSlaCase(GovernanceCase):
    pass


class ServiceSlaRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = ServiceSlaPolicy
    case_class = ServiceSlaCase
    metric_class = ServiceSlaMetric


def build_default_policies() -> tuple[ServiceSlaPolicy, ...]:
    return (
        ServiceSlaPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        ServiceSlaPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> ServiceSlaCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return ServiceSlaCase(
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


def demo_register() -> ServiceSlaRegister:
    register = ServiceSlaRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
