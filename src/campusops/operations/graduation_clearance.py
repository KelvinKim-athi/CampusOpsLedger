from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class GraduationClearanceNote(OperationNote):
    pass


class GraduationClearanceRecord(OperationRecord):
    pass


class GraduationClearanceRegister(OperationRegister):
    domain = "graduation_clearance"
    record_type = "clearance"
    record_class = GraduationClearanceRecord
