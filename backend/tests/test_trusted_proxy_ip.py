import sqlite3

from fastapi.testclient import TestClient

from app.main import app


TEST_PASSWORD = "N0tARealCredential-Proxy-Test-2026!"
TEST_ORIGIN = "http://localhost:5173"
TRUSTED_FRONTEND_IP = "172.31.254.3"


def _set_admin_password(password: str | None):
    import os
    import bcrypt

    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() if password else None
        conn.execute("UPDATE users SET password_hash = ? WHERE user_id = 'u-admin'", (password_hash,))
        conn.execute("DELETE FROM auth_login_attempts")
        conn.execute("DELETE FROM auth_sessions WHERE user_id = 'u-admin'")
        conn.commit()
    finally:
        conn.close()


def _failed_login(client: TestClient, forwarded_for: str | None = None) -> int:
    headers = {"Origin": TEST_ORIGIN}
    if forwarded_for is not None:
        headers["X-Forwarded-For"] = forwarded_for
    response = client.post(
        "/api/p0/auth/login",
        json={"username": "admin", "password": "invalid-proxy-test-password"},
        headers=headers,
    )
    return response.status_code


def test_login_throttle_uses_forwarded_address_from_trusted_frontend_only():
    _set_admin_password(TEST_PASSWORD)
    frontend = TestClient(app, client=(TRUSTED_FRONTEND_IP, 50000))
    try:
        assert [_failed_login(frontend, "203.0.113.10") for _ in range(5)] == [401] * 5
        # A different real client arriving through the same frontend gets its own bucket.
        assert _failed_login(frontend, "203.0.113.11") == 401
        assert _failed_login(frontend, "203.0.113.10") == 429
    finally:
        frontend.close()
        _set_admin_password(None)


def test_untrusted_client_cannot_spoof_forwarded_address_for_login_throttle():
    _set_admin_password(TEST_PASSWORD)
    untrusted = TestClient(app, client=("198.51.100.20", 50001))
    try:
        # This source is not the frontend container, so its supplied XFF must be ignored.
        assert [_failed_login(untrusted, "203.0.113.10") for _ in range(5)] == [401] * 5
        # Changing a forged XFF value must not let the same direct peer evade its lockout.
        assert _failed_login(untrusted, "203.0.113.11") == 429
    finally:
        untrusted.close()
        _set_admin_password(None)
