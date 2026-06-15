from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class DisciplinaryCaseNote(OperationNote):
    pass


class DisciplinaryCaseRecord(OperationRecord):
    pass


class DisciplinaryCaseRegister(OperationRegister):
    domain = "disciplinary_cases"
    record_type = "case"
    record_class = DisciplinaryCaseRecord
