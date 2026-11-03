"""Focused tests for SEC-H1 (rate limiter), SEC-H2 (trusted proxy IP), SEC-H3 (session absolute max)."""

import os
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app

TEST_ORIGIN = "http://localhost:5173"


# ── helpers ──────────────────────────────────────────────────────────────────

def _set_admin_password(password: str | None):
    conn = sqlite3.connect(os.environ["DMS_DB_PATH"])
    try:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode() if password else None
        conn.execute("UPDATE users SET password_hash = ? WHERE user_id = 'u-admin'", (password_hash,))
        conn.execute("DELETE FROM auth_sessions WHERE user_id = 'u-admin'")
        conn.execute("DELETE FROM auth_login_attempts")
        conn.commit()
    finally:
        conn.close()


def _login(client: TestClient, password: str = "N0tARealCredential-RateLimit-Test-2026!"):
    return client.post(
        "/api/p0/auth/login",
        json={"username": "admin", "password": password},
        headers={"Origin": TEST_ORIGIN},
    )


@pytest.fixture(autouse=True)
def _restore_rate_limiter_configuration(monkeypatch):
    yield
    # Reload after monkeypatch restores environment so module-level settings
    # cannot leak between tests.
    monkeypatch.undo()
    import importlib
    from app import rate_limiter
    importlib.reload(rate_limiter)
    rate_limiter._limiter._buckets.clear()


# ── SEC-H1: Rate Limiter ─────────────────────────────────────────────────────

