from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class LibraryCirculationNote(OperationNote):
    pass


class LibraryCirculationRecord(OperationRecord):
    pass


class LibraryCirculationRegister(OperationRegister):
    domain = "library_circulation"
    record_type = "loan"
    record_class = LibraryCirculationRecord
