from __future__ import annotations

from .core import Decimal, OperationNote, OperationRecord, OperationRegister


class CourseEvaluationNote(OperationNote):
    pass


class CourseEvaluationRecord(OperationRecord):
    pass


class CourseEvaluationRegister(OperationRegister):
    domain = "course_evaluation"
    record_type = "evaluation"
    record_class = CourseEvaluationRecord
