from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class ClinicVisitNote(OperationNote):
    pass


class ClinicVisitRecord(OperationRecord):
    pass


class ClinicVisitRegister(OperationRegister):
    domain = "clinic_visits"
    record_type = "case"
    record_class = ClinicVisitRecord
