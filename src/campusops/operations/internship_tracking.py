from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class InternshipTrackingNote(OperationNote):
    pass


class InternshipTrackingRecord(OperationRecord):
    pass


class InternshipTrackingRegister(OperationRegister):
    domain = "internship_tracking"
    record_type = "placement"
    record_class = InternshipTrackingRecord
