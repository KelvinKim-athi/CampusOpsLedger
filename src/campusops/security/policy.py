from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from campusops.security.identity import Role, StaffUser, clean_permission


@dataclass
class PermissionPolicy:
    roles: dict[str, Role] = field(default_factory=dict)

    def add_role(self, role: Role) -> Role:
        if role.role_id in self.roles:
            raise ValueError(f"role already exists: {role.role_id}")
        self.roles[role.role_id] = role
        return role

    def get_role(self, role_id: object) -> Role:
        key = str(role_id).strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        while "__" in key:
            key = key.replace("__", "_")
        key = key.strip("_")

        try:
            return self.roles[key]
        except KeyError as exc:
            raise KeyError(f"unknown role: {key}") from exc

    def permissions_for(self, user: StaffUser) -> tuple[str, ...]:
        permissions: set[str] = set()

        for role_id in user.roles:
            role = self.roles.get(role_id)
            if role is None:
                continue
            permissions.update(role.permissions)

        return tuple(sorted(permissions))

    def can(self, user: StaffUser, permission: object) -> bool:
        if not user.active:
            return False
        wanted = clean_permission(permission)
        return wanted in self.permissions_for(user)

    def require(self, user: StaffUser, permission: object) -> None:
        wanted = clean_permission(permission)
        if not user.active:
            raise PermissionError(f"inactive user cannot perform permission: {wanted}")
        if not self.can(user, wanted):
            raise PermissionError(f"user {user.username} lacks permission: {wanted}")

    def users_with_permission(self, users: Iterable[StaffUser], permission: object) -> list[StaffUser]:
        wanted = clean_permission(permission)
        return sorted(
            [user for user in users if self.can(user, wanted)],
            key=lambda user: user.username,
        )
