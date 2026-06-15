from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class StaffPayrollNote(OperationNote):
    pass


class StaffPayrollRecord(OperationRecord):
    pass


class StaffPayrollRegister(OperationRegister):
    domain = "staff_payroll"
    record_type = "pay_run"
    record_class = StaffPayrollRecord
