"""M1 regression: the backend Content-Security-Policy must not allow unsafe-eval.

The frontend nginx/Caddy CSP already uses script-src 'self'; the backend
SecurityHeadersMiddleware must match and not weaken it with 'unsafe-eval'.
"""


def test_csp_does_not_allow_unsafe_eval(client):
    response = client.get("/health")
    csp = response.headers.get("Content-Security-Policy", "")
    assert csp, "a Content-Security-Policy header must be present"
    assert "unsafe-eval" not in csp
    assert "script-src 'self'" in csp


def test_security_headers_present(client):
    response = client.get("/health")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"


def test_secure_session_cookie_satisfies_host_prefix_constraints(monkeypatch):
    # M4: with SESSION_COOKIE_SECURE=true (HTTPS staging/prod) the cookie becomes
    # __Host-kfl_session, which browsers only accept with Secure + Path=/ + no Domain.
    from app import p0_routes

    monkeypatch.setattr(p0_routes, "SESSION_COOKIE_SECURE", True)
    monkeypatch.setattr(p0_routes, "SESSION_COOKIE", "__Host-kfl_session")
    monkeypatch.setattr(p0_routes, "CSRF_COOKIE", "__Host-kfl_csrf")
    response = p0_routes._session_response({"ok": True}, "token-value", "csrf-value")
    cookies = response.headers.getlist("set-cookie")
    session = next(c for c in cookies if c.startswith("__Host-kfl_session="))
    assert "Secure" in session
    assert "Path=/" in session
    assert "Domain=" not in session
    assert "httponly" in session.lower()
    csrf = next(c for c in cookies if c.startswith("__Host-kfl_csrf="))
    assert "Secure" in csrf and "Path=/" in csrf and "Domain=" not in csrf