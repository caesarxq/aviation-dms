import bcrypt
import os
import sqlite3
import pytest

TEST_PASSWORD = "Multi-Role-Test-Password-2026!"
TEST_ORIGIN = "http://localhost:5173"
SWITCHABLE_ROLE_GROUPS = [
    ("u-admin", "admin", ("system_admin", "head_maintenance")),
    ("u-quality", "librarian", ("head_quality", "librarian", "records_custodian")),
    ("u-safety/security", "safety", ("head_safety", "head_security")),
    ("u-ops", "ops", ("head_operations", "chief_pilot", "head_training")),
    ("u-flight-ops", "flight_ops", ("flight_ops_officer", "dg_coordinator")),
]


def _set_password(user_id: str, password: str | None):
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() if password else None
        conn.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (hashed, user_id))
        conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def _login(client, username="librarian"):
    return client.post(
        "/api/p0/auth/login",
        json={"username": username, "password": TEST_PASSWORD},
        headers={"Origin": TEST_ORIGIN},
    )


def test_verified_accounts_consolidate_roles_and_preserve_legacy_ids(client):
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        expected = {
            "u-admin": {"system_admin", "head_maintenance"},
            "u-quality": {"head_quality", "librarian", "records_custodian"},
            "u-safety/security": {"head_safety", "head_security"},
            "u-ops": {"head_operations", "chief_pilot", "head_training"},
            "u-flight-ops": {"flight_ops_officer", "dg_coordinator"},
        }
        for canonical_id, roles in expected.items():
            row = conn.execute("SELECT is_active, merged_into_user_id FROM users WHERE user_id = ?", (canonical_id,)).fetchone()
            assert row == (1, None)
            assigned = {
                role for (role,) in conn.execute(
                    "SELECT role FROM user_roles WHERE user_id = ?", (canonical_id,)
                ).fetchall()
            }
            assert assigned == roles

        aliases = conn.execute(
            "SELECT legacy_user_id, canonical_user_id FROM user_id_aliases"
        ).fetchall()
        assert ("u-lib", "u-quality") in aliases
        assert ("u-records", "u-quality") in aliases
        assert ("quality", "u-quality") in aliases
        assert ("u-safety", "u-safety/security") in aliases
        assert ("u-security", "u-safety/security") in aliases
        assert ("safety", "u-safety/security") in aliases
        assert ("security", "u-safety/security") in aliases
        assert conn.execute("SELECT is_active, merged_into_user_id FROM users WHERE user_id = 'u-quality'").fetchone() == (1, None)
        assert conn.execute("SELECT is_active, merged_into_user_id FROM users WHERE user_id = 'u-lib'").fetchone() == (0, "u-quality")
        assert conn.execute("SELECT owner_id FROM compliance_obligations WHERE obligation_id = 'CO-007'").fetchone() == ("u-quality",)
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("user_id", "username", "assigned_roles"),
    SWITCHABLE_ROLE_GROUPS,
    ids=[f"{username}-roles" for _, username, _ in SWITCHABLE_ROLE_GROUPS],
)
def test_every_assigned_role_switches_to_every_other_assigned_role(
    client, user_id, username, assigned_roles
):
    from app.rbac import ROLE_PERMISSIONS

    _set_password(user_id, TEST_PASSWORD)
    try:
        assert _login(client, username).status_code == 200
        expected_roles = set(assigned_roles)
        for source_role in assigned_roles:
            selected = client.post(
                "/api/p0/auth/active-role",
                json={"active_role": source_role},
                headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
            )
            assert selected.status_code == 200
            assert selected.json()["active_role"] == source_role

            for target_role in assigned_roles:
                if target_role == source_role:
                    continue
                switched = client.post(
                    "/api/p0/auth/active-role",
                    json={"active_role": target_role},
                    headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
                )
                assert switched.status_code == 200
                profile = switched.json()
                assert profile["active_role"] == target_role
                assert profile["role"] == target_role
                assert profile["user"]["role"] == target_role
                assert profile["user"]["active_role"] == target_role
                assert set(profile["roles"]) == expected_roles
                assert profile["permissions"] == sorted(ROLE_PERMISSIONS[target_role])
                assert isinstance(profile["onboarding_completed"], bool)
                assert client.get("/api/p0/auth/profile").json()["active_role"] == target_role
    finally:
        _set_password(user_id, None)


