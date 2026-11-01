import pytest


class TestDistributions:
    def test_list_distributions(self, client, admin_headers):
        resp = client.get("/api/p0/distributions", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_version_id(self, client, admin_headers):
        resp = client.get("/api/p0/distributions", params={"version_id": "VER-DOC-001"}, headers=admin_headers)
        assert resp.status_code == 200
        assert all(d["version_id"] == "VER-DOC-001" for d in resp.json())

    def test_filter_by_status(self, client, admin_headers):
        resp = client.get("/api/p0/distributions", params={"status": "pending"}, headers=admin_headers)
        assert resp.status_code == 200
        assert all(d["status"] == "pending" for d in resp.json())

    def test_create_distribution(self, client, admin_headers):
        payload = {"version_id": "VER-DOC-001", "recipient_id": "u-chief-pilot", "channel": "email"}
        resp = client.post("/api/p0/distributions", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["distribution_id"].startswith("DIST")
        assert data["status"] == "pending"

    def test_acknowledge_distribution(self, client, admin_headers):
        payload = {"version_id": "VER-DOC-001", "recipient_id": "u-chief-pilot", "channel": "email"}
        create = client.post("/api/p0/distributions", json=payload, headers=admin_headers)
        dist_id = create.json()["distribution_id"]
        resp = client.post(f"/api/p0/distributions/{dist_id}/acknowledge", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "acknowledged"

    def test_non_recipient_cannot_acknowledge_other_holders_distribution(self, client, admin_headers):
        payload = {"version_id": "VER-DOC-001", "recipient_id": "u-chief-pilot", "channel": "email"}
        create = client.post("/api/p0/distributions", json=payload, headers=admin_headers)
        dist_id = create.json()["distribution_id"]
        wrong_actor = client.post(
            f"/api/p0/distributions/{dist_id}/acknowledge",
            headers={"X-Role": "flight_ops_officer", "X-Actor": "u-flight-ops"},
        )
        assert wrong_actor.status_code == 403
        holder = client.post(
            f"/api/p0/distributions/{dist_id}/acknowledge",
            headers={"X-Role": "chief_pilot", "X-Actor": "u-chief-pilot"},
        )
        assert holder.status_code == 200

    def test_unauthorized_access_denied(self, client):
        resp = client.get("/api/p0/distributions", headers={"X-Role": "system_admin", "X-Actor": "nonexistent"})
        assert resp.status_code in (401, 403)
