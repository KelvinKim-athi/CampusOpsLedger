from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class ProcurementNote(OperationNote):
    pass


class ProcurementRecord(OperationRecord):
    pass


class ProcurementRegister(OperationRegister):
    domain = "procurement"
    record_type = "purchase_order"
    record_class = ProcurementRecord
