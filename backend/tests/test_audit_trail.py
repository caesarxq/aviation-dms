import pytest


class TestAuditTrail:
    def test_list_audit_events(self, client, admin_headers):
        resp = client.get("/api/p0/audit-events", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_filter_by_entity_type(self, client, admin_headers):
        resp = client.get("/api/p0/audit-events", params={"entity_type": "document"}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["entity_type"] == "document" for e in data)

    def test_filter_by_entity_id(self, client, admin_headers):
        resp = client.get("/api/p0/audit-events", params={"entity_id": "DOC-001"}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(e["entity_id"] == "DOC-001" for e in data)

    def test_audit_event_fields(self, client, admin_headers):
        resp = client.get("/api/p0/audit-events", params={"limit": 1}, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        if len(data) > 0:
            event = data[0]
            assert "event_id" in event
            assert "entity_type" in event
            assert "entity_id" in event
            assert "action" in event
            assert "actor_id" in event
            assert "timestamp" in event

    def test_unauthorized_access_denied(self, client):
        resp = client.get("/api/p0/audit-events", headers={"X-Role": "unknown", "X-Actor": "nobody"})
        assert resp.status_code in (401, 403)
