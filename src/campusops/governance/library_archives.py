from __future__ import annotations

from .core import Decimal, GovernanceCase, GovernanceMetric, GovernancePolicy, GovernanceRegister


DOMAIN = "library_archives"
CASE_TYPE = "archive_case"


class LibraryArchivesPolicy(GovernancePolicy):
    pass


class LibraryArchivesMetric(GovernanceMetric):
    pass


class LibraryArchivesCase(GovernanceCase):
    pass


class LibraryArchivesRegister(GovernanceRegister):
    domain = DOMAIN
    case_type = CASE_TYPE
    policy_class = LibraryArchivesPolicy
    case_class = LibraryArchivesCase
    metric_class = LibraryArchivesMetric


def build_default_policies() -> tuple[LibraryArchivesPolicy, ...]:
    return (
        LibraryArchivesPolicy("amount-threshold", "Amount threshold", "amount", "gte", "1000", impact=25, tags=("risk",)),
        LibraryArchivesPolicy("source-required", "Source is required", "source", "exists", "", impact=10, tags=("data",)),
    )


def open_case(case_id: str, subject_id: str, title: str, owner: str, amount: object = "0.00", **data: object) -> LibraryArchivesCase:
    payload = dict(data)
    payload.setdefault("amount", str(amount))
    payload.setdefault("source", DOMAIN)
    return LibraryArchivesCase(
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


def demo_register() -> LibraryArchivesRegister:
    register = LibraryArchivesRegister(policies=build_default_policies())
    register.add_case(open_case("DEMO-1", "S001", f"Demo {CASE_TYPE}", "governance.office", "1250"))
    return register
