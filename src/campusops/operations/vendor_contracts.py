from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class VendorContractNote(OperationNote):
    pass


class VendorContractRecord(OperationRecord):
    pass


class VendorContractRegister(OperationRegister):
    domain = "vendor_contracts"
    record_type = "contract"
    record_class = VendorContractRecord
