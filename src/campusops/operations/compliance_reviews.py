from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class ComplianceReviewNote(OperationNote):
    pass


class ComplianceReviewRecord(OperationRecord):
    pass


class ComplianceReviewRegister(OperationRegister):
    domain = "compliance_reviews"
    record_type = "review"
    record_class = ComplianceReviewRecord
