from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class HostelAllocationNote(OperationNote):
    pass


class HostelAllocationRecord(OperationRecord):
    pass


class HostelAllocationRegister(OperationRegister):
    domain = "hostel_allocation"
    record_type = "bed_assignment"
    record_class = HostelAllocationRecord
