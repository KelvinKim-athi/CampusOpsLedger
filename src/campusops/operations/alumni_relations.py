from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class AlumniRelationsNote(OperationNote):
    pass


class AlumniRelationsRecord(OperationRecord):
    pass


class AlumniRelationsRegister(OperationRegister):
    domain = "alumni_relations"
    record_type = "alumni_case"
    record_class = AlumniRelationsRecord
