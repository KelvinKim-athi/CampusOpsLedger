from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "external_reporting"
CASE_TYPE = "reporting_case"


class ExternalReportingPolicy(GovernancePolicy):
    pass


class ExternalReportingMetric(GovernanceMetric):
    pass


class ExternalReportingCase(GovernanceCase):
    pass


class ExternalReportingRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = ExternalReportingPolicy
    case_class = ExternalReportingCase
    metric_class = ExternalReportingMetric


def build_default_policies() -> tuple[ExternalReportingPolicy, ...]:
    return (
        ExternalReportingPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        ExternalReportingPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> ExternalReportingCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return ExternalReportingCase(
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


def demo_register() -> ExternalReportingRegister:
    register = ExternalReportingRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
