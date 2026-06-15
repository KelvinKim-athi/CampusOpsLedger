from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class QualityAssuranceNote(OperationNote):
    pass


class QualityAssuranceRecord(OperationRecord):
    pass


class QualityAssuranceRegister(OperationRegister):
    domain = "quality_assurance"
    record_type = "audit"
    record_class = QualityAssuranceRecord
