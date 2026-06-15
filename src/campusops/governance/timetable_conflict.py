from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "timetable_conflict"
CASE_TYPE = "conflict_case"


class TimetableConflictPolicy(GovernancePolicy):
    pass


class TimetableConflictMetric(GovernanceMetric):
    pass


class TimetableConflictCase(GovernanceCase):
    pass


class TimetableConflictRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = TimetableConflictPolicy
    case_class = TimetableConflictCase
    metric_class = TimetableConflictMetric


def build_default_policies() -> tuple[TimetableConflictPolicy, ...]:
    return (
        TimetableConflictPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        TimetableConflictPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> TimetableConflictCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return TimetableConflictCase(
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


def demo_register() -> TimetableConflictRegister:
    register = TimetableConflictRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
