from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "exam_moderation"
CASE_TYPE = "moderation_case"


class ExamModerationPolicy(GovernancePolicy):
    pass


class ExamModerationMetric(GovernanceMetric):
    pass


class ExamModerationCase(GovernanceCase):
    pass


class ExamModerationRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = ExamModerationPolicy
    case_class = ExamModerationCase
    metric_class = ExamModerationMetric


def build_default_policies() -> tuple[ExamModerationPolicy, ...]:
    return (
        ExamModerationPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        ExamModerationPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> ExamModerationCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return ExamModerationCase(
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


def demo_register() -> ExamModerationRegister:
    register = ExamModerationRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
