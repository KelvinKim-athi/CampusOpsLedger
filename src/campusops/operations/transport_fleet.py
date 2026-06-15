from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class TransportFleetNote(OperationNote):
    pass


class TransportFleetRecord(OperationRecord):
    pass


class TransportFleetRegister(OperationRegister):
    domain = "transport_fleet"
    record_type = "trip"
    record_class = TransportFleetRecord
