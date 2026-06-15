from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "incident_escalation"
CASE_TYPE = "escalation_case"


class IncidentEscalationPolicy(GovernancePolicy):
    pass


class IncidentEscalationMetric(GovernanceMetric):
    pass


class IncidentEscalationCase(GovernanceCase):
    pass


class IncidentEscalationRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = IncidentEscalationPolicy
    case_class = IncidentEscalationCase
    metric_class = IncidentEscalationMetric


def build_default_policies() -> tuple[IncidentEscalationPolicy, ...]:
    return (
        IncidentEscalationPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        IncidentEscalationPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> IncidentEscalationCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return IncidentEscalationCase(
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


def demo_register() -> IncidentEscalationRegister:
    register = IncidentEscalationRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
