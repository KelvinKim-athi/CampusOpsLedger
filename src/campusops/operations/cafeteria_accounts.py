from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class CafeteriaAccountNote(OperationNote):
    pass


class CafeteriaAccountRecord(OperationRecord):
    pass


class CafeteriaAccountRegister(OperationRegister):
    domain = "cafeteria_accounts"
    record_type = "meal_account"
    record_class = CafeteriaAccountRecord
