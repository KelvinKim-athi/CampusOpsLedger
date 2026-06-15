from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class ParkingPermitNote(OperationNote):
    pass


class ParkingPermitRecord(OperationRecord):
    pass


class ParkingPermitRegister(OperationRegister):
    domain = "parking_permits"
    record_type = "permit"
    record_class = ParkingPermitRecord
