import pytest


class TestHazards:
    def test_create_hazard(self, client, safety_headers):
        resp = client.post("/api/p1/hazards", json={
            "title": "Runway incursion risk",
            "description": "Unauthorized vehicle on active runway during low visibility",
            "category": "operational",
            "risk_level": "high",
            "likelihood": "possible",
            "severity": "hazardous",
            "mitigation": "Implement vehicle tracking and clearance procedures",
            "owner_id": "u-safety"
        }, headers=safety_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Runway incursion risk"
        assert data["status"] == "identified"
        assert data["risk_level"] == "high"
        assert data["hazard_id"].startswith("HAZ")

    def test_list_hazards(self, client, safety_headers):
        resp = client.get("/api/p1/hazards", headers=safety_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_hazard(self, client, safety_headers):
        resp = client.post("/api/p1/hazards", json={
            "title": "Fuel leak hazard",
            "description": "Minor fuel leak observed during refueling",
            "category": "technical",
            "risk_level": "medium"
        }, headers=safety_headers)
        hazard_id = resp.json()["hazard_id"]
        resp = client.patch(f"/api/p1/hazards/{hazard_id}", json={
            "status": "mitigated",
            "risk_level": "low",
            "mitigation": "Repaired seal and added secondary containment"
        }, headers=safety_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "mitigated"
        assert data["risk_level"] == "low"

    def test_nonexistent_hazard_returns_404(self, client, safety_headers):
        resp = client.patch("/api/p1/hazards/NONEXISTENT", json={"status": "closed"}, headers=safety_headers)
        assert resp.status_code == 404

    def test_hazard_defaults(self, client, safety_headers):
        resp = client.post("/api/p1/hazards", json={
            "title": "Default test",
            "description": "Testing default values"
        }, headers=safety_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "operational"
        assert data["risk_level"] == "medium"
        assert data["status"] == "identified"
