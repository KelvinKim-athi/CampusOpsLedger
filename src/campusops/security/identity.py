from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


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


def clean_username(value: object) -> str:
    username = clean_code(value)
    if not username:
        raise ValueError("username is required")
    return username


def clean_permission(value: object) -> str:
    permission = clean_code(value)
    if not permission:
        raise ValueError("permission is required")
    return permission


@dataclass(frozen=True)
class Role:
    role_id: str
    name: str
    permissions: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        role_id = clean_code(self.role_id)
        name = clean_text(self.name)

        if not role_id:
            raise ValueError("role id is required")
        if not name:
            raise ValueError("role name is required")

        permissions = tuple(sorted({clean_permission(permission) for permission in self.permissions}))

        object.__setattr__(self, "role_id", role_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "permissions", permissions)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def allows(self, permission: object) -> bool:
        return clean_permission(permission) in self.permissions

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "permissions": list(self.permissions),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Role":
        return cls(
            role_id=payload["role_id"],
            name=payload["name"],
            permissions=tuple(payload.get("permissions") or ()),
            metadata=payload.get("metadata") or {},
        )


@dataclass(frozen=True)
class StaffUser:
    username: str
    full_name: str
    roles: tuple[str, ...] = field(default_factory=tuple)
    active: bool = True
    department: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        username = clean_username(self.username)
        full_name = clean_text(self.full_name)
        department = clean_text(self.department)

        if not full_name:
            raise ValueError("staff full name is required")

        roles = tuple(sorted({clean_code(role) for role in self.roles if clean_code(role)}))

        object.__setattr__(self, "username", username)
        object.__setattr__(self, "full_name", full_name)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "department", department)
        object.__setattr__(self, "metadata", deepcopy(dict(self.metadata)))

    def has_role(self, role_id: object) -> bool:
        return clean_code(role_id) in self.roles

    def with_roles(self, roles: tuple[str, ...]) -> "StaffUser":
        return StaffUser(
            username=self.username,
            full_name=self.full_name,
            roles=roles,
            active=self.active,
            department=self.department,
            metadata=self.metadata,
        )

    def with_active(self, active: bool) -> "StaffUser":
        return StaffUser(
            username=self.username,
            full_name=self.full_name,
            roles=self.roles,
            active=active,
            department=self.department,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "full_name": self.full_name,
            "roles": list(self.roles),
            "active": self.active,
            "department": self.department,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StaffUser":
        return cls(
            username=payload["username"],
            full_name=payload["full_name"],
            roles=tuple(payload.get("roles") or ()),
            active=bool(payload.get("active", True)),
            department=payload.get("department", ""),
            metadata=payload.get("metadata") or {},
        )
