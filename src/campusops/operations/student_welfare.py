from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class StudentWelfareNote(OperationNote):
    pass


class StudentWelfareRecord(OperationRecord):
    pass


class StudentWelfareRegister(OperationRegister):
    domain = "student_welfare"
    record_type = "case"
    record_class = StudentWelfareRecord
