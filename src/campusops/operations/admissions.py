from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class AdmissionsNote(OperationNote):
    pass


class AdmissionsRecord(OperationRecord):
    pass


class AdmissionsRegister(OperationRegister):
    domain = "admissions"
    record_type = "application"
    record_class = AdmissionsRecord