def test_active_role_switch_updates_session_permissions_and_keeps_canonical_actor(client):
    _set_password("u-quality", TEST_PASSWORD)
    try:
        login = _login(client, "librarian")
        assert login.status_code == 200
        profile = client.get("/api/p0/auth/profile").json()
        assert profile["user"]["user_id"] == "u-quality"
        assert profile["active_role"] == "head_quality"
        assert set(profile["roles"]) == {"librarian", "head_quality", "records_custodian"}
        assert "document:approve" in profile["permissions"]

        switched = client.post(
            "/api/p0/auth/active-role",
            json={"active_role": "librarian"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert switched.status_code == 200
        assert switched.json()["user"]["user_id"] == "u-quality"
        assert switched.json()["active_role"] == "librarian"
        assert "document:approve" not in switched.json()["permissions"]
        assert set(switched.json()["roles"]) == {"librarian", "head_quality", "records_custodian"}

        session = client.get("/api/p0/auth/profile").json()
        assert session["user"]["user_id"] == "u-quality"
        assert session["role"] == "librarian"
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            audit_actor = conn.execute(
                "SELECT actor_id FROM audit_events WHERE entity_type = 'auth_session' "
                "AND action = 'active_role_switched' ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()[0]
            assert audit_actor == "u-quality"
        finally:
            conn.close()
    finally:
        _set_password("u-quality", None)


def test_system_admin_switches_to_head_maintenance_with_complete_profile(client):
    _set_password("u-admin", TEST_PASSWORD)
    try:
        login_response = _login(client, "admin")
        assert login_response.status_code == 200
        login_profile = login_response.json()
        assert login_profile["active_role"] == "system_admin"
        assert login_profile["user"]["active_role"] == "system_admin"
        assert isinstance(login_profile["onboarding_completed"], bool)
        assert "settings:manage" in login_profile["permissions"]
        initial = client.get("/api/p0/auth/profile").json()
        assert initial["active_role"] == "system_admin"
        assert set(initial["roles"]) == {"system_admin", "head_maintenance"}
        assert isinstance(initial["onboarding_completed"], bool)

        switched = client.post(
            "/api/p0/auth/active-role",
            json={"active_role": "head_maintenance"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert switched.status_code == 200
        profile = switched.json()
        assert profile["user"]["user_id"] == "u-admin"
        assert profile["active_role"] == "head_maintenance"
        assert profile["user"]["active_role"] == "head_maintenance"
        assert profile["onboarding_completed"] is initial["onboarding_completed"]
        assert "aircraft:manage" in profile["permissions"]
        assert "settings:manage" not in profile["permissions"]

        back = client.post(
            "/api/p0/auth/active-role",
            json={"active_role": "system_admin"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert back.status_code == 200
        assert back.json()["active_role"] == "system_admin"
        assert "settings:manage" in back.json()["permissions"]
        assert client.get("/api/p0/auth/profile").json()["active_role"] == "system_admin"
    finally:
        _set_password("u-admin", None)


def test_active_role_switch_rolls_back_if_audit_write_fails(client, monkeypatch):
    from app import p0_routes

    _set_password("u-quality", TEST_PASSWORD)
    try:
        assert _login(client, "librarian").status_code == 200

        async def fail_audit(*args, **kwargs):
            raise RuntimeError("simulated role-switch audit failure")

        monkeypatch.setattr(p0_routes, "log_audit_event", fail_audit)
        with pytest.raises(RuntimeError, match="simulated role-switch audit failure"):
            client.post(
                "/api/p0/auth/active-role",
                json={"active_role": "librarian"},
                headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
            )
        assert client.get("/api/p0/auth/profile").json()["active_role"] == "head_quality"
    finally:
        _set_password("u-quality", None)


def test_active_role_switch_rejects_unassigned_role(client):
    _set_password("u-quality", TEST_PASSWORD)
    try:
        assert _login(client, "librarian").status_code == 200
        denied = client.post(
            "/api/p0/auth/active-role",
            json={"active_role": "system_admin"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert denied.status_code == 403
        assert client.get("/api/p0/auth/profile").json()["active_role"] == "head_quality"
    finally:
        _set_password("u-quality", None)


def test_sod_recognizes_legacy_actor_id_after_role_consolidation(client):
    _set_password("u-quality", TEST_PASSWORD)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute(
            """INSERT INTO change_requests
               (cr_id, document_id, title, description, change_type, status, requester_id,
                created_at, updated_at, created_by, updated_by)
               VALUES ('CR-LEGACY-ACTOR', 'DOC-001', 'Legacy actor', 'SOD test', 'minor', 'submitted',
                       'u-lib', '2026-01-01', '2026-01-01', 'u-lib', 'u-lib')"""
        )
        conn.commit()
    finally:
        conn.close()

    try:
        assert _login(client, "librarian").status_code == 200
        switched = client.post(
            "/api/p0/auth/active-role",
            json={"active_role": "librarian"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert switched.status_code == 200
        switched = client.post(
            "/api/p0/auth/active-role",
            json={"active_role": "head_quality"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert switched.status_code == 200
        review = client.post(
            "/api/p1/change-requests/CR-LEGACY-ACTOR/review",
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert review.status_code == 403
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        conn.execute("DELETE FROM change_requests WHERE cr_id = 'CR-LEGACY-ACTOR'")
        conn.commit()
        conn.close()
        _set_password("u-quality", None)


def test_admin_user_listing_returns_canonical_profiles_and_assigned_roles(client, admin_headers):
    response = client.get("/api/p0/auth/users", headers=admin_headers)
    assert response.status_code == 200
    users = {user["user_id"]: user for user in response.json()}
    assert set(users["u-quality"]["roles"]) == {"head_quality", "librarian", "records_custodian"}
    assert "u-lib" not in users


def test_role_assignment_cannot_remove_the_last_system_administrator(client, admin_headers):
    response = client.put(
        "/api/p0/auth/users/u-admin/roles",
        json={"roles": ["head_maintenance"]},
        headers=admin_headers,
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot remove the last active system administrator"


def test_role_switch_requires_a_cookie_backed_session(client, librarian_headers):
    response = client.post(
        "/api/p0/auth/active-role",
        json={"active_role": "head_quality"},
        headers={"Origin": TEST_ORIGIN, **librarian_headers},
    )
    assert response.status_code == 401


def test_admin_role_assignment_revokes_target_sessions_and_is_authorized(client):
    _set_password("u-admin", TEST_PASSWORD)
    _set_password("u-quality", TEST_PASSWORD)
    from fastapi.testclient import TestClient
    from app.main import app

    other_client = TestClient(app)
    try:
        assert _login(client, "admin").status_code == 200
        assert _login(other_client, "librarian").status_code == 200
        update = client.put(
            "/api/p0/auth/users/u-quality/roles",
            json={"roles": ["librarian", "head_quality"]},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert update.status_code == 200
        assert set(update.json()["roles"]) == {"librarian", "head_quality"}
        assert other_client.get("/api/p0/auth/profile").status_code == 401
    finally:
        other_client.close()
        _set_password("u-admin", None)
        _set_password("u-quality", None)
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        conn.execute("DELETE FROM user_roles WHERE user_id = 'u-quality'")
        conn.executemany(
            "INSERT INTO user_roles (user_id, role) VALUES ('u-quality', ?)",
            [("head_quality",), ("librarian",), ("records_custodian",)],
        )
        conn.execute("UPDATE users SET role = 'head_quality' WHERE user_id = 'u-quality'")
        conn.commit()
        conn.close()


def test_literal_slash_canonical_id_is_supported_by_admin_routes(client, admin_headers):
    roles = ["head_safety", "head_security"]
    encoded_user_id = "u-safety%2Fsecurity"
    updated = client.put(
        f"/api/p0/auth/users/{encoded_user_id}/roles",
        json={"roles": roles},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["user_id"] == "u-safety/security"
    assert set(updated.json()["roles"]) == set(roles)

    setup = client.post(
        f"/api/p0/auth/users/{encoded_user_id}/setup-token",
        headers=admin_headers,
    )
    assert setup.status_code == 200, setup.text
    assert setup.json()["use_once"] is True
