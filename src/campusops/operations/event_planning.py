from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class EventPlanningNote(OperationNote):
    pass


class EventPlanningRecord(OperationRecord):
    pass


class EventPlanningRegister(OperationRegister):
    domain = "event_planning"
    record_type = "event"
    record_class = EventPlanningRecord
