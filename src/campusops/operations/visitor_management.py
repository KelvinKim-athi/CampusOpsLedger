from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class VisitorManagementNote(OperationNote):
    pass


class VisitorManagementRecord(OperationRecord):
    pass


class VisitorManagementRegister(OperationRegister):
    domain = "visitor_management"
    record_type = "visit"
    record_class = VisitorManagementRecord
