import pytest


class TestSafetyActions:
    def test_create_safety_action(self, client, safety_headers):
        resp = client.post("/api/p1/safety-actions", json={
            "title": "Runway incursion mitigation",
            "description": "Implement vehicle tracking and clearance procedures",
            "action_type": "corrective",
            "owner_id": "u-safety",
            "due_date": "2026-11-30",
            "occurrence_id": "OCC-001",
            "hazard_id": "HAZ-001"
        }, headers=safety_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Runway incursion mitigation"
        assert data["status"] == "open"
        assert data["action_type"] == "corrective"
        assert data["action_id"].startswith("SA")

    def test_list_safety_actions(self, client, safety_headers):
        resp = client.get("/api/p1/safety-actions", headers=safety_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_occurrence_id(self, client, safety_headers):
        resp = client.post("/api/p1/safety-actions", json={
            "title": "Occurrence-linked action",
            "description": "Test occurrence filter",
            "action_type": "corrective",
            "owner_id": "u-safety",
            "occurrence_id": "OCC-FILTER"
        }, headers=safety_headers)
        assert resp.status_code == 201
        resp = client.get("/api/p1/safety-actions", params={"occurrence_id": "OCC-FILTER"}, headers=safety_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert all(a["occurrence_id"] == "OCC-FILTER" for a in data)

    def test_update_safety_action(self, client, safety_headers):
        resp = client.post("/api/p1/safety-actions", json={
            "title": "Updatable action",
            "description": "Test update",
            "action_type": "corrective",
            "owner_id": "u-safety"
        }, headers=safety_headers)
        action_id = resp.json()["action_id"]
        resp = client.patch(f"/api/p1/safety-actions/{action_id}", json={
            "status": "completed",
            "evidence": "Training records attached",
            "effectiveness_check": "No further incidents in 30 days"
        }, headers=safety_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["evidence"] == "Training records attached"

    def test_nonexistent_safety_action_returns_404(self, client, safety_headers):
        resp = client.patch("/api/p1/safety-actions/NONEXISTENT", json={"status": "closed"}, headers=safety_headers)
        assert resp.status_code == 404
