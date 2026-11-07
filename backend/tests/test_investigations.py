import pytest


class TestInvestigations:
    def test_create_investigation(self, client, safety_headers):
        # Create occurrence first
        occ = client.post("/api/p1/occurrences", json={
            "title": "Investigation test occurrence",
            "description": "For investigation test",
            "occurrence_type": "incident",
            "occurred_at": "2026-10-23T10:00:00+03:00"
        }, headers=safety_headers).json()
        occ_id = occ["occurrence_id"]

        resp = client.post("/api/p1/investigations", json={
            "occurrence_id": occ_id,
            "investigator_id": "u-safety/security",
            "findings": "Initial findings",
            "root_cause": "Human error",
            "recommendations": "Additional training required"
        }, headers=safety_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["occurrence_id"] == occ_id
        assert data["investigator_id"] == "u-safety/security"
        assert data["status"] == "open"
        assert data["investigation_id"].startswith("INV")

    def test_list_investigations(self, client, safety_headers):
        resp = client.get("/api/p1/investigations", headers=safety_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_investigation(self, client, safety_headers):
        occ = client.post("/api/p1/occurrences", json={
            "title": "Update test occurrence",
            "description": "For investigation update test",
            "occurrence_type": "incident",
            "occurred_at": "2026-10-23T10:00:00+03:00"
        }, headers=safety_headers).json()
        occ_id = occ["occurrence_id"]

        inv = client.post("/api/p1/investigations", json={
            "occurrence_id": occ_id,
            "investigator_id": "u-safety/security"
        }, headers=safety_headers).json()
        inv_id = inv["investigation_id"]

        resp = client.patch(f"/api/p1/investigations/{inv_id}", json={
            "status": "completed",
            "findings": "Updated findings",
            "root_cause": "Updated root cause",
            "recommendations": "Updated recommendations"
        }, headers=safety_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["findings"] == "Updated findings"

    def test_nonexistent_investigation_returns_404(self, client, safety_headers):
        resp = client.patch("/api/p1/investigations/NONEXISTENT", json={"status": "closed"}, headers=safety_headers)
        assert resp.status_code == 404

    def test_occurrence_status_updated_on_investigation_creation(self, client, safety_headers):
        occ = client.post("/api/p1/occurrences", json={
            "title": "Status update test",
            "description": "Test occurrence status update",
            "occurrence_type": "incident",
            "occurred_at": "2026-10-23T10:00:00+03:00"
        }, headers=safety_headers).json()
        occ_id = occ["occurrence_id"]

        client.post("/api/p1/investigations", json={
            "occurrence_id": occ_id,
            "investigator_id": "u-safety/security"
        }, headers=safety_headers)

        updated_occ = client.get(f"/api/p1/occurrences/{occ_id}", headers=safety_headers).json()
        assert updated_occ["status"] == "investigating"
        assert updated_occ["investigation_id"] is not None
