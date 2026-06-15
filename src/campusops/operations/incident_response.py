from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class IncidentResponseNote(OperationNote):
    pass


class IncidentResponseRecord(OperationRecord):
    pass


class IncidentResponseRegister(OperationRegister):
    domain = "incident_response"
    record_type = "incident"
    record_class = IncidentResponseRecord
