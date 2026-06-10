from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from campusops.audit.ledger import AuditLedger
from campusops.ledger.accounts import CHARGE, PAYMENT, WAIVER, LedgerLine, clean_code, clean_student_id, money
from campusops.ledger.fees import FeeSchedule


class StudentLedger:
    def __init__(
        self,
        lines: Iterable[LedgerLine] | None = None,
        *,
        audit: AuditLedger | None = None,
    ) -> None:
        self._lines: dict[str, LedgerLine] = {}
        self.audit = audit or AuditLedger()

        for line in lines or ():
            self._insert_existing(line)

    def _insert_existing(self, line: LedgerLine) -> None:
        if line.line_id in self._lines:
            raise ValueError(f"ledger line already exists: {line.line_id}")
        self._lines[line.line_id] = line

    def _reference_exists(self, student_id: str, reference: str) -> bool:
        if not reference:
            return False
        return any(line.student_id == student_id and line.reference == reference for line in self._lines.values())

    def post(self, line: LedgerLine, *, actor: str = "system") -> LedgerLine:
        if not isinstance(line, LedgerLine):
            raise TypeError("StudentLedger only accepts LedgerLine objects")
        if line.line_id in self._lines:
            raise ValueError(f"ledger line already exists: {line.line_id}")
        if self._reference_exists(line.student_id, line.reference):
            raise ValueError(f"ledger reference already posted for student: {line.reference}")

        self._lines[line.line_id] = line
        self.audit.record(
            event_type=f"ledger.{line.kind}",
            actor=actor,
            entity_type="ledger_line",
            entity_id=line.line_id,
            message=f"Posted {line.kind} for {line.student_id}",
            metadata={
                "student_id": line.student_id,
                "account_code": line.account_code,
                "term": line.term,
                "amount": str(line.amount),
                "reference": line.reference,
            },
        )
        return line

    def charge_fee(
        self,
        *,
        student_id: object,
        account_code: object,
        term: object,
        amount: object,
        description: object,
        actor: str = "system",
        line_id: object | None = None,
        reference: object = "",
    ) -> LedgerLine:
        student = clean_student_id(student_id)
        account = clean_code(account_code)
        term_text = str(term).strip().upper()
        count = len([line for line in self._lines.values() if line.student_id == student and line.term == term_text])
        resolved_line_id = line_id or f"{student}-{term_text}-{account}-{count + 1}"

        return self.post(
            LedgerLine(
                line_id=str(resolved_line_id),
                student_id=student,
                account_code=account,
                term=term_text,
                amount=amount,
                kind=CHARGE,
                description=str(description),
                reference=str(reference),
            ),
            actor=actor,
        )

    def record_payment(
        self,
        *,
        student_id: object,
        term: object,
        amount: object,
        description: object,
        actor: str = "system",
        account_code: object = "cash",
        line_id: object | None = None,
        reference: object = "",
    ) -> LedgerLine:
        student = clean_student_id(student_id)
        account = clean_code(account_code)
        term_text = str(term).strip().upper()
        count = len([line for line in self._lines.values() if line.student_id == student and line.term == term_text])
        resolved_line_id = line_id or f"{student}-{term_text}-{account}-payment-{count + 1}"

        return self.post(
            LedgerLine(
                line_id=str(resolved_line_id),
                student_id=student,
                account_code=account,
                term=term_text,
                amount=amount,
                kind=PAYMENT,
                description=str(description),
                reference=str(reference),
            ),
            actor=actor,
        )

    def apply_waiver(
        self,
        *,
        student_id: object,
        term: object,
        amount: object,
        description: object,
        actor: str = "system",
        account_code: object = "waiver",
        line_id: object | None = None,
        reference: object = "",
    ) -> LedgerLine:
        student = clean_student_id(student_id)
        account = clean_code(account_code)
        term_text = str(term).strip().upper()
        count = len([line for line in self._lines.values() if line.student_id == student and line.term == term_text])
        resolved_line_id = line_id or f"{student}-{term_text}-{account}-waiver-{count + 1}"

        return self.post(
            LedgerLine(
                line_id=str(resolved_line_id),
                student_id=student,
                account_code=account,
                term=term_text,
                amount=amount,
                kind=WAIVER,
                description=str(description),
                reference=str(reference),
            ),
            actor=actor,
        )

    def bill_student_from_schedule(
        self,
        *,
        student: object,
        schedule: FeeSchedule,
        term: object,
        actor: str = "system",
    ) -> list[LedgerLine]:
        student_id = clean_student_id(getattr(student, "student_id"))
        term_text = str(term).strip().upper()
        posted: list[LedgerLine] = []

        for item in schedule.expected_items(student):
            posted.append(
                self.charge_fee(
                    student_id=student_id,
                    account_code=item.account_code,
                    term=term_text,
                    amount=item.amount,
                    description=item.description,
                    actor=actor,
                    line_id=f"{student_id}-{term_text}-{schedule.schedule_id}-{item.item_code}",
                    reference=f"schedule:{schedule.schedule_id}:{term_text}:{item.item_code}",
                )
            )

        return posted

    def statement(self, student_id: object) -> list[LedgerLine]:
        student = clean_student_id(student_id)
        return sorted(
            [line for line in self._lines.values() if line.student_id == student],
            key=lambda line: (line.posted_at, line.line_id),
        )

    def balance_for_student(self, student_id: object, *, term: object | None = None) -> Decimal:
        student = clean_student_id(student_id)
        term_text = str(term).strip().upper() if term is not None else None
        total = Decimal("0.00")

        for line in self._lines.values():
            if line.student_id != student:
                continue
            if term_text is not None and line.term != term_text:
                continue
            total += line.signed_amount

        return money(total)

    def account_balance(self, account_code: object) -> Decimal:
        account = clean_code(account_code)
        total = Decimal("0.00")

        for line in self._lines.values():
            if line.account_code == account:
                total += line.signed_amount

        return money(total)

    def term_summary(self, term: object) -> dict[str, Decimal]:
        term_text = str(term).strip().upper()
        summary = {
            "charges": Decimal("0.00"),
            "payments": Decimal("0.00"),
            "waivers": Decimal("0.00"),
            "balance": Decimal("0.00"),
        }

        for line in self._lines.values():
            if line.term != term_text:
                continue
            if line.kind == CHARGE:
                summary["charges"] += line.amount
            elif line.kind == PAYMENT:
                summary["payments"] += line.amount
            elif line.kind == WAIVER:
                summary["waivers"] += line.amount
            summary["balance"] += line.signed_amount

        return {key: money(value) for key, value in summary.items()}

    def to_records(self) -> list[dict[str, object]]:
        return [line.to_dict() for line in sorted(self._lines.values(), key=lambda item: item.line_id)]

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_records(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path, *, audit: AuditLedger | None = None) -> "StudentLedger":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("student ledger file must contain a list")
        return cls((LedgerLine.from_dict(record) for record in payload), audit=audit)

    def __len__(self) -> int:
        return len(self._lines)
