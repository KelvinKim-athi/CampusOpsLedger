from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class ResearchGrantNote(OperationNote):
    pass


class ResearchGrantRecord(OperationRecord):
    pass


class ResearchGrantRegister(OperationRegister):
    domain = "research_grants"
    record_type = "grant"
    record_class = ResearchGrantRecord
