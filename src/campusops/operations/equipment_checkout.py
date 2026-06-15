from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class EquipmentCheckoutNote(OperationNote):
    pass


class EquipmentCheckoutRecord(OperationRecord):
    pass


class EquipmentCheckoutRegister(OperationRegister):
    domain = "equipment_checkout"
    record_type = "checkout"
    record_class = EquipmentCheckoutRecord
