from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class ExamSchedulingNote(OperationNote):
    pass


class ExamSchedulingRecord(OperationRecord):
    pass


class ExamSchedulingRegister(OperationRegister):
    domain = "exam_scheduling"
    record_type = "exam_slot"
    record_class = ExamSchedulingRecord
