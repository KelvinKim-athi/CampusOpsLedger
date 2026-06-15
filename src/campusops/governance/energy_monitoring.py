from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "energy_monitoring"
CASE_TYPE = "energy_case"


class EnergyMonitoringPolicy(GovernancePolicy):
    pass


class EnergyMonitoringMetric(GovernanceMetric):
    pass


class EnergyMonitoringCase(GovernanceCase):
    pass


class EnergyMonitoringRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = EnergyMonitoringPolicy
    case_class = EnergyMonitoringCase
    metric_class = EnergyMonitoringMetric


def build_default_policies() -> tuple[EnergyMonitoringPolicy, ...]:
    return (
        EnergyMonitoringPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        EnergyMonitoringPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> EnergyMonitoringCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return EnergyMonitoringCase(
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


def demo_register() -> EnergyMonitoringRegister:
    register = EnergyMonitoringRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
