from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from campusops.audit.ledger import AuditLedger
from campusops.security.identity import Role, StaffUser, clean_code, clean_permission, clean_username
from campusops.security.policy import PermissionPolicy


class AccessManager:
    def __init__(
        self,
        users: Iterable[StaffUser] | None = None,
        roles: Iterable[Role] | None = None,
        *,
        audit: AuditLedger | None = None,
    ) -> None:
        self._users: dict[str, StaffUser] = {}
        self.policy = PermissionPolicy()
        self.audit = audit or AuditLedger()

        for role in roles or ():
            self.policy.add_role(role)
        for user in users or ():
            self._insert_existing_user(user)

    def _insert_existing_user(self, user: StaffUser) -> None:
        if user.username in self._users:
            raise ValueError(f"user already exists: {user.username}")
        self._users[user.username] = user

    def add_role(self, role: Role, *, actor: str = "system") -> Role:
        created = self.policy.add_role(role)
        self.audit.record(
            event_type="security.role_created",
            actor=actor,
            entity_type="role",
            entity_id=role.role_id,
            message=f"Created role {role.name}",
            metadata={"permissions": list(role.permissions)},
        )
        return created

    def add_user(self, user: StaffUser, *, actor: str = "system") -> StaffUser:
        if user.username in self._users:
            raise ValueError(f"user already exists: {user.username}")

        missing_roles = [role for role in user.roles if role not in self.policy.roles]
        if missing_roles:
            raise KeyError(f"unknown role(s): {', '.join(missing_roles)}")

        self._users[user.username] = user
        self.audit.record(
            event_type="security.user_created",
            actor=actor,
            entity_type="staff_user",
            entity_id=user.username,
            message=f"Created staff user {user.full_name}",
            metadata={"roles": list(user.roles), "department": user.department, "active": user.active},
        )
        return user

    def get_user(self, username: object) -> StaffUser:
        key = clean_username(username)
        try:
            return self._users[key]
        except KeyError as exc:
            raise KeyError(f"unknown user: {key}") from exc

    def grant_role(self, username: object, role_id: object, *, actor: str = "system") -> StaffUser:
        user = self.get_user(username)
        role = self.policy.get_role(role_id)

        roles = tuple(sorted(set(user.roles) | {role.role_id}))
        updated = user.with_roles(roles)
        self._users[updated.username] = updated

        self.audit.record(
            event_type="security.role_granted",
            actor=actor,
            entity_type="staff_user",
            entity_id=updated.username,
            message=f"Granted {role.role_id} to {updated.username}",
            metadata={"role_id": role.role_id, "roles": list(updated.roles)},
        )
        return updated

    def revoke_role(self, username: object, role_id: object, *, actor: str = "system") -> StaffUser:
        user = self.get_user(username)
        role_key = clean_code(role_id)

        roles = tuple(role for role in user.roles if role != role_key)
        updated = user.with_roles(roles)
        self._users[updated.username] = updated

        self.audit.record(
            event_type="security.role_revoked",
            actor=actor,
            entity_type="staff_user",
            entity_id=updated.username,
            message=f"Revoked {role_key} from {updated.username}",
            metadata={"role_id": role_key, "roles": list(updated.roles)},
        )
        return updated

    def set_active(self, username: object, active: bool, *, actor: str = "system") -> StaffUser:
        user = self.get_user(username)
        updated = user.with_active(bool(active))
        self._users[updated.username] = updated

        self.audit.record(
            event_type="security.user_enabled" if active else "security.user_disabled",
            actor=actor,
            entity_type="staff_user",
            entity_id=updated.username,
            message=f"Set {updated.username} active={updated.active}",
            metadata={"active": updated.active},
        )
        return updated

    def can(self, username: object, permission: object) -> bool:
        return self.policy.can(self.get_user(username), permission)

    def require(self, username: object, permission: object) -> None:
        self.policy.require(self.get_user(username), permission)

    def check_access(
        self,
        *,
        username: object,
        permission: object,
        resource_type: object,
        resource_id: object,
        actor: str = "system",
    ) -> bool:
        user = self.get_user(username)
        wanted = clean_permission(permission)
        allowed = self.policy.can(user, wanted)

        self.audit.record(
            event_type="security.access_allowed" if allowed else "security.access_denied",
            actor=actor,
            entity_type=clean_code(resource_type) or "resource",
            entity_id=str(resource_id).strip(),
            message=f"Checked {wanted} for {user.username}",
            metadata={
                "username": user.username,
                "permission": wanted,
                "allowed": allowed,
            },
        )
        return allowed

    def users_with_role(self, role_id: object) -> list[StaffUser]:
        key = clean_code(role_id)
        return sorted(
            [user for user in self._users.values() if user.has_role(key)],
            key=lambda user: user.username,
        )

    def users_with_permission(self, permission: object) -> list[StaffUser]:
        return self.policy.users_with_permission(self._users.values(), permission)

    def to_dict(self) -> dict[str, object]:
        return {
            "roles": [role.to_dict() for role in sorted(self.policy.roles.values(), key=lambda item: item.role_id)],
            "users": [user.to_dict() for user in sorted(self._users.values(), key=lambda item: item.username)],
        }

    def save_json(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    @classmethod
    def load_json(cls, path: str | Path, *, audit: AuditLedger | None = None) -> "AccessManager":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        roles = [Role.from_dict(row) for row in payload.get("roles", ())]
        users = [StaffUser.from_dict(row) for row in payload.get("users", ())]
        return cls(users=users, roles=roles, audit=audit)

    def __len__(self) -> int:
        return len(self._users)
