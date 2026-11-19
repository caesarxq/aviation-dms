"""C1 regression: development identity headers must never serve proxied requests.

Staging/prod sit behind Caddy, which always injects X-Forwarded-For / X-Real-IP.
Even if DEV_MODE is enabled, the allow-listed X-Actor/X-Role development path must
reject any request that arrived through a reverse proxy, so an external client
cannot impersonate a role on a deployed host. Local development (no proxy headers)
must keep working.
"""


def test_dev_identity_rejected_when_forwarded_for_present(client, admin_headers):
    headers = {**admin_headers, "X-Forwarded-For": "203.0.113.10"}
    response = client.get("/api/p0/documents", headers=headers)
    assert response.status_code == 401


def test_dev_identity_rejected_when_real_ip_present(client, admin_headers):
    headers = {**admin_headers, "X-Real-IP": "203.0.113.10"}
    response = client.get("/api/p0/documents", headers=headers)
    assert response.status_code == 401


def test_dev_identity_rejected_when_forwarded_header_present(client, admin_headers):
    headers = {**admin_headers, "Forwarded": "for=203.0.113.10;proto=https"}
    response = client.get("/api/p0/documents", headers=headers)
    assert response.status_code == 401


def test_dev_identity_still_allowed_for_local_request_without_proxy_headers(client, admin_headers):
    # Local development / test path: no reverse-proxy forwarding headers.
    response = client.get("/api/p0/documents", headers=admin_headers)
    assert response.status_code == 200