class TestRateLimiter:

    def test_authenticated_requests_use_the_uniform_api_limit(self, monkeypatch):
        """The pre-auth middleware applies one configurable limit to every API client."""
        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MIN", "50")
        monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")

        import importlib
        from app import rate_limiter
        importlib.reload(rate_limiter)
        from app.rate_limiter import _limiter
        _limiter._buckets.clear()

        client = TestClient(fastapi_app, client=("10.99.88.79", 60000))
        test_pw = "N0tARealCredential-RateLimit-Test-2026!"
        _set_admin_password(test_pw)
        try:
            assert _login(client, test_pw).status_code == 200
            # Login also passes through the pre-auth API limiter; isolate this check.
            _limiter._buckets.clear()
            profile_statuses = [client.get("/api/p0/auth/profile").status_code for _ in range(50)]
            assert profile_statuses == [200] * 50
            assert client.get("/api/p0/auth/profile").status_code == 429
        finally:
            _set_admin_password(None)
            _limiter._buckets.clear()

    def test_retry_after_reports_remaining_window(self, monkeypatch):
        """429 Retry-After reports when the oldest request leaves the window."""
        import importlib
        from types import SimpleNamespace
        from app import rate_limiter

        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MIN", "1")
        monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "10")
        importlib.reload(rate_limiter)
        from app.rate_limiter import _limiter
        _limiter._buckets.clear()

        now = [100.0]
        monkeypatch.setattr(rate_limiter, "time", SimpleNamespace(monotonic=lambda: now[0]))
        client = TestClient(fastapi_app, client=("10.99.88.83", 60006))
        assert client.get("/api/p0/auth/bootstrap-status").status_code == 200

        now[0] = 103.0
        limited = client.get("/api/p0/auth/bootstrap-status")
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "7"
        _limiter._buckets.clear()

    def test_unauthenticated_protected_api_requests_are_rate_limited(self, monkeypatch):
        """Unauthorized protected requests consume the same API client budget."""
        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MIN", "2")
        monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
        import importlib
        from app import rate_limiter
        importlib.reload(rate_limiter)
        from app.rate_limiter import _limiter
        _limiter._buckets.clear()

        client = TestClient(fastapi_app, client=("10.99.88.80", 60003))
        assert client.get("/api/p0/auth/profile").status_code == 401
        assert client.get("/api/p1/documents").status_code in (401, 404, 405)
        assert client.get("/api/p0/auth/profile").status_code == 429
        _limiter._buckets.clear()

    def test_rate_limit_response_keeps_cors_headers(self, monkeypatch):
        """429 responses must retain allowed-origin CORS headers."""
        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MIN", "1")
        import importlib
        from app import rate_limiter
        importlib.reload(rate_limiter)
        from app.rate_limiter import _limiter
        _limiter._buckets.clear()

        client = TestClient(fastapi_app, client=("10.99.88.84", 60007))
        headers = {"Origin": TEST_ORIGIN}
        assert client.get("/api/p0/auth/bootstrap-status", headers=headers).status_code == 200
        limited = client.get("/api/p0/auth/bootstrap-status", headers=headers)
        assert limited.status_code == 429
        assert limited.headers["access-control-allow-origin"] == TEST_ORIGIN
        _limiter._buckets.clear()

    def test_trusted_forwarded_ip_separates_proxy_clients(self, monkeypatch):
        """Forwarded client IP is honored only when the exact proxy peer is trusted."""
        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MIN", "1")
        monkeypatch.setenv("DMS_TRUSTED_FRONTEND_IP", "10.99.88.81")
        import importlib
        from app import rate_limiter
        importlib.reload(rate_limiter)
        from app.rate_limiter import _limiter
        _limiter._buckets.clear()

        trusted = TestClient(fastapi_app, client=("10.99.88.81", 60004))
        assert trusted.get("/api/p0/auth/bootstrap-status", headers={"X-Forwarded-For": "192.0.2.10"}).status_code == 200
        assert trusted.get("/api/p0/auth/bootstrap-status", headers={"X-Forwarded-For": "192.0.2.11"}).status_code == 200
        assert trusted.get("/api/p0/auth/bootstrap-status", headers={"X-Forwarded-For": "192.0.2.10"}).status_code == 429

        _limiter._buckets.clear()
        untrusted = TestClient(fastapi_app, client=("10.99.88.82", 60005))
        assert untrusted.get("/api/p0/auth/bootstrap-status", headers={"X-Forwarded-For": "192.0.2.20"}).status_code == 200
        assert untrusted.get("/api/p0/auth/bootstrap-status", headers={"X-Forwarded-For": "192.0.2.21"}).status_code == 429
        _limiter._buckets.clear()

    def test_limiter_state_is_bounded_and_expires_idle_clients(self):
        """Client bucket count is capped, and idle buckets expire on subsequent requests."""
        from app.rate_limiter import SlidingWindowRateLimiter
        limiter = SlidingWindowRateLimiter(max_buckets=2)
        assert limiter.is_allowed("client-a", 1, window=0.01)
        assert limiter.is_allowed("client-b", 1, window=0.01)
        assert limiter.is_allowed("client-c", 1, window=0.01)
        assert len(limiter._buckets) == 2
        time.sleep(0.02)
        assert limiter.is_allowed("client-d", 1, window=0.01)
        assert "client-c" not in limiter._buckets
        assert len(limiter._buckets) <= 2

    def test_public_requests_return_429_on_limit(self, monkeypatch):
        """API requests return 429 once the configured per-client limit is exceeded."""
        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MIN", "5")
        import importlib
        from app import rate_limiter
        importlib.reload(rate_limiter)
        from app.rate_limiter import _limiter
        _limiter._buckets.clear()

        # Use a unique IP so we don't collide with other tests using the shared limiter
        client = TestClient(fastapi_app, client=("10.99.88.77", 60001))

        # Hit the public bootstrap-status endpoint many times
        statuses = []
        for _ in range(40):
            r = client.get("/api/p0/auth/bootstrap-status")
            statuses.append(r.status_code)
        assert 429 in statuses, f"Expected 429 in statuses: {statuses[:35]}"

    def test_non_api_paths_are_not_rate_limited(self, monkeypatch):
        """The /health endpoint remains available after the API client limit is hit."""
        monkeypatch.setenv("RATE_LIMIT_REQUESTS_PER_MIN", "1")
        import importlib
        from app import rate_limiter
        importlib.reload(rate_limiter)
        from app.rate_limiter import _limiter
        _limiter._buckets.clear()

        client = TestClient(fastapi_app, client=("10.99.88.78", 60002))
        assert client.get("/api/p0/auth/bootstrap-status").status_code == 200
        assert client.get("/api/p0/auth/bootstrap-status").status_code == 429
        for _ in range(50):
            r = client.get("/health")
            assert r.status_code == 200, f"Got {r.status_code} on /health"
        _limiter._buckets.clear()


# ── SEC-H2: Configurable Trusted Proxy IP ────────────────────────────────────

