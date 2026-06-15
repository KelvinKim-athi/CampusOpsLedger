from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class FieldAttachmentNote(OperationNote):
    pass


class FieldAttachmentRecord(OperationRecord):
    pass


class FieldAttachmentRegister(OperationRegister):
    domain = "field_attachment"
    record_type = "attachment"
    record_class = FieldAttachmentRecord
