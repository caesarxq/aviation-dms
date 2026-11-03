import pytest
from app.rbac import has_permission, check_sod, ROLE_PERMISSIONS, PERMISSIONS


def test_all_roles_defined():
    assert len(ROLE_PERMISSIONS) == 16


def test_system_admin_has_all_permissions():
    admin = ROLE_PERMISSIONS["system_admin"]
    assert admin == set(PERMISSIONS)


def test_librarian_cannot_approve():
    assert not has_permission("librarian", "document:approve")
    assert not has_permission("librarian", "document:publish")


def test_head_quality_can_approve_and_publish():
    assert has_permission("head_quality", "document:approve")
    assert has_permission("head_quality", "document:publish")


def test_head_quality_cannot_update():
    assert not has_permission("head_quality", "document:update")


def test_occurrence_reporter_permissions():
    assert has_permission("occurrence_reporter", "occurrence:report")
    assert has_permission("occurrence_reporter", "safety:create")
    assert not has_permission("occurrence_reporter", "document:create")


def test_sod_creator_cannot_publish():
    assert not check_sod("version", "publish", "u-lib", "u-lib")
    assert check_sod("version", "publish", "u-admin", "u-lib")


def test_sod_creator_cannot_approve():
    assert not check_sod("version", "approve", "u-lib", "u-lib")
    assert check_sod("version", "approve", "u-quality", "u-lib")


def test_risk_assessment_approval_permission_has_exact_existing_grants():
    granted_roles = {
        role for role, permissions in ROLE_PERMISSIONS.items()
        if "risk_assessment:approve" in permissions
    }
    assert granted_roles == {
        "system_admin", "accountable_manager", "head_safety", "head_operations", "chief_pilot",
    }


def test_unknown_role_no_permissions():
    assert not has_permission("nonexistent_role", "document:read")
    assert has_permission("nonexistent_role", "document:read") is False


def test_unknown_dev_role_returns_401(client):
    response = client.get("/api/p0/documents", headers={"X-Role": "not-a-role", "X-Actor": "eval"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Unknown role: not-a-role"


def test_as_contracted_minimal():
    assert has_permission("as_contracted", "document:read")
    assert has_permission("as_contracted", "safety:read")
    assert not has_permission("as_contracted", "document:create")