from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Iterable

from campusops.audit.ledger import AuditLedger


QUEUED = "queued"
SENT = "sent"
FAILED = "failed"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: object) -> str:
    text = str(value).strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def clean_code(value: object) -> str:
    text = clean_text(value).lower()
    for mark in (" ", "-", ".", "/", "\\"):
        text = text.replace(mark, "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def parse_iso(value: object) -> datetime:
    text = clean_text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class NotificationTemplate:
    template_id: str
    subject: str
    body: str
    channel: str = "email"

    def __post_init__(self) -> None:
        template_id = clean_code(self.template_id)
        subject = clean_text(self.subject)
        body = str(self.body).strip()
        channel = clean_code(self.channel) or "email"

        if not template_id:
            raise ValueError("notification template id is required")
        if not subject:
            raise ValueError("notification template subject is required")
        if not body:
            raise ValueError("notification template body is required")

        object.__setattr__(self, "template_id", template_id)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "channel", channel)

    def render(self, context: dict[str, object]) -> tuple[str, str]:
        safe_context = {key: str(value) for key, value in context.items()}
        return (
            Template(self.subject).safe_substitute(safe_context),
            Template(self.body).safe_substitute(safe_context),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "subject": self.subject,
            "body": self.body,
            "channel": self.channel,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "NotificationTemplate":
        return cls(
            template_id=payload["template_id"],
            subject=payload["subject"],
            body=payload["body"],
            channel=payload.get("channel", "email"),
        )


@dataclass(frozen=True)
class NotificationMessage:
    message_id: str
    recipient: str
    subject: str
    body: str
    channel: str = "email"
    status: str = QUEUED
    created_at: str = field(default_factory=utc_now_iso)
    send_after: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        message_id = clean_code(self.message_id)
        recipient = clean_text(self.recipient)
        subject = clean_text(self.subject)
        body = str(self.body).strip()
        channel = clean_code(self.channel) or "email"
        status = clean_code(self.status)

        if status not in {QUEUED, SENT, FAILED}:
            raise ValueError(f"unsupported notification status: {self.status}")
        if not message_id:
            raise ValueError("notification message id is required")
        if not recipient:
            raise ValueError("notification recipient is required")
        if not subject:
            raise ValueError("notification subject is required")
        if not body:
            raise ValueError("notification body is required")

        created_at = parse_iso(self.created_at).isoformat()
        send_after = parse_iso(self.send_after).isoformat() if self.send_after else None

        object.__setattr__(self, "message_id", message_id)
        object.__setattr__(self, "recipient", recipient)
        object.__setattr__(self, "subject", subject)
        object.__setattr__(self, "body", body)
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "send_after", send_after)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def with_status(self, status: str) -> "NotificationMessage":
        return NotificationMessage(
            message_id=self.message_id,
            recipient=self.recipient,
            subject=self.subject,
            body=self.body,
            channel=self.channel,
            status=status,
            created_at=self.created_at,
            send_after=self.send_after,
            metadata=self.metadata,
        )

    def is_due(self, now: object | None = None) -> bool:
        if self.status != QUEUED:
            return False
        if not self.send_after:
            return True
        current = parse_iso(now or utc_now_iso())
        return parse_iso(self.send_after) <= current

    def to_dict(self) -> dict[str, object]:
        return {
            "message_id": self.message_id,
            "recipient": self.recipient,
            "subject": self.subject,
            "body": self.body,
            "channel": self.channel,
            "status": self.status,
            "created_at": self.created_at,
            "send_after": self.send_after,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "NotificationMessage":
        return cls(
            message_id=payload["message_id"],
            recipient=payload["recipient"],
            subject=payload["subject"],
            body=payload["body"],
            channel=payload.get("channel", "email"),
            status=payload.get("status", QUEUED),
            created_at=payload.get("created_at", utc_now_iso()),
            send_after=payload.get("send_after"),
            metadata=payload.get("metadata") or {},
        )


class NotificationOutbox:
    def __init__(
        self,
        templates: Iterable[NotificationTemplate] | None = None,
        messages: Iterable[NotificationMessage] | None = None,
        *,
        audit: AuditLedger | None = None,
    ) -> None:
        self._templates: dict[str, NotificationTemplate] = {}
        self._messages: dict[str, NotificationMessage] = {}
        self.audit = audit or AuditLedger()

        for template in templates or ():
            self.add_template(template, audit_event=False)
        for message in messages or ():
            if message.message_id in self._messages:
                raise ValueError(f"notification message already exists: {message.message_id}")
            self._messages[message.message_id] = message

    def add_template(self, template: NotificationTemplate, *, actor: str = "system", audit_event: bool = True) -> NotificationTemplate:
        if template.template_id in self._templates:
            raise ValueError(f"notification template already exists: {template.template_id}")
        self._templates[template.template_id] = template
        if audit_event:
            self.audit.record(
                event_type="notification.template_created",
                actor=actor,
                entity_type="notification_template",
                entity_id=template.template_id,
                message=f"Created notification template {template.template_id}",
                metadata={"channel": template.channel},
            )
        return template

    def get_template(self, template_id: object) -> NotificationTemplate:
        key = clean_code(template_id)
        try:
            return self._templates[key]
        except KeyError as exc:
            raise KeyError(f"unknown notification template: {key}") from exc

    def queue(self, message: NotificationMessage, *, actor: str = "system") -> NotificationMessage:
        if message.message_id in self._messages:
            raise ValueError(f"notification message already exists: {message.message_id}")
        self._messages[message.message_id] = message
        self.audit.record(
            event_type="notification.queued",
            actor=actor,
            entity_type="notification_message",
            entity_id=message.message_id,
            message=f"Queued notification for {message.recipient}",
            metadata={"recipient": message.recipient, "channel": message.channel, "status": message.status},
        )
        return message

    def queue_from_template(
        self,
        *,
        message_id: object,
        template_id: object,
        recipient: object,
        context: dict[str, object],
        send_after: object | None = None,
        actor: str = "system",
    ) -> NotificationMessage:
        template = self.get_template(template_id)
        subject, body = template.render(context)
        return self.queue(
            NotificationMessage(
                message_id=str(message_id),
                recipient=str(recipient),
                subject=subject,
                body=body,
                channel=template.channel,
                send_after=str(send_after) if send_after else None,
                metadata={"template_id": template.template_id, "context": deepcopy(dict(context))},
            ),
            actor=actor,
        )

    def get_message(self, message_id: object) -> NotificationMessage:
        key = clean_code(message_id)
        try:
            return self._messages[key]
        except KeyError as exc:
            raise KeyError(f"unknown notification message: {key}") from exc

    def mark_sent(self, message_id: object, *, actor: str = "system") -> NotificationMessage:
        message = self.get_message(message_id).with_status(SENT)
        self._messages[message.message_id] = message
        self.audit.record(
            event_type="notification.sent",
            actor=actor,
            entity_type="notification_message",
            entity_id=message.message_id,
            message=f"Marked notification {message.message_id} as sent",
            metadata={"recipient": message.recipient},
        )
        return message

    def mark_failed(self, message_id: object, *, reason: str, actor: str = "system") -> NotificationMessage:
        message = self.get_message(message_id).with_status(FAILED)
        metadata = deepcopy(message.metadata)
        metadata["failure_reason"] = clean_text(reason)
        message = NotificationMessage(
            message_id=message.message_id,
            recipient=message.recipient,
            subject=message.subject,
            body=message.body,
            channel=message.channel,
            status=FAILED,
            created_at=message.created_at,
            send_after=message.send_after,
            metadata=metadata,
        )
        self._messages[message.message_id] = message
        self.audit.record(
            event_type="notification.failed",
            actor=actor,
            entity_type="notification_message",
            entity_id=message.message_id,
            message=f"Marked notification {message.message_id} as failed",
            metadata={"recipient": message.recipient, "reason": clean_text(reason)},
        )
        return message

    def due_messages(self, now: object | None = None) -> list[NotificationMessage]:
        return sorted(
            [message for message in self._messages.values() if message.is_due(now)],
            key=lambda item: (item.send_after or item.created_at, item.message_id),
        )

    def messages_for_recipient(self, recipient: object) -> list[NotificationMessage]:
        wanted = clean_text(recipient)
        return sorted(
            [message for message in self._messages.values() if message.recipient == wanted],
            key=lambda item: (item.created_at, item.message_id),
        )

    def status_counts(self) -> dict[str, int]:
        counts = {QUEUED: 0, SENT: 0, FAILED: 0}
        for message in self._messages.values():
            counts[message.status] += 1
        return counts

    def to_dict(self) -> dict[str, object]:
        return {
            "templates": [
                template.to_dict()
                for template in sorted(self._templates.values(), key=lambda item: item.template_id)
            ],
            "messages": [
                message.to_dict()
                for message in sorted(self._messages.values(), key=lambda item: item.message_id)
            ],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path, *, audit: AuditLedger | None = None) -> "NotificationOutbox":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        templates = [NotificationTemplate.from_dict(row) for row in payload.get("templates", ())]
        messages = [NotificationMessage.from_dict(row) for row in payload.get("messages", ())]
        return cls(templates=templates, messages=messages, audit=audit)

    def __len__(self) -> int:
        return len(self._messages)
