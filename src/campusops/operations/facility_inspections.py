from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class FacilityInspectionNote(OperationNote):
    pass


class FacilityInspectionRecord(OperationRecord):
    pass


class FacilityInspectionRegister(OperationRegister):
    domain = "facility_inspections"
    record_type = "inspection"
    record_class = FacilityInspectionRecord
