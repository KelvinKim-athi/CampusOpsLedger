from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "records_audit"
CASE_TYPE = "records_case"


class RecordsAuditPolicy(GovernancePolicy):
    pass


class RecordsAuditMetric(GovernanceMetric):
    pass


class RecordsAuditCase(GovernanceCase):
    pass


class RecordsAuditRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = RecordsAuditPolicy
    case_class = RecordsAuditCase
    metric_class = RecordsAuditMetric


def build_default_policies() -> tuple[RecordsAuditPolicy, ...]:
    return (
        RecordsAuditPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        RecordsAuditPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> RecordsAuditCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return RecordsAuditCase(
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


def demo_register() -> RecordsAuditRegister:
    register = RecordsAuditRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
