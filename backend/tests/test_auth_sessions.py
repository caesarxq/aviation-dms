import os
import sqlite3

import bcrypt


TEST_PASSWORD = "N0tARealCredential-Session-Test-2026!"
TEST_ORIGIN = "http://localhost:5173"


def _set_test_admin_password(password: str | None):
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() if password else None
        conn.execute("UPDATE users SET password_hash = ? WHERE user_id = 'u-admin'", (password_hash,))
        conn.execute("DELETE FROM auth_sessions WHERE user_id = 'u-admin'")
        conn.execute("DELETE FROM auth_login_attempts")
        conn.commit()
    finally:
        conn.close()


def test_login_issues_httponly_session_and_safe_profile(client):
    _set_test_admin_password(TEST_PASSWORD)
    try:
        response = client.post(
            "/api/p0/auth/login",
            json={"username": "admin", "password": TEST_PASSWORD},
            headers={"Origin": TEST_ORIGIN},
        )
        assert response.status_code == 200
        assert "kfl_session" in response.cookies
        assert "kfl_csrf" in response.cookies
        assert response.cookies.get("kfl_session")
        assert "password_hash" not in response.json()["user"]
        assert response.json()["user"]["user_id"] == "u-admin"

        profile = client.get("/api/p0/auth/profile")
        assert profile.status_code == 200
        assert profile.json()["role"] == "system_admin"
        assert "password_hash" not in profile.json()["user"]
    finally:
        _set_test_admin_password(None)


def test_logout_revokes_session_and_clears_cookies(client):
    _set_test_admin_password(TEST_PASSWORD)
    try:
        login = client.post(
            "/api/p0/auth/login",
            json={"username": "admin", "password": TEST_PASSWORD},
            headers={"Origin": TEST_ORIGIN},
        )
        assert login.status_code == 200
        csrf = client.cookies.get("kfl_csrf")

        logout = client.post(
            "/api/p0/auth/logout",
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": csrf},
        )
        assert logout.status_code == 200
        assert client.get("/api/p0/auth/profile").status_code == 401
    finally:
        _set_test_admin_password(None)


