from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "vehicle_logbook"
CASE_TYPE = "logbook_case"


class VehicleLogbookPolicy(GovernancePolicy):
    pass


class VehicleLogbookMetric(GovernanceMetric):
    pass


class VehicleLogbookCase(GovernanceCase):
    pass


class VehicleLogbookRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = VehicleLogbookPolicy
    case_class = VehicleLogbookCase
    metric_class = VehicleLogbookMetric


def build_default_policies() -> tuple[VehicleLogbookPolicy, ...]:
    return (
        VehicleLogbookPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        VehicleLogbookPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> VehicleLogbookCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return VehicleLogbookCase(
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


def demo_register() -> VehicleLogbookRegister:
    register = VehicleLogbookRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
