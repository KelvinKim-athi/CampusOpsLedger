from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "procurement_audit"
CASE_TYPE = "audit_case"


class ProcurementAuditPolicy(GovernancePolicy):
    pass


class ProcurementAuditMetric(GovernanceMetric):
    pass


class ProcurementAuditCase(GovernanceCase):
    pass


class ProcurementAuditRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = ProcurementAuditPolicy
    case_class = ProcurementAuditCase
    metric_class = ProcurementAuditMetric


def build_default_policies() -> tuple[ProcurementAuditPolicy, ...]:
    return (
        ProcurementAuditPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        ProcurementAuditPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> ProcurementAuditCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return ProcurementAuditCase(
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


def demo_register() -> ProcurementAuditRegister:
    register = ProcurementAuditRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
