from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class DocumentRegistryNote(OperationNote):
    pass


class DocumentRegistryRecord(OperationRecord):
    pass


class DocumentRegistryRegister(OperationRegister):
    domain = "document_registry"
    record_type = "document"
    record_class = DocumentRegistryRecord
