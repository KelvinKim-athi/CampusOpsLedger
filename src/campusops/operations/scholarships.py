from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class ScholarshipNote(OperationNote):
    pass


class ScholarshipRecord(OperationRecord):
    pass


class ScholarshipRegister(OperationRegister):
    domain = "scholarships"
    record_type = "award"
    record_class = ScholarshipRecord