def test_cookie_authenticated_mutation_requires_csrf_header(client):
    _set_test_admin_password(TEST_PASSWORD)
    try:
        login = client.post(
            "/api/p0/auth/login",
            json={"username": "admin", "password": TEST_PASSWORD},
            headers={"Origin": TEST_ORIGIN},
        )
        assert login.status_code == 200

        denied = client.post("/api/p0/auth/logout", headers={"Origin": TEST_ORIGIN})
        assert denied.status_code == 403

        allowed = client.post(
            "/api/p0/auth/logout",
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert allowed.status_code == 200
    finally:
        _set_test_admin_password(None)


def test_development_mode_does_not_default_missing_identity_to_admin(client):
    response = client.get("/api/p0/documents")
    assert response.status_code == 401


def test_login_rejects_invalid_credentials_without_account_enumeration(client):
    _set_test_admin_password(TEST_PASSWORD)
    try:
        response = client.post(
            "/api/p0/auth/login",
            json={"username": "admin", "password": "wrong-password-value"},
            headers={"Origin": TEST_ORIGIN},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid username or password"
        assert "kfl_session" not in response.cookies
    finally:
        _set_test_admin_password(None)


def test_first_admin_password_setup_requires_one_time_bootstrap_token(client, monkeypatch):
    _set_test_admin_password(None)
    monkeypatch.setenv("KFL_BOOTSTRAP_TOKEN", "one-time-bootstrap-test-token-not-a-secret")
    try:
        status = client.get("/api/p0/auth/bootstrap-status")
        assert status.status_code == 200
        assert status.json()["setup_required"] is True

        denied = client.post(
            "/api/p0/auth/bootstrap",
            json={"bootstrap_token": "wrong-token", "password": TEST_PASSWORD},
            headers={"Origin": TEST_ORIGIN},
        )
        assert denied.status_code == 403

        setup = client.post(
            "/api/p0/auth/bootstrap",
            json={"bootstrap_token": "one-time-bootstrap-test-token-not-a-secret", "password": TEST_PASSWORD},
            headers={"Origin": TEST_ORIGIN},
        )
        assert setup.status_code == 200
        assert setup.json()["user"]["user_id"] == "u-admin"
        assert "password_hash" not in setup.json()["user"]

        repeat = client.post(
            "/api/p0/auth/bootstrap",
            json={"bootstrap_token": "one-time-bootstrap-test-token-not-a-secret", "password": TEST_PASSWORD},
            headers={"Origin": TEST_ORIGIN},
        )
        assert repeat.status_code == 409
    finally:
        _set_test_admin_password(None)
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        conn.execute("DELETE FROM app_settings WHERE key = 'auth_bootstrap_completed'")
        conn.commit()
        conn.close()
        monkeypatch.delenv("KFL_BOOTSTRAP_TOKEN", raising=False)


def test_login_rate_limit_applies_to_invalid_credentials(client):
    _set_test_admin_password(TEST_PASSWORD)
    try:
        statuses = [
            client.post(
                "/api/p0/auth/login",
                json={"username": "admin", "password": "invalid-login-attempt"},
                headers={"Origin": TEST_ORIGIN},
            ).status_code
            for _ in range(6)
        ]
        assert statuses == [401, 401, 401, 401, 401, 429]
    finally:
        _set_test_admin_password(None)


def test_admin_issues_single_use_password_setup_token_for_uninitialized_user(client, admin_headers):
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        conn.execute("UPDATE users SET password_hash = NULL WHERE user_id = 'u-lib'")
        conn.execute("DELETE FROM auth_setup_tokens WHERE user_id = 'u-lib'")
        conn.commit()
    finally:
        conn.close()

    try:
        issued = client.post("/api/p0/auth/users/u-lib/setup-token", headers=admin_headers)
        assert issued.status_code == 200
        token = issued.json()["setup_token"]
        assert issued.json()["use_once"] is True

        setup = client.post(
            "/api/p0/auth/password-setup",
            json={"username": "librarian", "setup_token": token, "password": TEST_PASSWORD},
            headers={"Origin": TEST_ORIGIN},
        )
        assert setup.status_code == 200

        repeated = client.post(
            "/api/p0/auth/password-setup",
            json={"username": "librarian", "setup_token": token, "password": TEST_PASSWORD},
            headers={"Origin": TEST_ORIGIN},
        )
        assert repeated.status_code == 400
    finally:
        conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
        conn.execute("UPDATE users SET password_hash = NULL WHERE user_id = 'u-lib'")
        conn.execute("DELETE FROM auth_setup_tokens WHERE user_id = 'u-lib'")
        conn.commit()
        conn.close()


def test_password_change_revokes_other_sessions_but_preserves_current_session(client):
    from fastapi.testclient import TestClient
    from app.main import app

    _set_test_admin_password(TEST_PASSWORD)
    other_client = TestClient(app)
    try:
        first = client.post("/api/p0/auth/login", json={"username": "admin", "password": TEST_PASSWORD}, headers={"Origin": TEST_ORIGIN})
        other = other_client.post("/api/p0/auth/login", json={"username": "admin", "password": TEST_PASSWORD}, headers={"Origin": TEST_ORIGIN})
        assert first.status_code == 200
        assert other.status_code == 200

        changed = client.post(
            "/api/p0/auth/change-password",
            json={"current_password": TEST_PASSWORD, "new_password": "Another-Test-Password-2026!"},
            headers={"Origin": TEST_ORIGIN, "X-CSRF-Token": client.cookies.get("kfl_csrf")},
        )
        assert changed.status_code == 200
        assert client.get("/api/p0/auth/profile").status_code == 200
        assert other_client.get("/api/p0/auth/profile").status_code == 401

        retry_old = TestClient(app).post("/api/p0/auth/login", json={"username": "admin", "password": TEST_PASSWORD}, headers={"Origin": TEST_ORIGIN})
        retry_new = TestClient(app).post("/api/p0/auth/login", json={"username": "admin", "password": "Another-Test-Password-2026!"}, headers={"Origin": TEST_ORIGIN})
        assert retry_old.status_code == 401
        assert retry_new.status_code == 200
    finally:
        other_client.close()
        _set_test_admin_password(None)

