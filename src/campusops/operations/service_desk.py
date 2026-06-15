from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class ServiceDeskNote(OperationNote):
    pass


class ServiceDeskRecord(OperationRecord):
    pass


class ServiceDeskRegister(OperationRegister):
    domain = "service_desk"
    record_type = "ticket"
    record_class = ServiceDeskRecord