class TestTrustedProxyIP:

    def test_trusted_frontend_ip_is_configurable(self, monkeypatch):
        """TRUSTED_FRONTEND_IP should read from DMS_TRUSTED_FRONTEND_IP env var."""
        # Default value
        from app.p0_routes import TRUSTED_FRONTEND_IP
        assert TRUSTED_FRONTEND_IP == "172.31.254.3"

        # Set a different value
        monkeypatch.setenv("DMS_TRUSTED_FRONTEND_IP", "10.0.0.1")
        import importlib
        routes_module = importlib.import_module("app.p0_routes")
        importlib.reload(routes_module)
        from app.p0_routes import TRUSTED_FRONTEND_IP as new_ip
        assert new_ip == "10.0.0.1"

        # Restore
        monkeypatch.delenv("DMS_TRUSTED_FRONTEND_IP", raising=False)
        importlib.reload(routes_module)

    def test_docker_compose_passes_trusted_ip(self):
        """docker-compose.yml should include DMS_TRUSTED_FRONTEND_IP."""
        compose_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "docker-compose.yml"
        )
        with open(compose_path) as f:
            compose = f.read()
        assert re.search(r"(?m)^\s+DMS_TRUSTED_FRONTEND_IP:\s*['\"]?172\.31\.254\.3['\"]?\s*$", compose)
        assert 'RATE_LIMIT_REQUESTS_PER_MIN: "${RATE_LIMIT_REQUESTS_PER_MIN:-100}"' in compose
        assert 'SESSION_ABSOLUTE_MAX_SECONDS: "${SESSION_ABSOLUTE_MAX_SECONDS:-86400}"' in compose


# ── SEC-H3: Session Absolute Max TTL ─────────────────────────────────────────

class TestSessionAbsoluteMax:

    def test_session_absolute_max_is_configurable(self, monkeypatch):
        """SESSION_ABSOLUTE_MAX_SECONDS should read from env with default 86400."""
        from app.p0_auth import SESSION_ABSOLUTE_MAX_SECONDS
        assert SESSION_ABSOLUTE_MAX_SECONDS == 86400

        monkeypatch.setenv("SESSION_ABSOLUTE_MAX_SECONDS", "3600")
        import importlib
        auth_module = importlib.import_module("app.p0_auth")
        importlib.reload(auth_module)
        from app.p0_auth import SESSION_ABSOLUTE_MAX_SECONDS as new_val
        assert new_val == 3600

        monkeypatch.delenv("SESSION_ABSOLUTE_MAX_SECONDS", raising=False)
        importlib.reload(auth_module)

    def test_session_expires_at_absolute_max(self, monkeypatch):
        """A session older than absolute max should be revoked even if sliding expiry is extended."""
        import importlib
        auth_module = importlib.import_module("app.p0_auth")
        importlib.reload(auth_module)

        TEST_PW = "N0tARealCredential-AbsMax-Test-2026!"
        _set_admin_password(TEST_PW)

        # Set absolute max to 2 seconds for testing
        monkeypatch.setenv("SESSION_ABSOLUTE_MAX_SECONDS", "2")
        importlib.reload(auth_module)

        try:
            client = TestClient(fastapi_app)
            resp = _login(client, TEST_PW)
            assert resp.status_code == 200

            # Profile should work immediately
            assert client.get("/api/p0/auth/profile").status_code == 200

            # Wait longer than the absolute max
            time.sleep(3)

            # Now the session should be rejected
            r = client.get("/api/p0/auth/profile")
            assert r.status_code == 401, f"Expected 401 after absolute max, got {r.status_code}"
        finally:
            _set_admin_password(None)
            monkeypatch.delenv("SESSION_ABSOLUTE_MAX_SECONDS", raising=False)
            importlib.reload(auth_module)

    def test_sliding_session_not_revoked_before_absolute_max(self, monkeypatch):
        """A session within absolute max but after sliding TTL should still work after extension."""
        import importlib
        auth_module = importlib.import_module("app.p0_auth")
        importlib.reload(auth_module)

        TEST_PW = "N0tARealCredential-AbsMax-Sliding-2026!"
        _set_admin_password(TEST_PW)

        # Short sliding TTL, long absolute max
        monkeypatch.setenv("SESSION_TTL_SECONDS", "3")
        monkeypatch.setenv("SESSION_ABSOLUTE_MAX_SECONDS", "3600")
        importlib.reload(auth_module)

        try:
            client = TestClient(fastapi_app)
            resp = _login(client, TEST_PW)
            assert resp.status_code == 200

            # Wait near the sliding TTL but before it fully expires
            time.sleep(2)
            # First request extends the sliding window
            assert client.get("/api/p0/auth/profile").status_code == 200

            # Wait again
            time.sleep(2)
            # Should still work because sliding window was extended
            assert client.get("/api/p0/auth/profile").status_code == 200
        finally:
            _set_admin_password(None)
            monkeypatch.delenv("SESSION_TTL_SECONDS", raising=False)
            monkeypatch.delenv("SESSION_ABSOLUTE_MAX_SECONDS", raising=False)
            importlib.reload(auth_module)