from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class BudgetPlanningNote(OperationNote):
    pass


class BudgetPlanningRecord(OperationRecord):
    pass


class BudgetPlanningRegister(OperationRegister):
    domain = "budget_planning"
    record_type = "budget_line"
    record_class = BudgetPlanningRecord
