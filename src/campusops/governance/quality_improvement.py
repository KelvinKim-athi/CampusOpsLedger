from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "quality_improvement"
CASE_TYPE = "improvement_case"


class QualityImprovementPolicy(GovernancePolicy):
    pass


class QualityImprovementMetric(GovernanceMetric):
    pass


class QualityImprovementCase(GovernanceCase):
    pass


class QualityImprovementRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = QualityImprovementPolicy
    case_class = QualityImprovementCase
    metric_class = QualityImprovementMetric


def build_default_policies() -> tuple[QualityImprovementPolicy, ...]:
    return (
        QualityImprovementPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        QualityImprovementPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> QualityImprovementCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return QualityImprovementCase(
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


def demo_register() -> QualityImprovementRegister:
    register = QualityImprovementRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
