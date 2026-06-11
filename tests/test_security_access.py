import pytest

from campusops.security.access import AccessManager
from campusops.security.identity import Role, StaffUser, clean_permission
from campusops.security.policy import PermissionPolicy


def make_roles():
    return [
        Role(" Registrar ", "Registrar", permissions=("students.read", "students.write", "reports.view")),
        Role(" Finance-Officer ", "Finance Officer", permissions=("ledger.read", "ledger.write", "reports.view")),
        Role(" Lecturer ", "Lecturer", permissions=("attendance.write", "assessments.read")),
    ]


def make_manager():
    manager = AccessManager(roles=make_roles())
    manager.add_user(
        StaffUser(" Alice.Admin ", "Alice Admin", roles=("registrar",), department="Registry"),
        actor="system",
    )
    manager.add_user(
        StaffUser(" Bob.Finance ", "Bob Finance", roles=("finance officer",), department="Accounts"),
        actor="system",
    )
    return manager


def test_role_normalizes_permission_names_and_checks_membership():
    role = Role(
        role_id=" Finance Officer ",
        name=" Finance   Officer ",
        permissions=(" Ledger.Read ", "ledger-read", "reports.view", "reports.view"),
    )

    assert role.role_id == "finance_officer"
    assert role.name == "Finance Officer"
    assert role.permissions == ("ledger_read", "reports_view")
    assert role.allows("ledger.read") is True
    assert clean_permission("Reports View") == "reports_view"


def test_staff_user_normalizes_username_roles_and_metadata_copy():
    metadata = {"station": {"name": "main"}}
    user = StaffUser(
        username=" Alice.Admin ",
        full_name=" Alice   Admin ",
        roles=(" Registrar ", "registrar", "Finance Officer"),
        department=" Registry ",
        metadata=metadata,
    )

    metadata["station"]["name"] = "mutated"

    assert user.username == "alice_admin"
    assert user.full_name == "Alice Admin"
    assert user.roles == ("finance_officer", "registrar")
    assert user.department == "Registry"
    assert user.metadata == {"station": {"name": "main"}}


def test_permission_policy_collects_permissions_from_multiple_roles():
    policy = PermissionPolicy()
    for role in make_roles():
        policy.add_role(role)

    user = StaffUser("alice", "Alice", roles=("registrar", "finance-officer"))

    assert policy.permissions_for(user) == (
        "ledger_read",
        "ledger_write",
        "reports_view",
        "students_read",
        "students_write",
    )
    assert policy.can(user, "ledger.write") is True
    assert policy.can(user, "attendance.write") is False


def test_permission_policy_rejects_inactive_user_requirements():
    policy = PermissionPolicy()
    policy.add_role(Role("registrar", "Registrar", permissions=("students.read",)))
    user = StaffUser("alice", "Alice", roles=("registrar",), active=False)

    assert policy.can(user, "students.read") is False
    with pytest.raises(PermissionError, match="inactive user"):
        policy.require(user, "students.read")


def test_access_manager_adds_roles_users_and_writes_audit_events():
    manager = AccessManager()
    manager.add_role(Role("registrar", "Registrar", permissions=("students.read",)), actor="admin")
    manager.add_user(StaffUser("alice", "Alice Admin", roles=("registrar",)), actor="admin")

    assert len(manager) == 1
    assert manager.can("ALICE", "students.read") is True
    assert [event.event_type for event in manager.audit.all_events()] == [
        "security_role_created",
        "security_user_created",
    ]


def test_access_manager_rejects_users_with_unknown_roles():
    manager = AccessManager(roles=[Role("registrar", "Registrar", permissions=("students.read",))])

    with pytest.raises(KeyError, match="unknown role"):
        manager.add_user(StaffUser("alice", "Alice Admin", roles=("missing",)))


def test_grant_revoke_and_disable_user_change_access():
    manager = make_manager()

    assert manager.can("alice.admin", "ledger.write") is False

    manager.grant_role("alice.admin", "finance-officer", actor="admin")
    assert manager.can("alice.admin", "ledger.write") is True

    manager.revoke_role("alice.admin", "registrar", actor="admin")
    assert manager.can("alice.admin", "students.write") is False

    manager.set_active("alice.admin", False, actor="admin")
    assert manager.can("alice.admin", "ledger.write") is False


def test_check_access_records_allowed_and_denied_attempts():
    manager = make_manager()

    assert manager.check_access(
        username="alice.admin",
        permission="students.read",
        resource_type="student",
        resource_id="S001",
        actor="api",
    ) is True
    assert manager.check_access(
        username="bob.finance",
        permission="students.write",
        resource_type="student",
        resource_id="S001",
        actor="api",
    ) is False

    assert [event.event_type for event in manager.audit.all_events()[-2:]] == [
        "security_access_allowed",
        "security_access_denied",
    ]
    assert manager.audit.all_events()[-1].metadata["permission"] == "students_write"


def test_user_filters_by_role_and_permission_are_sorted():
    manager = make_manager()
    manager.grant_role("bob.finance", "registrar", actor="admin")

    assert [user.username for user in manager.users_with_role("registrar")] == ["alice_admin", "bob_finance"]
    assert [user.username for user in manager.users_with_permission("ledger.write")] == ["bob_finance"]


def test_access_manager_json_roundtrip(tmp_path):
    manager = make_manager()
    manager.grant_role("alice.admin", "finance-officer", actor="admin")

    path = tmp_path / "access.json"
    manager.save_json(path)
    loaded = AccessManager.load_json(path)

    assert len(loaded) == 2
    assert loaded.can("alice.admin", "ledger.write") is True
    assert loaded.can("bob.finance", "ledger.write") is True
    assert loaded.to_dict()["roles"][0]["role_id"] == "finance_officer"
