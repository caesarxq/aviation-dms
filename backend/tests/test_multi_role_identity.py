import bcrypt
import os
import sqlite3

TEST_PASSWORD = "Multi-Role-Test-Password-2026!"
TEST_ORIGIN = "http://localhost:5173"


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
            "u-lib": {"librarian", "head_quality", "records_custodian"},
            "u-safety": {"head_safety", "head_security"},
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
        assert ("u-quality", "u-lib") in aliases
        assert ("u-records", "u-lib") in aliases
        assert ("quality", "u-lib") in aliases
        assert conn.execute("SELECT is_active, merged_into_user_id FROM users WHERE user_id = 'u-quality'").fetchone() == (0, "u-lib")
        assert conn.execute("SELECT owner_id FROM compliance_obligations WHERE obligation_id = 'CO-007'").fetchone() == ("u-quality",)
    finally:
        conn.close()


def test_active_role_switch_updates_session_permissions_and_keeps_canonical_actor(client):
    _set_password("u-lib", TEST_PASSWORD)
    try:
        login = _login(client)
        assert login.status_code == 200
        profile = client.get("/api/p0/auth/profile").json()
        assert profile["user"]["user_id"] == "u-lib"
        assert profile["active_role"] == "librarian"
        assert set(profile["roles"]) == {"librarian", "head_quality", "records_custodian"}
        assert "document:approve" not in profile["permissions"]

        switched = client.post(
            "/api/p0/auth/active-role",
            json={"active_role": "head_quality"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert switched.status_code == 200
        assert switched.json()["user"]["user_id"] == "u-lib"
        assert switched.json()["active_role"] == "head_quality"
        assert "document:approve" in switched.json()["permissions"]
        assert set(switched.json()["roles"]) == {"librarian", "head_quality", "records_custodian"}

        session = client.get("/api/p0/auth/profile").json()
        assert session["user"]["user_id"] == "u-lib"
        assert session["role"] == "head_quality"
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        try:
            audit_actor = conn.execute(
                "SELECT actor_id FROM audit_events WHERE entity_type = 'auth_session' "
                "AND action = 'active_role_switched' ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()[0]
            assert audit_actor == "u-lib"
        finally:
            conn.close()
    finally:
        _set_password("u-lib", None)


def test_active_role_switch_rejects_unassigned_role(client):
    _set_password("u-lib", TEST_PASSWORD)
    try:
        assert _login(client).status_code == 200
        denied = client.post(
            "/api/p0/auth/active-role",
            json={"active_role": "system_admin"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert denied.status_code == 403
        assert client.get("/api/p0/auth/profile").json()["active_role"] == "librarian"
    finally:
        _set_password("u-lib", None)


def test_sod_recognizes_legacy_actor_id_after_role_consolidation(client):
    _set_password("u-lib", TEST_PASSWORD)
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute(
            """INSERT INTO change_requests
               (cr_id, document_id, title, description, change_type, status, requester_id,
                created_at, updated_at, created_by, updated_by)
               VALUES ('CR-LEGACY-ACTOR', 'DOC-001', 'Legacy actor', 'SOD test', 'minor', 'submitted',
                       'u-quality', '2026-01-01', '2026-01-01', 'u-quality', 'u-quality')"""
        )
        conn.commit()
    finally:
        conn.close()

    try:
        assert _login(client).status_code == 200
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
        _set_password("u-lib", None)


def test_admin_user_listing_returns_canonical_profiles_and_assigned_roles(client, admin_headers):
    response = client.get("/api/p0/auth/users", headers=admin_headers)
    assert response.status_code == 200
    users = {user["user_id"]: user for user in response.json()}
    assert set(users["u-lib"]["roles"]) == {"librarian", "head_quality", "records_custodian"}
    assert "u-quality" not in users


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
    _set_password("u-lib", TEST_PASSWORD)
    from fastapi.testclient import TestClient
    from app.main import app

    other_client = TestClient(app)
    try:
        assert _login(client, "admin").status_code == 200
        assert _login(other_client).status_code == 200
        update = client.put(
            "/api/p0/auth/users/u-lib/roles",
            json={"roles": ["librarian", "head_quality"]},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert update.status_code == 200
        assert set(update.json()["roles"]) == {"librarian", "head_quality"}
        assert other_client.get("/api/p0/auth/profile").status_code == 401
    finally:
        other_client.close()
        _set_password("u-admin", None)
        _set_password("u-lib", None)
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        conn.execute("DELETE FROM user_roles WHERE user_id = 'u-lib'")
        conn.executemany(
            "INSERT INTO user_roles (user_id, role) VALUES ('u-lib', ?)",
            [("librarian",), ("head_quality",), ("records_custodian",)],
        )
        conn.execute("UPDATE users SET role = 'librarian' WHERE user_id = 'u-lib'")
        conn.commit()
        conn.close()
