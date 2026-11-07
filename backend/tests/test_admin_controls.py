import os
import pytest
from jose import jwt

from app.rbac import ROLE_PERMISSIONS, ROLE_DESCRIPTIONS, role_profile
from app.p0_auth import DEV_IDENTITY_ROLES, validate_dev_identity


class TestAdminObservability:
    def test_system_admin_observability_reports_health_roles_and_workflows(self, client, admin_headers):
        response = client.get("/api/p0/admin/observability", headers=admin_headers)
        assert response.status_code == 200
        payload = response.json()
        assert payload["health"]["status"] == "ok"
        assert payload["database"]["status"] == "ok"
        assert payload["users"]["total"] >= 1
        assert payload["workflows"]["document_versions"] is not None
        assert len(payload["role_matrix"]) == len(ROLE_PERMISSIONS)
        assert payload["role_matrix"][0]["role"] in ROLE_PERMISSIONS

    def test_non_admin_cannot_read_system_observability(self, client, quality_headers):
        response = client.get("/api/p0/admin/observability", headers=quality_headers)
        assert response.status_code == 403


class TestIdentityValidation:
    def test_dev_identity_requires_known_profile_role_pair(self):
        assert validate_dev_identity("admin", "system_admin") == ("u-admin", "system_admin")
        assert validate_dev_identity("u-quality", "head_quality") == ("u-quality", "head_quality")
        assert validate_dev_identity("u-safety/security", "head_safety") == ("u-safety/security", "head_safety")

    def test_dev_identity_rejects_role_mismatch(self):
        with pytest.raises(ValueError, match="does not match"):
            validate_dev_identity("u-quality", "system_admin")

    def test_dev_identity_rejects_unknown_actor(self):
        with pytest.raises(ValueError, match="Unknown actor"):
            validate_dev_identity("not-a-user", "head_quality")
    def test_seeded_user_profiles_resolve_to_their_exact_roles(self, client):
        expected = {
            "u-admin": ("u-admin", "system_admin"), "u-lib": ("u-quality", "librarian"), "u-quality": ("u-quality", "head_quality"),
            "u-records": ("u-quality", "records_custodian"),
            "u-safety": ("u-safety/security", "head_safety"), "u-security": ("u-safety/security", "head_security"),
            "u-safety/security": ("u-safety/security", "head_safety"), "u-ops": ("u-ops", "head_operations"),
            "u-chief-pilot": ("u-ops", "chief_pilot"), "u-flight-ops": ("u-flight-ops", "flight_ops_officer"), "u-training": ("u-ops", "head_training"),
            "u-maintenance": ("u-admin", "head_maintenance"), "u-dg": ("u-flight-ops", "dg_coordinator"), "u-reporter": ("u-reporter", "occurrence_reporter"),
            "u-auditor": ("u-auditor", "independent_auditor"), "u-accountable": ("u-accountable", "accountable_manager"),
        }
        for actor, (canonical_id, role) in expected.items():
            response = client.get("/api/p0/auth/profile", headers={"X-Role": role, "X-Actor": actor})
            assert response.status_code == 200, response.text
            assert response.json()["user"]["user_id"] == canonical_id
            assert response.json()["role"] == role


class TestRoleProfiles:
    def test_every_role_has_explicit_profile(self):
        assert set(ROLE_PERMISSIONS) == set(ROLE_DESCRIPTIONS)
        for role in ROLE_PERMISSIONS:
            profile = role_profile(role)
            assert profile["role"] == role
            assert profile["access_level"]
            assert isinstance(profile["permissions"], list)


class TestWorkflowStateMachine:
    def test_invalid_document_transition_is_rejected(self, client, librarian_headers):
        response = client.post(
            "/api/p0/versions",
            json={"document_id": "DOC-001", "version_number": "99.99.01", "content": "workflow test"},
            headers=librarian_headers,
        )
        version_id = response.json()["version_id"]
        response = client.patch(
            f"/api/p0/versions/{version_id}/state?state=published",
            headers=librarian_headers,
        )
        assert response.status_code == 422
        assert "Invalid version transition" in response.json()["detail"]

    def test_document_state_transition_creates_audit_event(self, client, librarian_headers):
        response = client.post(
            "/api/p0/versions",
            json={"document_id": "DOC-001", "version_number": "99.99.02", "content": "workflow audit"},
            headers=librarian_headers,
        )
        version_id = response.json()["version_id"]
        response = client.patch(
            f"/api/p0/versions/{version_id}/state?state=in_review",
            headers=librarian_headers,
        )
        assert response.status_code == 200
        events = client.get(
            "/api/p0/audit-events?entity_type=document_version&entity_id=" + version_id,
            headers={"X-Role": "system_admin", "X-Actor": "admin"},
        )
        assert events.status_code == 200
        assert any(event["action"] == "state_changed" for event in events.json())
